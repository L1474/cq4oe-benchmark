# Task 4: Durable Run Worker and HTTP API

## RED

- Added run-service tests for draft state, missing uploads, invalid or incomplete CQ2Term JSON, incomplete CQ2Onto confirmation, multi-item upload completeness, path-safe upload names, size limits, and per-run input snapshots. The first focused run failed during collection because `web.services.run_service` did not exist.
- Added worker tests for readiness gating, FIFO run claiming, partial completion, persisted stage events, and startup recovery. The first focused run failed during collection because `web.services.worker` did not exist.
- Added API tests for catalog and bundle downloads, Agent and Agent-owned Model routes, run upload/start, event access, JSON upload errors, path-free run responses, and indexed-artifact-only downloads.
- Added repository coverage for listing models by Agent. Its first run failed because the repository did not yet provide `list_models`.

## GREEN

- Added a `RunService` that creates draft runs, resolves CQ IDs from the project catalog, snapshots the CQ bundle hash on each item, validates and copies uploads into generated per-item input paths, stores CQ2Onto confirmations, and atomically validates all items before queueing.
- Added database migrations through schema version 4 for item upload/confirmation snapshots and Agent ownership of Models. Models created through the nested API are scoped to their Agent; legacy repository-created Models may retain a null `agent_id` for compatibility.
- Added `ModelReadinessService` and a readiness-gated, single-claim worker. It evaluates items sequentially, stores stage events/state, metrics and indexed output artifacts, preserves successful items when another fails, and recovers interrupted runs with a durable event.
- Added FastAPI routes for health, catalog and bundles, Agents and nested Models, runs, confirmations, uploads, events, and indexed artifact downloads. Lifespan initializes the database and starts/stops background services; app construction itself does not create runtime data.

## Verification

Command:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest web/tests -q -p no:cacheprovider
```

Result: **46 passed**. `git diff --check` passed. Pytest reports one upstream `DeprecationWarning` from Starlette's TestClient using AnyIO's deprecated `BlockingPortal` alias; it does not affect test results.

## Notes

- API and repository-created Model behavior is Agent-associated. Existing database Models from before the migration remain unassigned rather than being guessed onto an Agent.
- The worker and readiness services are covered with deterministic fakes; no live Ollama service or full benchmark subprocess run was performed.

## Fix Round

### RED

- Added a repository test that creates two Agents and two owned Models, then attempts to create a run pairing Agent A with Model B. It failed because the initial schema allowed the mismatched pair.
- Added a worker test that emits an item result file and asserts its indexed path stays under `items/<item_id>/results/`. It failed because indexing copied the file into the shared run-level `results/` directory.

### GREEN

- Schema version 5 adds a composite `(user_id, agent_id, model_id)` foreign key from runs to models, plus matching model uniqueness and Agent ownership constraints. The repository now associates unqualified model creation with the user's sole Agent, and rejects ambiguous cases. Run service checks require exact Agent ownership.
- The v4 migration assigns legacy models to historical run Agents, splitting model rows when one legacy model was used by multiple Agents, then rebuilds the runs table with the composite foreign key.
- Worker output indexing snapshots each item-local category walk before copying artifacts back into that same item tree. Declared artifact metadata is applied during the single indexing pass, avoiding a second indexing pass for the same source.
- Added a migration regression test covering a legacy model shared across two Agents and verifying both historical run mappings and `PRAGMA foreign_key_check` after migration.
- Final fix-round command `PYTHONDONTWRITEBYTECODE=1 python -m pytest web/tests -q -p no:cacheprovider`: **50 passed** with the same single upstream Starlette/AnyIO deprecation warning.
