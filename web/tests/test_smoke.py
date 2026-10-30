import json
import sqlite3
import time
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from web.app import create_app
from web.config import Settings, settings_from_environment
from web.services.worker import EvaluationWorker


class ReadyModel:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        pass

    def stop(self, timeout=None):
        pass

    def is_ready(self):
        return True


class FakeEvaluator:
    def evaluate_item(self, run, item, event_sink):
        root = Path(run["run_path"]) / "items" / item["id"] / "results"
        root.mkdir(parents=True, exist_ok=True)
        (root / "report.md").write_text(f"# {item['task']} report\n\nCompleted {item['domain']}.", encoding="utf-8")
        (root / "metrics.csv").write_text("metric,value\nf1,0.75\n", encoding="utf-8")
        event_sink({"stage": "evaluate", "status": "completed"})
        return {"artifacts": [], "metrics": [{
            "dimension": "term" if item["task"] == "cq2term" else "class",
            "layer": "aggregate", "metric_name": "f1", "scope": "global",
            "value": 0.75, "unit": "ratio",
        }]}


def make_project(tmp_path):
    project = tmp_path / "project"
    for task, filename, cq_id in (
        ("CQ2Term", "alpha_cq2term_cqs.json", "T1"),
        ("CQ2Onto", "alpha_cq2onto_cqs.json", "O1"),
    ):
        folder = project / task / "competency_question"
        folder.mkdir(parents=True)
        (folder / filename).write_text(json.dumps([{"id": cq_id, "value": "What is alpha?"}]), encoding="utf-8")
    term_gold = project / "CQ2Term" / "00_gold_standard" / "alpha"
    term_gold.mkdir(parents=True)
    (term_gold / "cq_to_terms_alpha.json").write_text('[{"id":"T1"}]', encoding="utf-8")
    onto_gold = project / "CQ2Onto" / "00_gold_standard" / "alpha"
    (onto_gold / "ontology").mkdir(parents=True)
    (onto_gold / "axioms").mkdir()
    (onto_gold / "ontology" / "sub_alpha.owl").write_text(
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"/>', encoding="utf-8")
    (onto_gold / "axioms" / "alpha_axiom_gold.json").write_text('{"axioms":[]}', encoding="utf-8")
    return project


def test_full_run_and_outputs_survive_app_restart(tmp_path, monkeypatch):
    monkeypatch.setattr("web.app.ModelReadinessService", ReadyModel)
    project = make_project(tmp_path)
    settings = Settings(project, tmp_path / "data", worker_poll_interval=0.01)

    def worker_factory(settings, readiness):
        return EvaluationWorker(settings.database_path, settings.runs_root, readiness,
                                evaluator=FakeEvaluator(), poll_interval=0.01)

    with TestClient(create_app(settings, worker_factory)) as client:
        assert client.get("/health").json()["embedding"] == "ready"
        agent = client.post("/api/agents", json={"name": "Smoke Agent"}).json()
        model = client.post(f"/api/agents/{agent['id']}/models",
                            json={"name": "Smoke Model", "model_id": "local"}).json()
        for task, expected_id in (("cq2term", "T1"), ("cq2onto", "O1")):
            bundle = client.get(f"/api/catalog/{task}/alpha/bundle")
            assert bundle.status_code == 200
            with zipfile.ZipFile(BytesIO(bundle.content)) as archive:
                assert json.loads(archive.read("manifest.json"))["expected_cq_ids"] == [expected_id]

        created = client.post("/api/runs", json={"agent_id": agent["id"], "model_id": model["id"],
                                                  "items": [{"task": "cq2term", "domain": "alpha"},
                                                            {"task": "cq2onto", "domain": "alpha"}]}).json()
        run_id = created["id"]
        items = {item["task"]: item for item in created["items"]}
        term = json.dumps([{"id": "T1", "class": [], "property": []}]).encode()
        onto = b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"/>'
        for task, filename, content in (("cq2term", "prediction.json", term), ("cq2onto", "model.owl", onto)):
            response = client.post(f"/api/runs/{run_id}/items/{items[task]['id']}/upload",
                                   files={"file": (filename, content)})
            assert response.status_code == 201, response.text
        confirmation = client.put(f"/api/runs/{run_id}/items/{items['cq2onto']['id']}/confirmation",
                                  json={"confirmed_ids": ["O1"]})
        assert confirmation.status_code == 200, confirmation.text
        started = client.post(f"/api/runs/{run_id}/start")
        assert started.status_code == 200, started.text
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            detail = client.get(f"/api/runs/{run_id}").json()
            if detail["status"] in {"completed", "partial", "failed"}:
                break
            time.sleep(0.02)
        assert detail["status"] == "completed", detail
        assert len(detail["metrics"]) == 2
        assert len([artifact for artifact in detail["artifacts"] if artifact["name"] == "report.md"]) == 2
        for artifact in detail["artifacts"]:
            assert client.get(f"/api/artifacts/{artifact['id']}").status_code == 200
        assert "cq2onto report" in client.get(f"/runs/{run_id}").text

    assert settings.database_path.is_file()
    with TestClient(create_app(settings, worker_factory)) as client:
        assert any(row["id"] == agent["id"] for row in client.get("/api/agents").json())
        detail = client.get(f"/api/runs/{run_id}").json()
        assert detail["status"] == "completed" and len(detail["metrics"]) == 2
        assert all(client.get(f"/api/artifacts/{a['id']}").status_code == 200 for a in detail["artifacts"])
        assert client.get("/records").status_code == 200
        assert client.get("/domains/alpha").status_code == 200
        assert client.get("/compare").status_code == 200


def test_environment_settings_use_persistent_data_and_ollama_url(tmp_path, monkeypatch):
    monkeypatch.setenv("CQ4OE_DATA_DIR", str(tmp_path / "persisted"))
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    settings = settings_from_environment(tmp_path / "project")
    assert settings.database_path == tmp_path / "persisted" / "evaluator.sqlite3"
    assert settings.runs_root == tmp_path / "persisted" / "runs"
    assert settings.ollama_url == "http://ollama:11434"


def test_health_reports_database_failure_separately_from_model(tmp_path, monkeypatch):
    monkeypatch.setattr("web.app.ModelReadinessService", ReadyModel)
    settings = Settings(make_project(tmp_path), tmp_path / "data")

    class IdleWorker:
        def run_forever(self, stop):
            stop.wait()

    with TestClient(create_app(settings, lambda *_: IdleWorker())) as client:
        assert client.get("/health").json() == {"status": "ok", "database": "ok", "embedding": "ready"}
        assert client.get("/api/health").json() == {"status": "ok", "database": "ok", "embedding": "ready"}
        object.__setattr__(settings, "database_path", tmp_path / "missing" / "evaluator.sqlite3")
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"status": "unhealthy", "database": "unavailable", "embedding": "ready"}
        assert client.get("/api/health").status_code == 503
        empty_database = tmp_path / "empty.sqlite3"
        sqlite3.connect(empty_database).close()
        object.__setattr__(settings, "database_path", empty_database)
        assert client.get("/health").status_code == 503


def test_health_keeps_pages_available_during_model_startup(tmp_path, monkeypatch):
    class StartingModel(ReadyModel):
        def is_ready(self):
            return False

    class IdleWorker:
        def run_forever(self, stop):
            stop.wait()

    monkeypatch.setattr("web.app.ModelReadinessService", StartingModel)
    settings = Settings(make_project(tmp_path), tmp_path / "data")
    with TestClient(create_app(settings, lambda *_: IdleWorker())) as client:
        assert client.get("/health").json() == {"status": "ok", "database": "ok", "embedding": "starting"}
        assert client.get("/runs/new").status_code == 200
