import sqlite3
from pathlib import Path


SCHEMA_VERSION = 5


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
    agent_id TEXT NOT NULL,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_id TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(user_id, id)
    ,UNIQUE(user_id, agent_id, id)
    ,FOREIGN KEY(user_id, agent_id) REFERENCES agents(user_id, id)
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
    evaluator_version TEXT NOT NULL DEFAULT 'unknown',
    gold_fingerprint TEXT NOT NULL DEFAULT '',
    UNIQUE(user_id, id),
    FOREIGN KEY(user_id, agent_id) REFERENCES agents(user_id, id),
    FOREIGN KEY(user_id, model_id) REFERENCES models(user_id, id),
    FOREIGN KEY(user_id, agent_id, model_id) REFERENCES models(user_id, agent_id, id)
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
    input_path TEXT,
    confirmation_json TEXT,
    bundle_sha256 TEXT,
    UNIQUE(run_id, task, domain),
    UNIQUE(user_id, id),
    UNIQUE(user_id, run_id, id),
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
    FOREIGN KEY(user_id, run_item_id) REFERENCES run_items(user_id, id),
    FOREIGN KEY(user_id, run_id, run_item_id) REFERENCES run_items(user_id, run_id, id)
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
    FOREIGN KEY(user_id, run_item_id) REFERENCES run_items(user_id, id),
    FOREIGN KEY(user_id, run_id, run_item_id) REFERENCES run_items(user_id, run_id, id)
);
CREATE TABLE run_stages (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    run_id TEXT NOT NULL,
    run_item_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    state_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL,
    UNIQUE(run_item_id, stage),
    FOREIGN KEY(user_id, run_id, run_item_id) REFERENCES run_items(user_id, run_id, id)
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


_MIGRATE_1_TO_2 = """
BEGIN;
ALTER TABLE runs ADD COLUMN evaluator_version TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE runs ADD COLUMN gold_fingerprint TEXT NOT NULL DEFAULT '';
CREATE UNIQUE INDEX idx_run_items_user_run_id ON run_items(user_id, run_id, id);
CREATE TABLE artifacts_v2 (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), run_id TEXT NOT NULL,
    run_item_id TEXT, category TEXT NOT NULL, relative_path TEXT NOT NULL, media_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL, name TEXT NOT NULL, created_at TEXT NOT NULL,
    FOREIGN KEY(user_id, run_id) REFERENCES runs(user_id, id),
    FOREIGN KEY(user_id, run_id, run_item_id) REFERENCES run_items(user_id, run_id, id)
);
INSERT INTO artifacts_v2 SELECT * FROM artifacts;
DROP TABLE artifacts;
ALTER TABLE artifacts_v2 RENAME TO artifacts;
CREATE TABLE metrics_v2 (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), run_id TEXT NOT NULL,
    run_item_id TEXT NOT NULL, dimension TEXT NOT NULL, layer TEXT NOT NULL, metric_name TEXT NOT NULL,
    scope TEXT NOT NULL, value REAL, count INTEGER, unit TEXT, scope_json TEXT, created_at TEXT NOT NULL,
    UNIQUE(run_item_id, dimension, layer, metric_name, scope),
    FOREIGN KEY(user_id, run_id) REFERENCES runs(user_id, id),
    FOREIGN KEY(user_id, run_id, run_item_id) REFERENCES run_items(user_id, run_id, id)
);
INSERT INTO metrics_v2 SELECT * FROM metrics;
DROP TABLE metrics;
ALTER TABLE metrics_v2 RENAME TO metrics;
CREATE TABLE run_stages (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), run_id TEXT NOT NULL,
    run_item_id TEXT NOT NULL, stage TEXT NOT NULL, status TEXT NOT NULL,
    state_json TEXT NOT NULL DEFAULT '{}', updated_at TEXT NOT NULL,
    UNIQUE(run_item_id, stage),
    FOREIGN KEY(user_id, run_id, run_item_id) REFERENCES run_items(user_id, run_id, id)
);
PRAGMA user_version = 2;
COMMIT;
"""

_MIGRATE_2_TO_3 = """
BEGIN;
ALTER TABLE run_items ADD COLUMN input_path TEXT;
ALTER TABLE run_items ADD COLUMN confirmation_json TEXT;
ALTER TABLE run_items ADD COLUMN bundle_sha256 TEXT;
PRAGMA user_version = 3;
COMMIT;
"""

_MIGRATE_3_TO_4 = """
BEGIN;
ALTER TABLE models ADD COLUMN agent_id TEXT REFERENCES agents(id);
PRAGMA user_version = 4;
COMMIT;
"""


def _migrate_4_to_5(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN IMMEDIATE")
        # Old models were user-scoped. Preserve historical runs by splitting a
        # model into Agent-owned copies when it was shared across Agents.
        models = connection.execute("SELECT * FROM models WHERE agent_id IS NULL").fetchall()
        from uuid import uuid4
        for model in models:
            owners = connection.execute(
                "SELECT DISTINCT agent_id FROM runs WHERE user_id=? AND model_id=? ORDER BY agent_id",
                (model["user_id"], model["id"]),
            ).fetchall()
            if not owners:
                agents = connection.execute("SELECT id FROM agents WHERE user_id=? ORDER BY id", (model["user_id"],)).fetchall()
                owners = agents if len(agents) == 1 else []
            for index, owner in enumerate(owners):
                agent_id = owner["agent_id"] if "agent_id" in owner.keys() else owner["id"]
                model_id = model["id"] if index == 0 else str(uuid4())
                if index == 0:
                    connection.execute("UPDATE models SET agent_id=? WHERE id=?", (agent_id, model["id"]))
                else:
                    connection.execute(
                        "INSERT INTO models (id,user_id,agent_id,name,provider,model_id,config_json,created_at) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (model_id, model["user_id"], agent_id, model["name"], model["provider"],
                         model["model_id"], model["config_json"], model["created_at"]),
                    )
                    connection.execute("UPDATE runs SET model_id=? WHERE user_id=? AND model_id=? AND agent_id=?",
                                       (model_id, model["user_id"], model["id"], agent_id))
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_models_owner_ref ON models(user_id,agent_id,id)")
        connection.execute("""
            CREATE TABLE runs_v5 (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), agent_id TEXT NOT NULL,
                model_id TEXT NOT NULL, status TEXT NOT NULL, config_json TEXT NOT NULL,
                created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, run_path TEXT NOT NULL,
                evaluator_version TEXT NOT NULL DEFAULT 'unknown', gold_fingerprint TEXT NOT NULL DEFAULT '',
                UNIQUE(user_id,id),
                FOREIGN KEY(user_id,agent_id) REFERENCES agents(user_id,id),
                FOREIGN KEY(user_id,model_id) REFERENCES models(user_id,id),
                FOREIGN KEY(user_id,agent_id,model_id) REFERENCES models(user_id,agent_id,id)
            )
        """)
        connection.execute("INSERT INTO runs_v5 SELECT * FROM runs")
        connection.execute("DROP TABLE runs")
        connection.execute("ALTER TABLE runs_v5 RENAME TO runs")
        connection.execute("CREATE INDEX idx_runs_user ON runs(user_id,created_at DESC)")
        connection.execute("PRAGMA user_version = 5")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def initialize_database(db_path: Path) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect_database(db_path)
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError(f"database version {version} is newer than supported {SCHEMA_VERSION}")
        if version == 0:
            connection.executescript("BEGIN;\n" + _SCHEMA + "\nPRAGMA user_version = 5;\nCOMMIT;")
        elif version == 1:
            connection.executescript(_MIGRATE_1_TO_2)
            connection.executescript(_MIGRATE_2_TO_3)
            connection.executescript(_MIGRATE_3_TO_4)
        elif version == 2:
            connection.executescript(_MIGRATE_2_TO_3)
            connection.executescript(_MIGRATE_3_TO_4)
        elif version == 3:
            connection.executescript(_MIGRATE_3_TO_4)
            _migrate_4_to_5(connection)
        elif version == 4:
            _migrate_4_to_5(connection)
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
