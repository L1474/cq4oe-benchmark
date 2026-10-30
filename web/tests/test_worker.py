import threading
import time
from pathlib import Path

from web.db import connect_database, initialize_database
from web.repositories import create_agent, create_model, create_run, get_run
from web.services.worker import EvaluationWorker


class Ready:
    def __init__(self, ready=True):
        self.ready = ready

    def is_ready(self):
        return self.ready


class Evaluator:
    def __init__(self, fail_domain=None):
        self.seen = []
        self.fail_domain = fail_domain

    def evaluate_item(self, run, item, event_sink):
        self.seen.append(item["domain"])
        event_sink({"stage": "predict", "status": "started"})
        if item["domain"] == self.fail_domain:
            raise RuntimeError("stage failed")
        output = item["input_path"]
        return {"artifacts": [], "metrics": []}


def setup(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    agent = create_agent(db, user_id="local", name="A")
    model = create_model(db, user_id="local", name="M", provider="ollama", model_id="m")
    runs = tmp_path / "runs"
    for domain in ("older", "newer"):
        result = create_run(db, user_id="local", agent_id=agent["id"], model_id=model["id"],
                            items=[{"task": "cq2term", "domain": domain}], config={}, runs_root=runs)
        item = result["items"][0]
        source = runs / result["id"] / "items" / item["id"] / "input" / "p.json"
        source.write_text("[]", encoding="utf-8")
        with connect_database(db) as conn:
            conn.execute("UPDATE run_items SET input_path=? WHERE id=?", (str(source), item["id"]))
    return db, runs


def test_worker_waits_for_readiness_then_claims_fifo_once(tmp_path):
    db, runs = setup(tmp_path)
    ready, evaluator = Ready(False), Evaluator()
    worker = EvaluationWorker(db, runs, ready, evaluator, poll_interval=0.02)
    stop = threading.Event()
    thread = threading.Thread(target=worker.run_forever, args=(stop,), daemon=True)
    thread.start()
    time.sleep(0.08)
    assert evaluator.seen == []
    ready.ready = True
    deadline = time.time() + 2
    while len(evaluator.seen) < 2 and time.time() < deadline:
        time.sleep(0.02)
    stop.set()
    thread.join(2)
    assert evaluator.seen == ["older", "newer"]


def test_worker_persists_partial_completion_and_stage_order(tmp_path):
    db = tmp_path / "partial.sqlite3"
    initialize_database(db)
    runs = tmp_path / "partial_runs"
    agent = create_agent(db, user_id="local", name="A2")
    model = create_model(db, user_id="local", name="M2", provider="ollama", model_id="m")
    run = create_run(db, user_id="local", agent_id=agent["id"], model_id=model["id"],
                     items=[{"task": "cq2term", "domain": "older"}, {"task": "cq2term", "domain": "newer"}],
                     config={}, runs_root=runs)
    for item in run["items"]:
        source = runs / run["id"] / "items" / item["id"] / "input" / "p.json"
        source.write_text("[]", encoding="utf-8")
        with connect_database(db) as conn:
            conn.execute("UPDATE run_items SET input_path=? WHERE id=?", (str(source), item["id"]))
    evaluator = Evaluator(fail_domain="newer")
    worker = EvaluationWorker(db, runs, Ready(), evaluator)
    worker.process_one()
    result = get_run(db, user_id="local", run_id=run["id"])
    assert result["status"] == "partial"
    assert {item["domain"]: item["status"] for item in result["items"]} == {"older": "completed", "newer": "failed"}
    assert [stage["stage"] for stage in result["stages"]] == ["predict", "predict"]
    event_types = [event["event_type"] for event in result["events"]]
    assert event_types.count("stage") == 2
    assert event_types[-1] == "partial" and event_types.index("stage") < event_types.index("partial")


def test_worker_recovers_running_run_and_keeps_queued_run(tmp_path):
    db, runs = setup(tmp_path)
    with connect_database(db) as conn:
        conn.execute("UPDATE runs SET status='running' WHERE id=(SELECT id FROM runs ORDER BY created_at,id LIMIT 1)")
    worker = EvaluationWorker(db, runs, Ready(), Evaluator())
    worker.recover()
    with connect_database(db) as conn:
        events = conn.execute("SELECT event_type FROM run_events WHERE event_type='interrupted'").fetchall()
        states = [r[0] for r in conn.execute("SELECT status FROM runs ORDER BY created_at,id")]
    assert len(events) == 1 and states == ["failed", "queued"]
    evaluator = Evaluator()
    worker = EvaluationWorker(db, runs, Ready(), evaluator)
    assert worker.process_one() is True
    assert len(evaluator.seen) == 1


def test_indexed_outputs_stay_under_their_run_item_directory(tmp_path):
    db = tmp_path / "item-output.sqlite3"
    initialize_database(db)
    runs = tmp_path / "item-output-runs"
    agent = create_agent(db, user_id="local", name="A")
    model = create_model(db, user_id="local", agent_id=agent["id"], name="M", provider="ollama", model_id="m")
    run = create_run(db, user_id="local", agent_id=agent["id"], model_id=model["id"],
                     items=[{"task": "cq2term", "domain": "alpha"}], config={}, runs_root=runs)
    item = run["items"][0]
    input_path = runs / run["id"] / "items" / item["id"] / "input" / "prediction.json"
    input_path.write_text("[]", encoding="utf-8")
    with connect_database(db) as conn:
        conn.execute("UPDATE run_items SET input_path=? WHERE id=?", (str(input_path), item["id"]))

    class OutputEvaluator:
        def evaluate_item(self, run, item, event_sink):
            output = Path(run["run_path"]) / "items" / item["id"] / "results" / "result.txt"
            output.write_text("result", encoding="utf-8")
            return {"artifacts": [], "metrics": []}

    assert EvaluationWorker(db, runs, Ready(), OutputEvaluator()).process_one()
    result = get_run(db, user_id="local", run_id=run["id"])
    output_artifact = next(a for a in result["artifacts"] if a["category"] == "results")
    assert output_artifact["relative_path"].startswith(f"items/{item['id']}/results/")
    assert (runs / run["id"] / output_artifact["relative_path"]).read_text(encoding="utf-8") == "result"


def test_worker_shutdown_interrupts_active_stage_and_records_partial_log(tmp_path):
    import sys
    from web.services.evaluator import run_stage
    from web.types import EvaluationStage

    db, runs = setup(tmp_path)
    started = threading.Event()

    class SleepingEvaluator:
        stop_event = None

        def evaluate_item(self, run, item, event_sink):
            log = Path(run["run_path"]) / "items" / item["id"] / "logs"
            stage = EvaluationStage("sleep", [sys.executable, "-u", "-c",
                "import time; print('started', flush=True); time.sleep(60)"], tmp_path)

            def sink(event):
                if "started" in event.get("text", ""):
                    started.set()
                event_sink(event)

            run_stage(stage, log / "sleep.stdout.log", log / "sleep.stderr.log", sink,
                      stop_event=self.stop_event)

    worker = EvaluationWorker(db, runs, Ready(), SleepingEvaluator(), poll_interval=0.01)
    stop = threading.Event()
    thread = threading.Thread(target=worker.run_forever, args=(stop,))
    thread.start()
    try:
        assert started.wait(5)
        stop.set()
        thread.join(3)
        assert not thread.is_alive()
        with connect_database(db) as conn:
            row = conn.execute("SELECT id,status FROM runs WHERE status='failed'").fetchone()
        assert row is not None
        result = get_run(db, user_id="local", run_id=row["id"])
        assert any(event["event_type"] == "interrupted" for event in result["events"])
        assert any(artifact["name"] == "sleep.stdout.log" for artifact in result["artifacts"])
    finally:
        stop.set()
        thread.join(3)
