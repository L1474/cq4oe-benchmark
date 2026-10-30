import sqlite3

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
        assert tables == {
            "users", "agents", "models", "runs", "run_items",
            "artifacts", "metrics", "run_events",
        }
        assert connection.execute("SELECT count(*) FROM users").fetchone()[0] == 1
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO run_items (id, run_id, user_id, task, domain) "
                "VALUES ('orphan', 'missing', 'local', 'cq2term', 'd')"
            )


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
