import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from web.db import connect_database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dict(row: sqlite3.Row) -> dict:
    return dict(row)


def create_agent(db_path: Path, *, user_id: str, name: str, description: str = "", config: dict | None = None) -> dict:
    result = {"id": str(uuid4()), "user_id": user_id, "name": name, "description": description,
              "config_json": json.dumps(config or {}, sort_keys=True), "created_at": _now()}
    with connect_database(db_path) as connection:
        connection.execute("INSERT INTO agents VALUES (:id, :user_id, :name, :description, :config_json, :created_at)", result)
    return result


def list_agents(db_path: Path, *, user_id: str) -> list[dict]:
    with connect_database(db_path) as connection:
        return [_dict(row) for row in connection.execute("SELECT * FROM agents WHERE user_id = ? ORDER BY created_at, id", (user_id,))]


def create_model(db_path: Path, *, user_id: str, name: str, provider: str, model_id: str, config: dict | None = None) -> dict:
    result = {"id": str(uuid4()), "user_id": user_id, "name": name, "provider": provider,
              "model_id": model_id, "config_json": json.dumps(config or {}, sort_keys=True), "created_at": _now()}
    with connect_database(db_path) as connection:
        connection.execute("INSERT INTO models VALUES (:id, :user_id, :name, :provider, :model_id, :config_json, :created_at)", result)
    return result


