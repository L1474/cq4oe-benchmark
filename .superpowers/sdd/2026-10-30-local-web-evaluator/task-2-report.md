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
