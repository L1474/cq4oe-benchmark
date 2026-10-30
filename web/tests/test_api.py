import json
import threading
import time
import zipfile
from io import BytesIO

from fastapi.testclient import TestClient

from web.config import Settings
from web.app import create_app
from web.db import connect_database
from web.repositories import add_artifact
from web.services.evaluator import EvaluationStageError
from web.services.worker import EvaluationWorker


class FakeWorker:
    def run_forever(self, stop):
        stop.wait()


def make_client(tmp_path):
    project = tmp_path / "project"
    for task, cqname, contents in [
        ("CQ2Term", "alpha_cq2term_cqs.json", '[{"id":"C1","value":"one?"}]'),
        ("CQ2Onto", "alpha_cq2onto_cqs.json", '[{"id":"O1","value":"onto?"}]'),
    ]:
        folder = project / task / "competency_question"
        folder.mkdir(parents=True)
        (folder / cqname).write_text(contents, encoding="utf-8")
    gold_term = project / "CQ2Term" / "00_gold_standard" / "alpha"
    gold_term.mkdir(parents=True)
    (gold_term / "cq_to_terms_alpha.json").write_text('[{"id":"C1"}]', encoding="utf-8")
    gold_onto = project / "CQ2Onto" / "00_gold_standard" / "alpha"
    (gold_onto / "ontology").mkdir(parents=True)
    (gold_onto / "axioms").mkdir()
    (gold_onto / "ontology" / "sub_alpha.owl").write_text('<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"/>', encoding="utf-8")
    (gold_onto / "axioms" / "alpha_axiom_gold.json").write_text('{"axioms":[]}', encoding="utf-8")
    app = create_app(Settings(project, tmp_path / "data"), lambda settings, readiness: FakeWorker())
    return TestClient(app), app


def test_app_construction_does_not_create_runtime_data(tmp_path):
    project = tmp_path / "project"
    data = tmp_path / "runtime"
    app = create_app(Settings(project, data), lambda settings, readiness: FakeWorker())
    assert app is not None
    assert not data.exists()


def test_catalog_bundle_and_agent_model_routes(tmp_path):
    client, _ = make_client(tmp_path)
    with client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/api/catalog").status_code == 200
        detail = client.get("/api/catalog/cq2term/alpha")
        assert detail.json()["cqs"][0]["id"] == "C1"
        bundle = client.get("/api/catalog/cq2term/alpha/bundle")
        assert bundle.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(BytesIO(bundle.content)) as archive:
            assert "manifest.json" in archive.namelist()
        agent = client.post("/api/agents", json={"name": "Agent"}).json()
        model = client.post(f"/api/agents/{agent['id']}/models", json={"name": "Local", "model_id": "qwen"})
        assert model.status_code == 201
        assert client.get(f"/api/agents/{agent['id']}/models").json()[0]["model_id"] == "qwen"
        other = client.post("/api/agents", json={"name": "Other"}).json()
        other_model = client.post(f"/api/agents/{other['id']}/models", json={"name": "Other model", "model_id": "other"}).json()
        assert [row["id"] for row in client.get(f"/api/agents/{agent['id']}/models").json()] == [model.json()["id"]]
        assert other_model["agent_id"] == other["id"]
        assert client.patch(f"/api/agents/{agent['id']}", json={"name": "Renamed"}).status_code == 200


def test_run_upload_start_and_artifacts_are_index_restricted(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        agent = client.post("/api/agents", json={"name": "Agent"}).json()
        model = client.post(f"/api/agents/{agent['id']}/models", json={"name": "Local", "model_id": "qwen"}).json()
        body = {"agent_id": agent["id"], "model_id": model["id"], "items": [{"task": "cq2term", "domain": "alpha"}], "config": {}}
        run = client.post("/api/runs", json=body).json()
        assert "run_path" not in run and "input_path" not in run["items"][0]
        item_id = run["items"][0]["id"]
        assert run["status"] == "draft"
        assert client.post(f"/api/runs/{run['id']}/start").status_code == 400
        prediction = json.dumps([{"id": "C1", "class": [], "property": []}]).encode()
        uploaded = client.post(f"/api/runs/{run['id']}/items/{item_id}/upload", files={"file": ("prediction.json", prediction)})
        assert uploaded.status_code == 201
        assert client.post(f"/api/runs/{run['id']}/start").status_code == 200
        artifact = uploaded.json()
        assert client.get(f"/api/artifacts/{artifact['id']}").content == prediction
        with connect_database(app.state.settings.database_path) as conn:
            record = conn.execute("SELECT * FROM artifacts WHERE id=?", (artifact["id"],)).fetchone()
        evil = add_artifact(app.state.settings.database_path, user_id="local", run_id=run["id"],
                             run_item_id=item_id, category="results", relative_path="../../secret.txt",
                             media_type="text/plain", size_bytes=4, sha256="x", name="secret.txt")
        assert client.get(f"/api/artifacts/{evil['id']}").status_code == 404


def test_upload_errors_are_json_and_run_events_are_available(tmp_path):
    client, _ = make_client(tmp_path)
    with client:
        agent = client.post("/api/agents", json={"name": "Agent"}).json()
        model = client.post(f"/api/agents/{agent['id']}/models", json={"name": "Local", "model_id": "qwen"}).json()
        run = client.post("/api/runs", json={"agent_id": agent["id"], "model_id": model["id"], "items": [{"task": "cq2term", "domain": "alpha"}]}).json()
        item_id = run["items"][0]["id"]
        response = client.post(f"/api/runs/{run['id']}/items/{item_id}/upload", files={"file": ("bad.txt", b"bad")})
        assert response.status_code == 400 and response.json()["detail"]
        assert client.get(f"/api/runs/{run['id']}/events").status_code == 200


def test_failure_events_do_not_expose_workspace_paths(tmp_path):
    client, app = make_client(tmp_path)
    with client:
        agent = client.post("/api/agents", json={"name": "Agent"}).json()
        model = client.post(f"/api/agents/{agent['id']}/models", json={"name": "Local", "model_id": "qwen"}).json()
        run = client.post("/api/runs", json={"agent_id": agent["id"], "model_id": model["id"],
                                             "items": [{"task": "cq2term", "domain": "alpha"}]}).json()
        item_id = run["items"][0]["id"]
        prediction = json.dumps([{"id": "C1", "class": [], "property": []}]).encode()
        client.post(f"/api/runs/{run['id']}/items/{item_id}/upload", files={"file": ("prediction.json", prediction)})
        client.post(f"/api/runs/{run['id']}/start")

        class FailingEvaluator:
            def evaluate_item(self, run, item, event_sink):
                raise EvaluationStageError("predict", 1, tmp_path / "private" / "stdout.log", tmp_path / "private" / "stderr.log")

        class Ready:
            def is_ready(self):
                return True

        worker = EvaluationWorker(app.state.settings.database_path, app.state.settings.runs_root, Ready(), FailingEvaluator())
        assert worker.process_one()
        events = client.get(f"/api/runs/{run['id']}/events").json()
        assert str(tmp_path) not in json.dumps(events)
        assert all("stdout.log" not in event["payload_json"] for event in events)
