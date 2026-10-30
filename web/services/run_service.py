import hashlib
import json
import re
import sqlite3
from pathlib import Path
from uuid import uuid4

from web.db import connect_database
from web.domain.bundles import build_cq_bundle
from web.domain.catalog import _cq_file, _load_cqs
from web.domain.validation import validate_cq2onto_confirmation, validate_cq_term_prediction
from web.repositories import (add_artifact, create_run, get_run, get_run_items,
                              transition_run, update_run_item)


class RunServiceError(ValueError):
    pass


def _fingerprint_files(files: list[tuple[str, Path]]) -> str:
    digest = hashlib.sha256()
    for label, path in sorted(files, key=lambda entry: entry[0]):
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _provenance(project_root: Path, items: list[dict]) -> tuple[str, str]:
    source_root = Path(__file__).resolve().parents[2]
    evaluator_files = [
        (path.relative_to(source_root).as_posix(), path)
        for path in (source_root / "web" / "services").glob("*.py")
    ]
    evaluator_files += [
        (path.relative_to(source_root).as_posix(), path)
        for path in (source_root / "web" / "domain").glob("*.py")
    ]
    for item in items:
        task_root = Path(project_root) / ("CQ2Term" if item["task"] == "cq2term" else "CQ2Onto") / "scripts"
        if task_root.is_dir():
            evaluator_files.extend((path.relative_to(project_root).as_posix(), path)
                                   for path in task_root.rglob("*.py") if path.is_file())
    evaluator_version = "sha256:" + _fingerprint_files(evaluator_files)

    gold_files = []
    for item in items:
        domain = item["domain"]
        if item["task"] == "cq2term":
            paths = [Path(project_root) / "CQ2Term" / "00_gold_standard" / domain / f"cq_to_terms_{domain}.json"]
        else:
            base = Path(project_root) / "CQ2Onto" / "00_gold_standard" / domain
            paths = [base / "ontology" / f"sub_{domain}.owl", base / "axioms" / f"{domain}_axiom_gold.json"]
        for path in paths:
            if not path.is_file():
                raise RunServiceError(f"Missing gold input required for provenance: {path.name}")
            gold_files.append((path.relative_to(project_root).as_posix(), path))
    return evaluator_version, _fingerprint_files(gold_files)


