import io
import json

import pytest
from web.db import initialize_database
from web.repositories import create_agent, create_model, get_run
from web.services.run_service import RunService, RunServiceError


def setup_service(tmp_path):
    project = tmp_path / "project"
    cq_dir = project / "CQ2Term" / "competency_question"
    cq_dir.mkdir(parents=True)
    (cq_dir / "alpha_cq2term_cqs.json").write_text(
        '[{"id":"CQ1","value":"One?"},{"id":"CQ2","value":"Two?"}]', encoding="utf-8"
    )
    onto_dir = project / "CQ2Onto" / "competency_question"
    onto_dir.mkdir(parents=True)
    (onto_dir / "alpha_cq2onto_cqs.json").write_text(
        '[{"id":"OCQ1","value":"Ontology?"}]', encoding="utf-8"
    )
    db = tmp_path / "app.sqlite3"
    initialize_database(db)
    agent = create_agent(db, user_id="local", name="Agent")
    model = create_model(db, user_id="local", name="Model", provider="ollama", model_id="m")
    service = RunService(db, tmp_path / "runs", project, max_upload_bytes=1024)
    return service, db, agent, model, tmp_path / "runs"


def upload(name, body):
    class Upload:
        filename = name
        file = io.BytesIO(body)

    return Upload()


def test_run_stays_draft_until_valid_upload_and_start(tmp_path):
    service, db, agent, model, _ = setup_service(tmp_path)
    run_id = service.create_draft_run("local", agent["id"], model["id"], [{"task": "cq2term", "domain": "alpha"}], {})
    item = get_run(db, user_id="local", run_id=run_id)["items"][0]
    with pytest.raises(RunServiceError, match="upload"):
        service.start_run(run_id)
    service.save_item_upload(run_id, item["id"], upload("prediction.json", json.dumps([
        {"id": "CQ1", "class": [], "property": []}, {"id": "CQ2", "class": [], "property": []}
    ]).encode()))
    service.start_run(run_id)
    assert get_run(db, user_id="local", run_id=run_id)["status"] == "queued"


@pytest.mark.parametrize("content", [b"{bad", b"[]"])
def test_malformed_or_incomplete_cq2term_upload_cannot_start(tmp_path, content):
    service, db, agent, model, _ = setup_service(tmp_path)
    run_id = service.create_draft_run("local", agent["id"], model["id"], [{"task": "cq2term", "domain": "alpha"}], {})
    item = get_run(db, user_id="local", run_id=run_id)["items"][0]
    with pytest.raises(RunServiceError, match="valid"):
        service.save_item_upload(run_id, item["id"], upload("prediction.json", content))


def test_cq2onto_requires_complete_confirmation_and_upload(tmp_path):
    service, db, agent, model, _ = setup_service(tmp_path)
    run_id = service.create_draft_run("local", agent["id"], model["id"], [{"task": "cq2onto", "domain": "alpha"}], {})
    item = get_run(db, user_id="local", run_id=run_id)["items"][0]
    service.save_item_upload(run_id, item["id"], upload("model.owl", b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"/>'))
    with pytest.raises(RunServiceError, match="confirmation"):
        service.set_confirmation(run_id, item["id"], ["wrong-id"])
    with pytest.raises(RunServiceError, match="confirmation"):
        service.start_run(run_id)
    service.set_confirmation(run_id, item["id"], ["OCQ1"])
    service.start_run(run_id)
    stored = get_run(db, user_id="local", run_id=run_id)["items"][0]
    assert json.loads(stored["confirmation_json"]) == ["OCQ1"]
    assert len(stored["bundle_sha256"]) == 64


def test_multi_item_run_requires_every_upload_and_snapshots_are_isolated(tmp_path):
    service, db, agent, model, runs_root = setup_service(tmp_path)
    items = [{"task": "cq2term", "domain": "alpha"}, {"task": "cq2onto", "domain": "alpha"}]
    first = service.create_draft_run("local", agent["id"], model["id"], items, {})
    second = service.create_draft_run("local", agent["id"], model["id"], items, {})
    one = next(item for item in get_run(db, user_id="local", run_id=first)["items"] if item["task"] == "cq2term")
    two = next(item for item in get_run(db, user_id="local", run_id=second)["items"] if item["task"] == "cq2term")
    body = json.dumps([{"id": "CQ1", "class": [], "property": []}, {"id": "CQ2", "class": [], "property": []}]).encode()
    service.save_item_upload(first, one["id"], upload("same.json", body))
    with pytest.raises(RunServiceError, match="upload"):
        service.start_run(first)
    service.save_item_upload(second, two["id"], upload("same.json", body))
    path1 = runs_root / first / "items" / one["id"] / "input"
    path2 = runs_root / second / "items" / two["id"] / "input"
    file1, file2 = next(path1.iterdir()), next(path2.iterdir())
    assert file1 != file2 and file1.read_bytes() == file2.read_bytes() == body


def test_upload_rejects_unsafe_name_and_oversize(tmp_path):
    service, db, agent, model, _ = setup_service(tmp_path)
    run_id = service.create_draft_run("local", agent["id"], model["id"], [{"task": "cq2term", "domain": "alpha"}], {})
    item = get_run(db, user_id="local", run_id=run_id)["items"][0]
    with pytest.raises(RunServiceError, match="filename"):
        service.save_item_upload(run_id, item["id"], upload("../bad.json", b"{}"))
    with pytest.raises(RunServiceError, match="size"):
        service.save_item_upload(run_id, item["id"], upload("ok.json", b"x" * 1025))
