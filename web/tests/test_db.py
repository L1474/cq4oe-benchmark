import sqlite3
from uuid import uuid4

import pytest

from web.db import connect_database, initialize_database


def test_initialization_is_idempotent_and_enforces_run_item_constraints(tmp_path):
    path = tmp_path / "evaluator.sqlite3"
    initialize_database(path)
    initialize_database(path)

    with connect_database(path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {
            "users", "agents", "models", "runs", "run_items",
            "artifacts", "metrics", "run_events", "run_stages",
        }.issubset(tables)
        assert connection.execute("SELECT count(*) FROM users").fetchone()[0] == 1
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO run_items (id, run_id, user_id, task, domain) "
                "VALUES ('orphan', 'missing', 'local', 'cq2term', 'd')"
            )


def test_v4_migration_splits_legacy_model_shared_by_multiple_agents(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with connect_database(path) as connection:
        connection.executescript("""
            CREATE TABLE users(id TEXT PRIMARY KEY,name TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE agents(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',config_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL,
                UNIQUE(user_id,id));
            CREATE TABLE models(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,agent_id TEXT,name TEXT NOT NULL,
                provider TEXT NOT NULL,model_id TEXT NOT NULL,config_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL,
                UNIQUE(user_id,id));
            CREATE TABLE runs(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,agent_id TEXT NOT NULL,model_id TEXT NOT NULL,
                status TEXT NOT NULL,config_json TEXT NOT NULL,created_at TEXT NOT NULL,started_at TEXT,finished_at TEXT,
                run_path TEXT NOT NULL,evaluator_version TEXT NOT NULL DEFAULT 'unknown',gold_fingerprint TEXT NOT NULL DEFAULT '',
                UNIQUE(user_id,id));
            PRAGMA user_version=4;
        """)
        connection.execute("INSERT INTO users VALUES ('local','Local','now')")
        agents = [str(uuid4()), str(uuid4())]
        connection.executemany("INSERT INTO agents(id,user_id,name,created_at) VALUES (?,'local',?,'now')",
                               [(agents[0], "A"), (agents[1], "B")])
        model_id = str(uuid4())
        connection.execute("INSERT INTO models VALUES (?, 'local', NULL, 'Shared', 'ollama', 'm', '{}', 'now')", (model_id,))
        for agent_id in agents:
            connection.execute("INSERT INTO runs VALUES (?, 'local', ?, ?, 'completed', '{}', 'now', NULL, NULL, '/runs/x', 'v', '')",
                               (str(uuid4()), agent_id, model_id))
    initialize_database(path)
    with connect_database(path) as connection:
        models = connection.execute("SELECT id,agent_id FROM models WHERE user_id='local' ORDER BY agent_id").fetchall()
        mappings = connection.execute("SELECT agent_id,model_id FROM runs ORDER BY agent_id").fetchall()
        assert len(models) == len(mappings) == 2
        assert [(run["agent_id"], run["model_id"]) for run in mappings] == [
            (model["agent_id"], model["id"]) for model in models
        ]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
def test_run_items_are_unique_by_run_task_and_domain(tmp_path):
    from web.repositories import create_agent, create_model

    path = tmp_path / "evaluator.sqlite3"
    initialize_database(path)
    agent = create_agent(path, user_id="local", name="Agent")
    model = create_model(path, user_id="local", name="Model", provider="ollama", model_id="m")
    with connect_database(path) as connection:
        connection.execute(
            "INSERT INTO runs (id, user_id, agent_id, model_id, status, config_json, created_at, run_path) "
            "VALUES ('run-1', 'local', ?, ?, 'queued', '{}', '2026-01-01T00:00:00+00:00', 'run-1')",
            (agent["id"], model["id"]),
        )
        connection.execute(
                "INSERT INTO run_items (id, run_id, user_id, task, domain, status, created_at) "
                "VALUES ('item-1', 'run-1', 'local', 'cq2term', 'd', 'queued', '2026-01-01T00:00:00+00:00')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO run_items (id, run_id, user_id, task, domain, status, created_at) "
                "VALUES ('item-2', 'run-1', 'local', 'cq2term', 'd', 'queued', '2026-01-01T00:00:00+00:00')"
            )
