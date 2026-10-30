import hashlib

import pytest

from web.db import initialize_database
from web.repositories import add_artifact, create_agent, create_model, create_run, resolve_artifact_path
from web.services.artifacts import store_artifact


def test_store_artifact_copies_and_hashes_source(tmp_path):
    root = tmp_path / "run"
    source = root / "work" / "result.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(b'{"ok": true}')
    record = store_artifact(root, source, category="results", media_type="application/json")
    copied = root / record.relative_path
    assert copied.read_bytes() == source.read_bytes()
    assert record.size_bytes == len(source.read_bytes())
    assert record.sha256 == hashlib.sha256(source.read_bytes()).hexdigest()


def test_artifact_database_resolution_stays_inside_run_root(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    root = tmp_path / "run"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    agent = create_agent(db, user_id="local", name="Agent")
    model = create_model(db, user_id="local", name="Model", provider="ollama", model_id="m")
    run = create_run(db, user_id="local", agent_id=agent["id"], model_id=model["id"],
                     items=[], config={}, runs_root=tmp_path / "runs")
    artifact = add_artifact(db, user_id="local", run_id=run["id"], run_item_id=None,
                            category="results", relative_path="../secret.txt",
                            media_type="text/plain", size_bytes=6, sha256="x", name="secret.txt")
    with pytest.raises(ValueError, match="artifact path escapes run root"):
        resolve_artifact_path(root, artifact)
