import sqlite3

import pytest

from web.db import connect_database, initialize_database
from web.repositories import (
    add_event,
    create_agent,
    create_model,
    create_run,
    get_run,
    list_agents,
    list_runs,
    save_metrics,
    get_stage_states,
    save_stage_state,
)


def test_agents_and_models_are_user_scoped(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    agent = create_agent(db, user_id="local", name="Agent", description="desc")
    assert agent["name"] == "Agent"
    assert list_agents(db, user_id="other") == []
    model = create_model(db, user_id="local", name="local-model", provider="ollama", model_id="m")
    assert model["provider"] == "ollama"


def test_run_creation_items_events_and_metric_uniqueness(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    agent = create_agent(db, user_id="local", name="Agent")
    model = create_model(db, user_id="local", name="Model", provider="ollama", model_id="m")
    run = create_run(
        db, user_id="local", agent_id=agent["id"], model_id=model["id"],
        items=[{"task": "cq2term", "domain": "alpha"}, {"task": "cq2onto", "domain": "beta"}],
        config={"temperature": 0},
        runs_root=tmp_path / "runs",
    )
    assert run["status"] == "queued"
    assert len(run["items"]) == 2
    assert (tmp_path / "runs" / run["id"] / "items" / run["items"][0]["id"] / "input").is_dir()
    add_event(db, user_id="local", run_id=run["id"], event_type="started", payload={"x": 1})
    events = get_run(db, user_id="local", run_id=run["id"])["events"]
    assert [event["event_type"] for event in events] == ["queued", "started"]
    assert list_runs(db, user_id="other") == []
    metric = {"run_item_id": run["items"][0]["id"], "dimension": "f1", "layer": "term", "metric_name": "score", "scope": "all", "value": 0.5}
    save_metrics(db, user_id="local", run_id=run["id"], metrics=[metric])
    with pytest.raises(sqlite3.IntegrityError):
        save_metrics(db, user_id="local", run_id=run["id"], metrics=[metric])


def test_create_run_rejects_foreign_owner(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    agent = create_agent(db, user_id="local", name="Agent")
    model = create_model(db, user_id="local", name="Model", provider="ollama", model_id="m")
    with pytest.raises(sqlite3.IntegrityError):
        create_run(db, user_id="other", agent_id=agent["id"], model_id=model["id"], items=[], config={}, runs_root=tmp_path / "runs")


def test_artifacts_and_metrics_cannot_pair_item_with_another_run(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    agent = create_agent(db, user_id="local", name="Agent")
    model = create_model(db, user_id="local", name="Model", provider="ollama", model_id="m")
    first = create_run(db, user_id="local", agent_id=agent["id"], model_id=model["id"], items=[{"task": "cq2term", "domain": "a"}], config={}, runs_root=tmp_path / "runs")
    second = create_run(db, user_id="local", agent_id=agent["id"], model_id=model["id"], items=[], config={}, runs_root=tmp_path / "runs")
    item_id = first["items"][0]["id"]
    with pytest.raises(sqlite3.IntegrityError):
        save_metrics(db, user_id="local", run_id=second["id"], metrics=[{
            "run_item_id": item_id, "dimension": "f1", "layer": "term", "metric_name": "score", "scope": "all", "value": 0.5,
        }])
    with pytest.raises(sqlite3.IntegrityError):
        from web.repositories import add_artifact
        add_artifact(db, user_id="local", run_id=second["id"], run_item_id=item_id, category="results",
                     relative_path="result.json", media_type="application/json", size_bytes=1, sha256="x", name="result.json")


def test_run_filesystem_failure_leaves_no_database_rows_or_partial_workspace(tmp_path, monkeypatch):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    agent = create_agent(db, user_id="local", name="Agent")
    model = create_model(db, user_id="local", name="Model", provider="ollama", model_id="m")
    original_mkdir = __import__("pathlib").Path.mkdir

    def fail_work_directory(path, *args, **kwargs):
        if path.name == "work" and "items" in path.parts:
            raise OSError("simulated mkdir failure")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr("pathlib.Path.mkdir", fail_work_directory)
    with pytest.raises(OSError, match="simulated mkdir failure"):
        create_run(db, user_id="local", agent_id=agent["id"], model_id=model["id"],
                   items=[{"task": "cq2term", "domain": "a"}], config={}, runs_root=tmp_path / "runs")
    monkeypatch.setattr("pathlib.Path.mkdir", original_mkdir)
    assert list_runs(db, user_id="local") == []
    assert not list((tmp_path / "runs").glob("*")) if (tmp_path / "runs").exists() else True


def test_run_provenance_and_stage_state_round_trip(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    agent = create_agent(db, user_id="local", name="Agent")
    model = create_model(db, user_id="local", name="Model", provider="ollama", model_id="m")
    run = create_run(db, user_id="local", agent_id=agent["id"], model_id=model["id"], items=[{"task": "cq2term", "domain": "a"}], config={}, runs_root=tmp_path / "runs", evaluator_version="2.1.0", gold_fingerprint="abc123")
    assert run["evaluator_version"] == "2.1.0"
    assert run["gold_fingerprint"] == "abc123"
    persisted = get_run(db, user_id="local", run_id=run["id"])
    assert persisted["evaluator_version"] == "2.1.0"
    assert persisted["gold_fingerprint"] == "abc123"
    save_stage_state(db, user_id="local", run_id=run["id"], run_item_id=run["items"][0]["id"], stage="predict", status="completed", state={"artifact_id": "a1"})
    assert get_stage_states(db, user_id="local", run_id=run["id"], run_item_id=run["items"][0]["id"]) == [{
        "run_id": run["id"], "run_item_id": run["items"][0]["id"], "stage": "predict", "status": "completed", "state_json": '{"artifact_id": "a1"}',
    }]
