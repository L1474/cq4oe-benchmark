# Task 2 Report: SQLite Schema and Durable Artifact Storage

## TDD Evidence

RED command before implementation:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; .superpowers/sdd/2026-10-30-local-web-evaluator/venv/Scripts/python.exe -m pytest -p no:cacheprovider web/tests/test_db.py -q
```

Output:

```text
ERROR collecting web/tests/test_db.py
ModuleNotFoundError: No module named 'web.db'
1 error in 0.17s
```

This confirmed the schema behavior tests failed because the requested database module did not exist.

GREEN focused command:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; .superpowers/sdd/2026-10-30-local-web-evaluator/venv/Scripts/python.exe -m pytest -p no:cacheprovider web/tests/test_db.py web/tests/test_repositories.py web/tests/test_artifacts.py -q
```

Output:

```text
.......                                                                  [100%]
7 passed in 0.36s
```

GREEN full web tests command:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; .superpowers/sdd/2026-10-30-local-web-evaluator/venv/Scripts/python.exe -m pytest -p no:cacheprovider web/tests -q
```

Output:

```text
.....................                                                    [100%]
21 passed in 0.45s
```

`git diff --check` completed without output.

## Files

- `web/db.py`: version 1 schema, UTC timestamps, ownership-aware foreign keys, uniqueness constraints, and configured SQLite connections.
- `web/repositories.py`: typed agent/model/run/event/metric/artifact persistence functions with user scoping and atomic run/item/event insertion.
- `web/services/__init__.py`: service package marker.
- `web/services/artifacts.py`: run-root file copy with category validation, byte size, and SHA-256 metadata.
- `web/tests/test_db.py`: idempotent initialization, table set, FK, and run-item uniqueness.
- `web/tests/test_repositories.py`: ownership, queued run/item directories, event ordering, and metric uniqueness.
- `web/tests/test_artifacts.py`: copied artifact integrity and path escape rejection.

## Self-Review

- Database transactions are owned by repository calls; artifact bytes remain outside SQLite.
- Composite foreign keys prevent runs and run items from referring across users.
- Run identifiers and item directory names are UUIDs; Agent/model names are not used in filesystem paths.
- Artifact source paths must resolve within the run root, and downloaded artifact paths are checked after resolution to reject traversal and symlink escapes.
- Metric uniqueness is enforced by SQLite on `(run_item_id, dimension, layer, metric_name, scope)`.
- No material concerns remain for this storage slice.

## Review Round 1: Run Ownership, Workspace Atomicity, and Stage Provenance

RED command after adding the review regressions:

```text
cmd.exe /c "set PYTHONDONTWRITEBYTECODE=1 && .superpowers\sdd\2026-10-30-local-web-evaluator\venv\Scripts\python.exe -m pytest -p no:cacheprovider web/tests/test_db.py web/tests/test_repositories.py web/tests/test_artifacts.py -q"
```

Output:

```text
ERROR collecting web/tests/test_repositories.py
ImportError: cannot import name 'get_stage_states' from 'web.repositories'
1 error in 0.20s
```

The new repository contract failed collection because stage persistence was not implemented.

GREEN focused persistence command and output:

```text
cmd.exe /c "set PYTHONDONTWRITEBYTECODE=1 && .superpowers\sdd\2026-10-30-local-web-evaluator\venv\Scripts\python.exe -m pytest -p no:cacheprovider web/tests/test_db.py web/tests/test_repositories.py web/tests/test_artifacts.py -q"
```

```text
..........                                                               [100%]
10 passed in 0.55s
```

GREEN full web suite command and output:

```text
cmd.exe /c "set PYTHONDONTWRITEBYTECODE=1 && .superpowers\sdd\2026-10-30-local-web-evaluator\venv\Scripts\python.exe -m pytest -p no:cacheprovider web/tests -q"
```

```text
........................                                                 [100%]
24 passed in 0.63s
```

The schema is now version 2. Existing version 1 databases migrate by adding evaluator/gold provenance columns, rebuilding artifact and metric constraints to bind item references to the same run, and adding `run_stages`. New and upgraded schemas both enforce `(user_id, run_id, run_item_id)` associations. Run directories are fully created before the queued run transaction; any directory or insert failure removes the partial run workspace. Stage state can be upserted and queried by run and item.

Review regression coverage verifies cross-run artifact/metric inserts fail, injected directory creation failures leave no queued database rows or partial run directories, and evaluator version, gold fingerprint, and stage state round-trip.