def create_run(db_path: Path, *, user_id: str, agent_id: str, model_id: str, items: list[dict],
               config: dict, runs_root: Path, evaluator_version: str = "unknown",
               gold_fingerprint: str = "") -> dict:
    run_id = str(uuid4())
    run_path = Path(runs_root) / run_id
    created_at = _now()
    run = {"id": run_id, "user_id": user_id, "agent_id": agent_id, "model_id": model_id,
           "status": "queued", "config_json": json.dumps(config, sort_keys=True), "created_at": created_at,
           "started_at": None, "finished_at": None, "run_path": str(run_path),
           "evaluator_version": evaluator_version, "gold_fingerprint": gold_fingerprint}
    records = []
    for item in items:
        item_id = str(uuid4())
        records.append({"id": item_id, "run_id": run_id, "user_id": user_id, "task": item["task"],
                        "domain": item["domain"], "status": "queued", "created_at": created_at,
                        "started_at": None, "finished_at": None})
    try:
        for directory in (run_path, run_path / "items"):
            directory.mkdir(parents=True, exist_ok=True)
        for item in records:
            for category in ("input", "work", "results", "logs"):
                (run_path / "items" / item["id"] / category).mkdir(parents=True, exist_ok=True)
        with connect_database(db_path) as connection:
            connection.execute("INSERT INTO runs (id, user_id, agent_id, model_id, status, config_json, created_at, started_at, finished_at, run_path, evaluator_version, gold_fingerprint) VALUES (:id, :user_id, :agent_id, :model_id, :status, :config_json, :created_at, :started_at, :finished_at, :run_path, :evaluator_version, :gold_fingerprint)", run)
            connection.executemany("INSERT INTO run_items VALUES (:id, :run_id, :user_id, :task, :domain, :status, :created_at, :started_at, :finished_at)", records)
            connection.execute("INSERT INTO run_events (id, user_id, run_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                               (str(uuid4()), user_id, run_id, "queued", "{}", created_at))
    except BaseException:
        shutil.rmtree(run_path, ignore_errors=True)
        raise
    run["items"] = records
    run["events"] = [{"event_type": "queued", "payload_json": "{}", "created_at": created_at}]
    return run


def get_run(db_path: Path, *, user_id: str, run_id: str) -> dict | None:
    with connect_database(db_path) as connection:
        row = connection.execute("SELECT * FROM runs WHERE user_id = ? AND id = ?", (user_id, run_id)).fetchone()
        if row is None:
            return None
        result = _dict(row)
        result["items"] = [_dict(item) for item in connection.execute("SELECT * FROM run_items WHERE user_id = ? AND run_id = ? ORDER BY created_at, id", (user_id, run_id))]
        result["events"] = [_dict(event) for event in connection.execute("SELECT * FROM run_events WHERE user_id = ? AND run_id = ? ORDER BY rowid", (user_id, run_id))]
        result["artifacts"] = [_dict(item) for item in connection.execute("SELECT * FROM artifacts WHERE user_id = ? AND run_id = ? ORDER BY created_at, id", (user_id, run_id))]
        result["metrics"] = [_dict(item) for item in connection.execute("SELECT * FROM metrics WHERE user_id = ? AND run_id = ? ORDER BY created_at, id", (user_id, run_id))]
        result["stages"] = [_dict(item) for item in connection.execute("SELECT run_id, run_item_id, stage, status, state_json, updated_at FROM run_stages WHERE user_id = ? AND run_id = ? ORDER BY run_item_id, stage", (user_id, run_id))]
        return result


def list_runs(db_path: Path, *, user_id: str) -> list[dict]:
    with connect_database(db_path) as connection:
        return [_dict(row) for row in connection.execute("SELECT * FROM runs WHERE user_id = ? ORDER BY created_at DESC, id", (user_id,))]


def add_event(db_path: Path, *, user_id: str, run_id: str, event_type: str, payload: dict | None = None) -> dict:
    event = {"id": str(uuid4()), "user_id": user_id, "run_id": run_id, "event_type": event_type,
             "payload_json": json.dumps(payload or {}, sort_keys=True), "created_at": _now()}
    with connect_database(db_path) as connection:
        connection.execute("INSERT INTO run_events VALUES (:id, :user_id, :run_id, :event_type, :payload_json, :created_at)", event)
    return event


def save_metrics(db_path: Path, *, user_id: str, run_id: str, metrics: list[dict]) -> list[dict]:
    created = []
    with connect_database(db_path) as connection:
        for metric in metrics:
            row = {"id": str(uuid4()), "user_id": user_id, "run_id": run_id,
                   "run_item_id": metric["run_item_id"], "dimension": metric["dimension"],
                   "layer": metric["layer"], "metric_name": metric["metric_name"], "scope": metric["scope"],
                   "value": metric.get("value"), "count": metric.get("count"), "unit": metric.get("unit"),
                   "scope_json": json.dumps(metric["scope_json"], sort_keys=True) if metric.get("scope_json") is not None else None,
                   "created_at": _now()}
            connection.execute("INSERT INTO metrics VALUES (:id, :user_id, :run_id, :run_item_id, :dimension, :layer, :metric_name, :scope, :value, :count, :unit, :scope_json, :created_at)", row)
            created.append(row)
    return created


def add_artifact(db_path: Path, *, user_id: str, run_id: str, run_item_id: str | None,
                 category: str, relative_path: str, media_type: str, size_bytes: int,
                 sha256: str, name: str) -> dict:
    record = {"id": str(uuid4()), "user_id": user_id, "run_id": run_id, "run_item_id": run_item_id,
              "category": category, "relative_path": relative_path, "media_type": media_type,
              "size_bytes": size_bytes, "sha256": sha256, "name": name, "created_at": _now()}
    with connect_database(db_path) as connection:
        connection.execute("INSERT INTO artifacts VALUES (:id, :user_id, :run_id, :run_item_id, :category, :relative_path, :media_type, :size_bytes, :sha256, :name, :created_at)", record)
    return record


def resolve_artifact_path(run_root: Path, artifact: dict) -> Path:
    candidate = (Path(run_root) / artifact["relative_path"]).resolve()
    if not candidate.is_relative_to(Path(run_root).resolve()):
        raise ValueError("artifact path escapes run root")
    return candidate


def save_stage_state(db_path: Path, *, user_id: str, run_id: str, run_item_id: str,
                     stage: str, status: str, state: dict | None = None) -> dict:
    record = {"id": str(uuid4()), "user_id": user_id, "run_id": run_id,
              "run_item_id": run_item_id, "stage": stage, "status": status,
              "state_json": json.dumps(state or {}, sort_keys=True), "updated_at": _now()}
    with connect_database(db_path) as connection:
        connection.execute(
            "INSERT INTO run_stages (id, user_id, run_id, run_item_id, stage, status, state_json, updated_at) "
            "VALUES (:id, :user_id, :run_id, :run_item_id, :stage, :status, :state_json, :updated_at) "
            "ON CONFLICT(run_item_id, stage) DO UPDATE SET status=excluded.status, "
            "state_json=excluded.state_json, updated_at=excluded.updated_at",
            record,
        )
    return {key: record[key] for key in ("run_id", "run_item_id", "stage", "status", "state_json", "updated_at")}


def get_stage_states(db_path: Path, *, user_id: str, run_id: str,
                     run_item_id: str | None = None) -> list[dict]:
    query = "SELECT run_id, run_item_id, stage, status, state_json FROM run_stages WHERE user_id = ? AND run_id = ?"
    params: tuple = (user_id, run_id)
    if run_item_id is not None:
        query += " AND run_item_id = ?"
        params += (run_item_id,)
    query += " ORDER BY run_item_id, stage"
    with connect_database(db_path) as connection:
        return [_dict(row) for row in connection.execute(query, params)]
