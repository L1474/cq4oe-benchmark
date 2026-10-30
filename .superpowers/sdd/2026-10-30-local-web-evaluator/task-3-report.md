# Task 3 Report: Isolated Evaluator Adapter and Metric Extraction

## TDD Evidence

RED command:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; .superpowers/sdd/2026-10-30-local-web-evaluator/venv/Scripts/python.exe -m pytest -p no:cacheprovider web/tests/services/test_commands.py -q
```

Output:

```text
ModuleNotFoundError: No module named 'web.services.commands'
1 error during collection
```

GREEN focused command:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; .superpowers/sdd/2026-10-30-local-web-evaluator/venv/Scripts/python.exe -m pytest -p no:cacheprovider web/tests/services -q
```

Output:

```text
......                                                                   [100%]
6 passed in 0.24s
```

Full web test command:

```text
$env:PYTHONDONTWRITEBYTECODE='1'; .superpowers/sdd/2026-10-30-local-web-evaluator/venv/Scripts/python.exe -m pytest -p no:cacheprovider web/tests -q
```

Output:

```text
..............................                                           [100%]
30 passed in 0.82s
```

## Changes

- Added run item, run paths, evaluation stage, and metric record contracts while preserving `ValidationResult`.
- Added CQ2Term and ordered CQ2Onto command builders that invoke each evaluator script directly with per-item output/report paths. Uploaded ontologies are copied under `work/atomic/` before atomic TBox extraction; the axiom embedding cache is under `work/`.
- Requested the Axiom Layer 2 pair CSV and Hierarchy TXT report, and kept gold inputs rooted in the checked-in read-only gold directories.
- Added concurrent stdout/stderr draining with separate log files, tagged stream events, and stage-specific errors that retain partial logs.
- Added CQ2Term and CQ2Onto metric extractors for aggregated, semantic, alignment-conditioned, global, characteristic, and CQ-coverage values. Scope is retained in each metric identity and zero-denominator source nulls remain null.
- Added command path/order, stream/error behavior, metric scope, coverage, and null-value service tests.

## Concerns

- Single-worker scheduling and model-readiness gating belong to the queue orchestration layer. These adapter functions do not implement that scheduler; callers should invoke ordered stages through one worker and leave queued items untouched until embeddings are available.
- Tests mock subprocess streams and do not start Java, Ollama, embeddings, or evaluator scripts, as required for focused service tests.

`git diff --check` passed.