class RunService:
    def __init__(self, db_path: Path, runs_root: Path, project_root: Path, max_upload_bytes: int = 50 * 1024 * 1024):
        self.db_path = Path(db_path)
        self.runs_root = Path(runs_root)
        self.project_root = Path(project_root)
        self.max_upload_bytes = max_upload_bytes

    def create_draft_run(self, user_id: str, agent_id: str, model_id: str | None, items: list[dict], config: dict) -> str:
        if not items:
            raise RunServiceError("A run must contain at least one item.")
        prepared = []
        try:
            for item in items:
                task, domain = item["task"], item["domain"]
                if task not in ("cq2term", "cq2onto"):
                    raise RunServiceError(f"Unsupported task: {task}")
                bundle = build_cq_bundle(self.project_root, task, domain)
                prepared.append({"task": task, "domain": domain, "bundle_sha256": hashlib.sha256(bundle).hexdigest()})
        except (KeyError, ValueError, FileNotFoundError) as exc:
            if isinstance(exc, RunServiceError):
                raise
            raise RunServiceError(f"Invalid task or domain: {exc}") from exc
        if model_id is None:
            with connect_database(self.db_path) as conn:
                model = conn.execute("SELECT id FROM models WHERE user_id=? ORDER BY created_at,id LIMIT 1", (user_id,)).fetchone()
            if model is None:
                raise RunServiceError("A model is required to create a run.")
            model_id = model["id"]
        with connect_database(self.db_path) as conn:
            agent = conn.execute("SELECT 1 FROM agents WHERE id=? AND user_id=?", (agent_id, user_id)).fetchone()
            model = conn.execute("SELECT agent_id FROM models WHERE id=? AND user_id=?", (model_id, user_id)).fetchone()
        if agent is None:
            raise RunServiceError("Agent not found.")
        if model is None or model["agent_id"] != agent_id:
            raise RunServiceError("Model does not belong to the selected Agent.")
        evaluator_version, gold_fingerprint = _provenance(self.project_root, prepared)
        run = create_run(self.db_path, user_id=user_id, agent_id=agent_id, model_id=model_id,
                         items=prepared, config=config, runs_root=self.runs_root, initial_status="draft",
                         evaluator_version=evaluator_version, gold_fingerprint=gold_fingerprint)
        return run["id"]

    def _item(self, run_id: str, item_id: str) -> tuple[dict, dict]:
        run = get_run(self.db_path, user_id="local", run_id=run_id)
        if not run:
            raise RunServiceError("Run not found.")
        item = next((row for row in run["items"] if row["id"] == item_id), None)
        if item is None:
            raise RunServiceError("Run item not found.")
        if run["status"] != "draft":
            raise RunServiceError("Uploads and confirmations are allowed only for draft runs.")
        return run, item

    def save_item_upload(self, run_id: str, item_id: str, upload) -> dict:
        run, item = self._item(run_id, item_id)
        filename = getattr(upload, "filename", None)
        if not isinstance(filename, str) or not filename or filename in (".", "..") or "/" in filename or "\\" in filename or Path(filename).name != filename:
            raise RunServiceError("Invalid upload filename.")
        extension = Path(filename).suffix.lower()
        allowed = {".json"} if item["task"] == "cq2term" else {".owl", ".rdf", ".xml", ".ttl", ".nt", ".n3"}
        if extension not in allowed:
            raise RunServiceError(f"Unsupported file extension for {item['task']}.")
        fileobj = getattr(upload, "file", None)
        if fileobj is not None:
            data = fileobj.read(self.max_upload_bytes + 1)
        else:
            data = upload.read()
            if hasattr(data, "__await__"):
                raise RunServiceError("Upload must expose a synchronous file stream.")
        if len(data) > self.max_upload_bytes:
            raise RunServiceError("Upload exceeds configured size limit.")
        if item["task"] == "cq2term":
            try:
                payload = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RunServiceError("CQ2Term upload is not valid UTF-8 JSON.") from exc
            result = validate_cq_term_prediction(self.project_root, item["domain"], payload)
            if not result.valid:
                raise RunServiceError("CQ2Term upload is invalid: " + " ".join(result.errors))
        else:
            try:
                try:
                    from rdflib import Graph
                except ImportError:
                    if extension not in {".owl", ".rdf", ".xml"}:
                        raise
                    from xml.etree import ElementTree
                    ElementTree.fromstring(data)
                else:
                    Graph().parse(data=data, format={".owl": "xml", ".rdf": "xml", ".xml": "xml", ".ttl": "turtle", ".nt": "nt", ".n3": "n3"}[extension])
            except Exception as exc:
                raise RunServiceError(f"Ontology upload cannot be parsed: {exc}") from exc
        input_dir = Path(run["run_path"]) / "items" / item_id / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{uuid4().hex}{extension}"
        destination = input_dir / safe_name
        destination.write_bytes(data)
        record = add_artifact(self.db_path, user_id=run["user_id"], run_id=run_id, run_item_id=item_id,
                              category="input", relative_path=destination.relative_to(run["run_path"]).as_posix(),
                              media_type={".json": "application/json", ".ttl": "text/turtle", ".nt": "application/n-triples",
                                          ".n3": "text/n3", ".owl": "application/rdf+xml", ".rdf": "application/rdf+xml",
                                          ".xml": "application/xml"}[extension],
                              size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), name=filename)
        update_run_item(self.db_path, user_id=run["user_id"], run_id=run_id, item_id=item_id,
                        input_path=str(destination), bundle_sha256=item["bundle_sha256"])
        return record

    def set_confirmation(self, run_id: str, item_id: str, confirmed_ids: list[str]) -> None:
        run, item = self._item(run_id, item_id)
        if item["task"] != "cq2onto":
            raise RunServiceError("CQ confirmation applies only to CQ2Onto items.")
        result = validate_cq2onto_confirmation(self.project_root, item["domain"], confirmed_ids)
        if not result.valid:
            raise RunServiceError("CQ confirmation is incomplete: " + " ".join(result.errors))
        update_run_item(self.db_path, user_id=run["user_id"], run_id=run_id, item_id=item_id,
                        confirmation_json=json.dumps(confirmed_ids, ensure_ascii=False))

    def start_run(self, run_id: str) -> None:
        run = get_run(self.db_path, user_id="local", run_id=run_id)
        if not run:
            raise RunServiceError("Run not found.")
        try:
            with connect_database(self.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                current = conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
                if not current or current["status"] != "draft":
                    raise RunServiceError("Run is not a draft.")
                items = conn.execute("SELECT * FROM run_items WHERE run_id=? ORDER BY created_at,id", (run_id,)).fetchall()
                for item in items:
                    item_input = Path(run["run_path"]) / "items" / item["id"] / "input"
                    input_path = Path(item["input_path"]).resolve() if item["input_path"] else None
                    if not input_path or not input_path.is_relative_to(item_input.resolve()) or not input_path.is_file():
                        raise RunServiceError(f"Run item {item['id']} requires an upload.")
                    data = input_path.read_bytes()
                    if item["task"] == "cq2term":
                        try:
                            valid = validate_cq_term_prediction(self.project_root, item["domain"], json.loads(data.decode("utf-8")))
                        except Exception as exc:
                            raise RunServiceError("CQ2Term upload is not valid JSON.") from exc
                    else:
                        if not item["confirmation_json"]:
                            raise RunServiceError(f"Run item {item['id']} requires complete CQ confirmation.")
                        valid = validate_cq2onto_confirmation(self.project_root, item["domain"], json.loads(item["confirmation_json"]))
                        try:
                            from rdflib import Graph
                            Graph().parse(source=input_path)
                        except ImportError:
                            try:
                                from xml.etree import ElementTree
                                ElementTree.parse(input_path)
                            except Exception as exc:
                                raise RunServiceError(f"Ontology upload cannot be parsed: {exc}") from exc
                        except Exception as exc:
                            raise RunServiceError(f"Ontology upload cannot be parsed: {exc}") from exc
                    if not valid.valid:
                        raise RunServiceError("Run item upload is not valid: " + " ".join(valid.errors))
                now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
                conn.execute("UPDATE runs SET status='queued' WHERE id=? AND status='draft'", (run_id,))
                conn.execute("UPDATE run_items SET status='queued' WHERE run_id=?", (run_id,))
                conn.execute("INSERT INTO run_events VALUES (lower(hex(randomblob(16))), ?, ?, 'queued', '{}', ?)", (run["user_id"], run_id, now))
        except sqlite3.IntegrityError as exc:
            raise RunServiceError(str(exc)) from exc
