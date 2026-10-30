import sqlite3
from pathlib import Path


SCHEMA_VERSION = 1


def connect_database(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path, timeout=30, isolation_level="DEFERRED")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


_SCHEMA = """
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    config_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(user_id, id)
);
CREATE TABLE models (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_id TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(user_id, id)
);
CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    agent_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    status TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    run_path TEXT NOT NULL,
    UNIQUE(user_id, id),
    FOREIGN KEY(user_id, agent_id) REFERENCES agents(user_id, id),
    FOREIGN KEY(user_id, model_id) REFERENCES models(user_id, id)
);
CREATE TABLE run_items (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id),
    task TEXT NOT NULL,
    domain TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    UNIQUE(run_id, task, domain),
    UNIQUE(user_id, id),
    FOREIGN KEY(user_id, run_id) REFERENCES runs(user_id, id)
);
CREATE TABLE artifacts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    run_id TEXT NOT NULL,
    run_item_id TEXT,
    category TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    media_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id, run_id) REFERENCES runs(user_id, id),
    FOREIGN KEY(user_id, run_item_id) REFERENCES run_items(user_id, id)
);
CREATE TABLE metrics (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    run_id TEXT NOT NULL,
    run_item_id TEXT NOT NULL,
    dimension TEXT NOT NULL,
    layer TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    scope TEXT NOT NULL,
    value REAL,
    count INTEGER,
    unit TEXT,
    scope_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(run_item_id, dimension, layer, metric_name, scope),
    FOREIGN KEY(user_id, run_id) REFERENCES runs(user_id, id),
    FOREIGN KEY(user_id, run_item_id) REFERENCES run_items(user_id, id)
);
CREATE TABLE run_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    run_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id, run_id) REFERENCES runs(user_id, id)
);
CREATE INDEX idx_agents_user ON agents(user_id, created_at);
CREATE INDEX idx_runs_user ON runs(user_id, created_at DESC);
CREATE INDEX idx_run_items_run ON run_items(run_id, created_at);
CREATE INDEX idx_events_run ON run_events(run_id, created_at, id);
"""


def initialize_database(db_path: Path) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect_database(db_path)
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError(f"database version {version} is newer than supported {SCHEMA_VERSION}")
        if version == 0:
            connection.executescript("BEGIN;\n" + _SCHEMA + "\nPRAGMA user_version = 1;\nCOMMIT;")
        connection.execute(
            "INSERT OR IGNORE INTO users (id, name, created_at) VALUES (?, ?, ?)",
            ("local", "Local User", "1970-01-01T00:00:00+00:00"),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
