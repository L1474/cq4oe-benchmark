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
