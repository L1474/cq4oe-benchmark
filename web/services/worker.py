import json
import threading
import time
from pathlib import Path

from web.db import connect_database
from web.repositories import (add_artifact, add_event, claim_oldest_queued_run, get_run,
                              recover_interrupted_runs, save_metrics, save_stage_state,
                              transition_run)
from web.services.commands import build_cq2onto_commands, build_cq2term_command
from web.services.evaluator import EvaluationCancelled, run_stage
from web.services.metrics import extract_cq2onto_metrics, extract_cq2term_metrics
from web.services.artifacts import store_artifact
from web.services.privacy import redact_paths
from web.types import RunItem, RunPaths, EvaluationStage


class LocalEvaluator:
    def __init__(self, project_root, ollama_url="http://127.0.0.1:11434"):
        self.project_root = Path(project_root)
        self.ollama_url = ollama_url
        self.stop_event = None

    def evaluate_item(self, run, item, event_sink):
        item_root = Path(run["run_path"]) / "items" / item["id"]
        paths = RunPaths(item_root)
        paths.ensure()
        domain_item = RunItem(item["id"], item["task"], item["domain"], Path(item["input_path"]))
        config = json.loads(run["config_json"])
        stages = ([EvaluationStage("evaluate", build_cq2term_command(self.project_root, domain_item, paths, config),
                                   (self.project_root / "CQ2Term").resolve())]
                  if item["task"] == "cq2term" else build_cq2onto_commands(self.project_root, domain_item, paths, config,
                                                                            ollama_url=self.ollama_url))
        for index, stage in enumerate(stages):
            event_sink({"stage": stage.name, "status": "started"})
            try:
                run_stage(stage, paths.logs / f"{stage.name}.stdout.log", paths.logs / f"{stage.name}.stderr.log",
                          lambda output: event_sink({**output, "status": "running"}),
                          stop_event=self.stop_event, env={"OLLAMA_HOST": self.ollama_url})
            except EvaluationCancelled:
                event_sink({"stage": stage.name, "status": "interrupted"})
                raise
            except Exception as exc:
                event_sink({"stage": stage.name, "status": "failed", "error": str(exc)})
                for later in stages[index + 1:]:
                    event_sink({"stage": later.name, "status": "blocked", "reason": f"{stage.name} failed"})
                raise
            event_sink({"stage": stage.name, "status": "completed"})
        if item["task"] == "cq2term":
            metrics = extract_cq2term_metrics(paths.results / "06_cq_terms/result.json", paths.results / "06_cq_terms/cq_coverage.csv")
        else:
            metrics = extract_cq2onto_metrics(paths)
        return {"metrics": [m.__dict__ for m in metrics], "artifacts": []}


class EvaluationWorker:
    def __init__(self, db_path, runs_root, readiness, evaluator=None, *, project_root=None,
                 ollama_url="http://127.0.0.1:11434", poll_interval=1):
        self.db_path = Path(db_path)
        self.runs_root = Path(runs_root)
        self.readiness = readiness
        self.evaluator = evaluator or LocalEvaluator(project_root or Path.cwd(), ollama_url)
        self.poll_interval = poll_interval
        self.stop_event = threading.Event()

    def recover(self):
        return recover_interrupted_runs(self.db_path)

    def _claim(self):
        connection = connect_database(self.db_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            run = claim_oldest_queued_run(connection)
            connection.commit()
            return run
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _record_event(self, run, item, event):
        event = redact_paths(event)
        payload = dict(event)
        stage = payload.pop("stage", None)
        status = payload.pop("status", None)
        add_event(self.db_path, user_id=run["user_id"], run_id=run["id"], event_type="stage", payload={"item_id": item["id"], **event})
        if stage and status:
            save_stage_state(self.db_path, user_id=run["user_id"], run_id=run["id"], run_item_id=item["id"],
                             stage=stage, status=status, state=payload)

    def process_one(self):
        if self.stop_event.is_set() or not self.readiness.is_ready():
            return False
        run = self._claim()
        if run is None:
            return False
        data = get_run(self.db_path, user_id=run["user_id"], run_id=run["id"])
        failures = 0
        completed = 0
        for item in data["items"]:
            if self.stop_event.is_set():
                self._interrupt_run(run)
                return True
            with connect_database(self.db_path) as conn:
                conn.execute("UPDATE run_items SET status='running', started_at=datetime('now') WHERE id=?", (item["id"],))
            try:
                result = self.evaluator.evaluate_item(run, item, lambda event: self._record_event(run, item, event)) or {}
                if result.get("metrics"):
                    records = [{**metric, "run_item_id": item["id"]} for metric in result["metrics"]]
                    save_metrics(self.db_path, user_id=run["user_id"], run_id=run["id"], metrics=records)
                self._index_outputs(run, item, result.get("artifacts", []))
                completed += 1
                status = "completed"
            except EvaluationCancelled:
                self._index_outputs(run, item)
                self._interrupt_run(run)
                return True
            except Exception as exc:
                failures += 1
                try:
                    self._index_outputs(run, item)
                except Exception as artifact_error:
                    exc = RuntimeError(f"{exc}; output indexing failed: {artifact_error}")
                add_event(self.db_path, user_id=run["user_id"], run_id=run["id"], event_type="item_failed",
                          payload={"item_id": item["id"], "error": redact_paths(str(exc))})
                status = "failed"
            with connect_database(self.db_path) as conn:
                conn.execute("UPDATE run_items SET status=?, finished_at=datetime('now') WHERE id=?", (status, item["id"]))
        final = "completed" if not failures else "partial" if completed else "failed"
        transition_run(self.db_path, run_id=run["id"], expected="running", new=final)
        return True

    def _interrupt_run(self, run):
        with connect_database(self.db_path) as conn:
            conn.execute("UPDATE run_items SET status='failed', finished_at=datetime('now') "
                         "WHERE run_id=? AND status IN ('queued','running')", (run["id"],))
        add_event(self.db_path, user_id=run["user_id"], run_id=run["id"], event_type="interrupted",
                  payload={"reason": "application shutdown"})
        transition_run(self.db_path, run_id=run["id"], expected="running", new="failed")

    def _index_outputs(self, run, item, artifact_metadata=()):
        root = Path(run["run_path"])
        item_root = root / "items" / item["id"]
        declared = {Path(entry["path"]).resolve(): entry for entry in artifact_metadata
                    if isinstance(entry, dict) and entry.get("path")}
        sources = {}
        for category in ("work", "results", "logs"):
            sources.update({path.resolve(): category for path in (item_root / category).rglob("*") if path.is_file()})
        for source in declared:
            if source.is_file() and source.is_relative_to(item_root.resolve()):
                sources.setdefault(source, "results")
        for path, source_category in sources.items():
            metadata = declared.get(path, {})
            category = metadata.get("category", source_category)
            media_type = metadata.get("media_type", "text/plain")
            record = store_artifact(item_root, path, category, media_type)
            add_artifact(self.db_path, user_id=run["user_id"], run_id=run["id"], run_item_id=item["id"],
                         category=category, relative_path=f"items/{item['id']}/{record.relative_path}",
                         media_type=record.media_type, size_bytes=record.size_bytes, sha256=record.sha256,
                         name=metadata.get("name", record.name))

    def run_forever(self, stop_event: threading.Event):
        self.stop_event = stop_event
        if hasattr(self.evaluator, "stop_event"):
            self.evaluator.stop_event = stop_event
        self.recover()
        while not stop_event.is_set():
            try:
                if not self.process_one():
                    stop_event.wait(self.poll_interval)
            except Exception:
                stop_event.wait(self.poll_interval)
