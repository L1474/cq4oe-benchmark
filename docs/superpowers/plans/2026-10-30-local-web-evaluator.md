# CQ4OE Local Web Evaluator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Docker Compose local Web app where users manage Agents and models, package and review benchmark CQs, upload predictions, run isolated CQ4OE evaluations, and browse or compare durable results.

**Architecture:** Add a focused `web/` Python application using FastAPI, server-rendered Jinja pages, vanilla JavaScript, SQLite, and a single persistent database-backed worker. Existing evaluator scripts remain the scoring engine; a per-run adapter invokes them with run-specific input/output paths, parses their JSON/CSV metrics, and indexes every output under `data/runs/<run_id>/`. Docker Compose runs the app with Java and an Ollama embedding service, while a host bind mount preserves the database and run artifacts.

**Tech Stack:** Python 3.10, FastAPI, Uvicorn, Jinja2, Python-Markdown, Bleach, SQLite (`sqlite3`), vanilla JavaScript/CSS, Docker Compose, Java/HermiT, Ollama `embeddinggemma`, pytest.

## Global Constraints

- The app is a single-machine local application; it does not provide public hosting, account registration, or cross-user sharing in the first release.
- The first release does not generate model predictions; users download task/domain CQ packages and upload generated prediction files.
- Use SQLite for run metadata, status, structured metrics, and artifact indexes; store files under `data/runs/<run_id>/` and save relative paths, file types, sizes, and SHA-256 hashes in SQLite.
- Store every evaluation's input snapshot, parameters, evaluator version, gold-standard fingerprint, stage status, stdout/stderr, reports, metrics, and raw output files under its unique `run_id`.
- Do not stage Web uploads into the repository's shared `01_predictions` folders or refresh the shared leaderboard during a Web run.
- CQ2Term must reject predictions with missing, duplicate, or unknown required CQ IDs.
- CQ2Onto requires CQ completion confirmation in an upload-check dialog; the combined ontology file itself cannot prove per-CQ generation provenance.
- CQ2Onto must present metric dimensions and AC/Global, strict/closure, and diagnostic scopes distinctly; do not produce one synthetic total score.
- Preserve all existing evaluator-produced artifacts, including merged Markdown reports, alignment traces, per-CQ coverage, Triple TXT, and Atomic TBox JSON/TXT/XLSX.
- Use the Python range already declared in `pyproject.toml` (`>=3.10,<3.11`) and keep the new runtime dependencies in sync between `requirements.txt` and `pyproject.toml`.

---

## File Map

- Create `web/app.py` for FastAPI construction and lifecycle wiring.
- Create `web/config.py` for repository/data paths, upload limits, and dependency URLs.
- Create `web/types.py` for shared `ValidationResult`, `RunItemInput`, `RunItem`, `RunPaths`, `ArtifactRecord`, `MetricRecord`, `EvaluationStage`, `RunSummary`, and `ComparisonResult` dataclasses.
- Create `web/__init__.py`, `web/domain/__init__.py`, `web/services/__init__.py`, and `web/routes/__init__.py` so application modules have stable package imports.
- Create `web/db.py` for SQLite connection setup and versioned schema migration.
- Create `web/repositories.py` for SQL operations over users, agents, models, runs, run items, artifacts, metrics, and run events.
- Create `web/domain/catalog.py`, `web/domain/bundles.py`, and `web/domain/validation.py` for discovering benchmark domains/CQs, building downloadable CQ packages, and validating uploads/confirmations.
- Create `web/services/run_service.py` and `web/services/worker.py` for durable run creation, queueing, stage events, recovery, and status transitions.
- Create `web/services/evaluator.py` and `web/services/metrics.py` for isolated evaluator subprocess invocation, artifact collection, and normalized metric extraction.
- Create `web/routes/api.py` for JSON APIs and upload/download endpoints; create `web/routes/pages.py` for HTML pages.
- Create `web/templates/` for the Agent, Run, Domain, Record, Detail, and Compare screens; create `web/static/app.css` and `web/static/app.js` for page interactions.
- Create `web/tests/` for isolated unit, API, evaluator-adapter, and database tests using temporary directories and mocked subprocess calls.
- Create `Dockerfile`, `docker-compose.yml`, and `docker/entrypoint.sh` for the local app image, Java runtime, background Ollama model readiness, health checks, and persistent data mount.
- Create `.dockerignore` so Git history, old versions, existing predictions/results, caches, virtual environments, and host `data/` do not inflate the image build context.
- Modify `requirements.txt` and `pyproject.toml` for FastAPI, Uvicorn, Jinja2, and multipart upload support; add HTTPX to the dev test dependencies for FastAPI TestClient.
- Modify `README.md` with Docker startup, CQ package, upload, data location, and backup instructions.

## Shared Type Contracts

Define these in `web/types.py` before implementing service modules; keep optional measurements nullable rather than encoding undefined metric values as zero.

```python
@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str]

@dataclass(frozen=True)
class RunItemInput:
    task: str
    domain: str

@dataclass(frozen=True)
class RunPaths:
    run_root: Path
    input_dir: Path
    work_dir: Path
    results_dir: Path
    logs_dir: Path
    report_path: Path

@dataclass(frozen=True)
class MetricRecord:
    dimension: str
    layer: str
    metric_name: str
    value: float | None
    unit: str
    scope: str
    tp: int | None = None
    fp: int | None = None
    fn: int | None = None
    numerator: int | None = None
    denominator: int | None = None
```

`Settings` in `web/config.py` contains `project_root`, `data_dir`, `db_path`, `max_upload_bytes`, `ollama_base_url`, `worker_poll_seconds`, and `shutdown_grace_seconds`. `RunItemInput` is only the requested task/domain pair; the server resolves expected CQ IDs from its own catalog. `RunItem` adds its database ID, run ID, task, domain, input artifact path, server-resolved expected CQ IDs, and confirmed CQ IDs. `ArtifactRecord` contains its database ID, run/item IDs, category, relative path, media type, byte size, and SHA-256. `EvaluationStage` contains its name, argv list, task-root working directory, and expected output paths. `RunSummary` contains run ID, Agent/model IDs and labels, item keys, state, evaluator/gold fingerprints, canonical config, and indexed metric records. `ComparisonResult` contains selected run IDs and metric deltas with compatibility reasons.

## Task 1: CQ Catalog, Packages, and Upload Validation

**Files:**
- Create: `web/domain/catalog.py`
- Create: `web/domain/bundles.py`
- Create: `web/domain/validation.py`
- Create: `web/domain/__init__.py`
- Create: `web/__init__.py`
- Create: `web/types.py`
- Create: `web/tests/domain/test_catalog.py`
- Create: `web/tests/domain/test_bundles.py`
- Create: `web/tests/domain/test_validation.py`

**Interfaces:**
- `list_domains(project_root: Path) -> list[dict]` returns domain slug, display name, and per-task effective unique CQ counts plus raw source counts by reading the task-specific CQ JSON files.
- `get_domain_detail(project_root: Path, domain: str) -> dict` returns de-duplicated task-specific CQ IDs/questions, exact duplicate counts, and input requirements, never gold annotations.
- `build_cq_bundle(project_root: Path, task: str, domain: str) -> bytes` returns a ZIP with de-duplicated `cqs.json`, `manifest.json`, `README.txt`, and for CQ2Term a blank prediction JSON containing every unique expected ID.
- `validate_cq_term_prediction(project_root: Path, domain: str, payload: object) -> ValidationResult` verifies the list schema, unique complete expected IDs, no unknown IDs, and class/property string arrays.
- `validate_cq2onto_confirmation(project_root: Path, domain: str, confirmed_ids: list[str]) -> ValidationResult` verifies that each current task-specific CQ ID has been confirmed exactly once.
- Supported task identifiers are `cq2term` and `cq2onto`; domain discovery is based on `CQ2Term/competency_question/*_cq2term_cqs.json` and `CQ2Onto/competency_question/*_cq2onto_cqs.json`.

- [ ] **Step 1: Write failing tests for domain discovery and task-specific CQ counts**

Assert the checked-in catalog returns task counts independently: Wine `5/5`, SWO `26/35`, and ODRL source counts `19/18` in `(CQ2Term, CQ2Onto)` order. ODRL CQ2Term has two exact repeated rows (`CQ13`, `CQ26`), so its effective unique CQ count is `17`; the catalog must report both `source_count=19` and `count=17`. Assert an unknown domain raises `KeyError` and an absent task CQ file does not invent a count.

- [ ] **Step 2: Run the catalog tests and verify they fail**

Run: `pytest web/tests/domain/test_catalog.py -q`
Expected: FAIL because `web.domain.catalog` does not exist.

- [ ] **Step 3: Implement catalog discovery from the checked-in CQ files**

Parse CQ JSON as structured data; require each entry to have a non-empty `id` and a string question from `value` or `question`. Merge repeated entries only when both `id` and question are identical; reject one ID paired with conflicting question text. Keep CQ2Term and CQ2Onto registries separate even where their current contents overlap, and do not modify benchmark CQ or gold files.

Use the task's exact source path and keep questions in memory only for the response:

```python
def _cq_file(project_root: Path, task: str, domain: str) -> Path:
    task_dir = {"cq2term": "CQ2Term", "cq2onto": "CQ2Onto"}[task]
    return project_root / task_dir / "competency_question" / f"{domain}_{task}_cqs.json"
```

- [ ] **Step 4: Run the catalog tests and verify they pass**

Run: `pytest web/tests/domain/test_catalog.py -q`
Expected: PASS with task counts matching the repository data.

- [ ] **Step 5: Write failing tests for CQ ZIP contents and CQ2Term validation**

Use `zipfile.ZipFile` over `build_cq_bundle(...)` bytes. Assert the bundle contains `cqs.json`, `manifest.json`, `README.txt`, and `prediction_template.json` for CQ2Term; assert the CQ2Onto bundle omits prediction templates and gold-standard paths. Test a valid CQ2Term list plus missing, duplicate, unknown IDs and malformed term arrays.

- [ ] **Step 6: Implement deterministic CQ bundles and validation results**

The manifest must contain `task`, `domain`, `version`, `source_count`, `count`, `deduplicated_exact_duplicates`, and unique `expected_cq_ids`. Use the SHA-256 of canonicalized raw task CQ JSON as `version`. Set `count` to the number of unique prompts and `source_count` to the number of rows in the repository file. The prediction template rows must contain exactly `id`, `value`, `class`, and `property`, with empty term arrays.

Keep ZIP paths fixed and use only source CQ data:

```python
manifest = {
    "task": task,
    "domain": domain,
    "version": hashlib.sha256(canonical_cq_json).hexdigest(),
    "source_count": len(source_cqs),
    "count": len(cqs),
    "deduplicated_exact_duplicates": len(source_cqs) - len(cqs),
    "expected_cq_ids": [cq["id"] for cq in cqs],
}
```

- [ ] **Step 7: Run all domain tests and commit the catalog slice**

Run: `pytest web/tests/domain -q`
Expected: PASS, including a scan proving no gold annotation directory or gold answer field is included in either bundle.

Commit: `git add web/domain web/tests/domain && git commit -m "feat(web): add CQ catalog and upload validation"`

## Task 2: SQLite Schema and Durable Artifact Storage

**Files:**
- Create: `web/db.py`
- Create: `web/repositories.py`
- Create: `web/services/artifacts.py`
- Create: `web/tests/test_db.py`
- Create: `web/tests/test_repositories.py`
- Create: `web/tests/test_artifacts.py`

**Interfaces:**
- `initialize_database(db_path: Path) -> None` creates/upgrades schema using `PRAGMA user_version` and inserts the single local user if absent.
- `connect_database(db_path: Path) -> sqlite3.Connection` enables foreign keys, a 30-second busy timeout, and row objects.
- Repository methods use explicit typed inputs and return dictionaries with stable snake_case keys; repository code owns transactions but never writes artifact files.
- `store_artifact(run_root: Path, source: Path, category: str, media_type: str) -> ArtifactRecord` copies a file into a category directory, calculates byte size and SHA-256, and returns its relative path and metadata.
- Core tables: `users`, `agents`, `models`, `runs`, `run_items`, `artifacts`, `metrics`, and `run_events`; all user-owned rows carry `user_id`, and every run item has `(run_id, task, domain)` uniqueness.

- [ ] **Step 1: Write failing tests for schema constraints and initialization idempotence**

Create a temporary SQLite database twice and assert there is one local user, all eight tables exist, foreign keys reject an item with no run, and duplicate `(run_id, task, domain)` rows fail.

- [ ] **Step 2: Run the database tests and verify they fail**

Run: `pytest web/tests/test_db.py -q`
Expected: FAIL because schema initialization is not implemented.

- [ ] **Step 3: Implement the initial versioned SQLite schema and connections**

Keep SQL statements in `web/db.py`; store timestamps as UTC ISO-8601 text, metric values as nullable REAL plus optional count/unit/scope JSON, and run configuration as JSON text. Do not store uploaded file bytes in SQLite.

Use the SQLite built-in version number for the first migration and enable FK checks on every connection:

```python
def connect_database(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30, isolation_level="DEFERRED")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn
```

- [ ] **Step 4: Run database tests and verify they pass**

Run: `pytest web/tests/test_db.py -q`
Expected: PASS, with the second initialization leaving the schema and local user unchanged.

- [ ] **Step 5: Write failing repository and artifact tests**

Test Agent/model ownership, queued run plus items in one transaction, status/event ordering, metric uniqueness by `(run_item_id, dimension, layer, metric_name, scope)`, artifact SHA-256, and refusal to copy a source outside the run workspace when resolving stored relative paths.

- [ ] **Step 6: Implement repositories and the run-scoped artifact store**

Define `create_agent`, `list_agents`, `create_model`, `create_run`, `get_run`, `list_runs`, `add_event`, `save_metrics`, `add_artifact`, and `resolve_artifact_path`. Generate `run_id` with UUID4; create shared run metadata under `data/runs/<run_id>/` and isolated item data under `data/runs/<run_id>/items/<item_id>/{input,work,results,logs}`. Do not use user-controlled Agent or model names in paths.

Resolve an indexed path beneath its run root before serving a download:

```python
candidate = (run_root / artifact.relative_path).resolve()
if not candidate.is_relative_to(run_root.resolve()):
    raise ValueError("artifact path escapes run root")
```

- [ ] **Step 7: Run persistence tests and commit the storage slice**

Run: `pytest web/tests/test_db.py web/tests/test_repositories.py web/tests/test_artifacts.py -q`
Expected: PASS, including a test that two runs with identical model/domain names resolve to distinct directories.

Commit: `git add web/db.py web/repositories.py web/services/artifacts.py web/tests/test_db.py web/tests/test_repositories.py web/tests/test_artifacts.py && git commit -m "feat(web): persist runs and artifacts in SQLite"`

## Task 3: Isolated Evaluator Adapter and Metric Extraction

**Files:**
- Create: `web/services/evaluator.py`
- Create: `web/services/metrics.py`
- Create: `web/services/commands.py`
- Create: `web/services/__init__.py`
- Create: `web/tests/services/test_commands.py`
- Create: `web/tests/services/test_evaluator.py`
- Create: `web/tests/services/test_metrics.py`

**Interfaces:**
- `build_cq2term_command(project_root: Path, item: RunItem, paths: RunPaths, config: dict) -> list[str]` returns the `eval_cq_terms.py` command with absolute gold/input/output paths and every standard CQ2Term artifact path.
- `build_cq2onto_commands(project_root: Path, item: RunItem, paths: RunPaths, config: dict) -> list[EvaluationStage]` returns ordered stages `class`, `property`, `triple`, `atomic`, `axiom`, `hierarchy`; every result and report path is inside the current run.
- `run_stage(stage: EvaluationStage, stdout_path: Path, stderr_path: Path, event_sink: Callable) -> None` executes one subprocess in `stage.cwd`, streams stdout and stderr independently to the supplied paths and tagged event lines, and raises `EvaluationStageError` with stage, exit code, and both log paths on failure.
- `extract_cq2term_metrics(result_json: Path, coverage_csv: Path) -> list[MetricRecord]` and `extract_cq2onto_metrics(result_paths: RunPaths) -> list[MetricRecord]` preserve dimension, layer, metric name, unit, scope, and source counts.
- No adapter invokes the batch runners or writes below repository `01_predictions`, `02_atomic_axioms`, `03_evaluation_results`, `04_summary`, or `leaderboard` directories.

- [ ] **Step 1: Write command-builder tests for run-local paths and exact stage order**

Build commands with temporary `RunPaths`; assert every `--save_*`, `--output_*`, input, and prediction path belongs to the run or read-only gold root. Assert CQ2Onto stages are ordered class/property/triple/atomic/axiom/hierarchy and CQ2Term uses the supplied gold and prediction paths.

- [ ] **Step 2: Run the adapter tests and verify they fail**

Run: `pytest web/tests/services/test_commands.py -q`
Expected: FAIL because the adapter module does not exist.

- [ ] **Step 3: Implement command builders using existing evaluator CLIs**

Call the scripts in `CQ2Term/scripts` and `CQ2Onto/scripts` directly with `cwd` set to the corresponding task root (`CQ2Term` or `CQ2Onto`), matching the existing batch runner's relative-path assumptions. For Atomic TBox extraction, copy the uploaded ontology into `work/` first because `Axioms_atomic.py` writes JSON/TXT/XLSX beside its input. Set Axiom cache path under `work/`; request Axiom Layer 2 pair CSV and Hierarchy TXT so supported diagnostics are archived too.

Construct arguments as a list, never as a shell command string:

```python
command = [
    sys.executable,
    "scripts/eval_cq_terms.py",
    "--gold_cq_to_terms", str(gold_path),
    "--pred_cq_to_terms", str(item.input_path),
    "--save_result_json", str(paths.results / "06_cq_terms" / "result.json"),
    "--save_report_md", str(paths.results / "report.md"),
]
```

- [ ] **Step 4: Write and run subprocess streaming tests**

Mock `subprocess.Popen` to emit stdout and stderr in chunks; assert complete text is saved separately to `<stage>.stdout.log` and `<stage>.stderr.log`, each event carries its stream name, a zero exit completes, and non-zero exit raises `EvaluationStageError` without deleting partial files.

- [ ] **Step 5: Implement stage execution and failure recording**

Use one queue worker so Java, Ollama, and local embedding/cache resources are not concurrently contested. Leave runs queued while the embedding model is not ready; do not fail them just because the first model download is in progress. Keep one separate report path per run item so report append operations cannot mix runs. Stream stdout and stderr independently to their respective files and persist tagged event lines in `run_events`.

Run with argument arrays and retain partial outputs if a process fails:

```python
proc = subprocess.Popen(stage.command, cwd=stage.cwd, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, bufsize=1)
return_code = stream_both_pipes(proc, stdout_path, stderr_path, event_sink)
if return_code:
    raise EvaluationStageError(stage.name, return_code, stdout_path, stderr_path)
```

- [ ] **Step 6: Write metric extraction tests from representative output shapes**

Cover CQ2Term `metrics_overall` and per-CQ coverage; CQ2Onto class/property aggregated results, property-characteristic AC/Global, Triple semantic/AC/Global, Axiom semantic/AC/Global/CQ coverage, and Hierarchy combined P/R/F1 plus closure CQ coverage. Assert denominator-zero metrics stay null and scopes remain distinct.

- [ ] **Step 7: Implement metric extraction and run the complete service test set**

Use fixture JSON objects with the checked-in result schema. Store each metric as `MetricRecord(dimension, layer, metric_name, value, unit, scope, tp, fp, fn, numerator, denominator)`; do not infer a global CQ2Onto score.

Extract each metric with its comparison scope in the identity:

```python
records.append(MetricRecord(
    dimension="triple", layer="layer3_strict", metric_name="f1",
    value=float(overall["f1"]), unit="ratio", scope="alignment_conditioned",
    tp=overall["tp"], fp=overall["fp"], fn=overall["fn"],
))
```

Run: `pytest web/tests/services -q`
Expected: PASS, with no test invoking embedding, Java, or a real evaluator process.

Commit: `git add web/services/evaluator.py web/services/metrics.py web/services/commands.py web/tests/services && git commit -m "feat(web): run evaluations in isolated workspaces"`

## Task 4: Durable Run Worker and HTTP API

**Files:**
- Create: `web/services/run_service.py`
- Create: `web/services/model_readiness.py`
- Create: `web/services/worker.py`
- Create: `web/routes/api.py`
- Create: `web/routes/__init__.py`
- Create: `web/config.py`
- Create: `web/tests/test_run_service.py`
- Create: `web/tests/test_api.py`
- Modify: `web/app.py`

**Interfaces:**
- `create_draft_run(user_id: int, agent_id: int, model_id: int | None, items: list[RunItemInput], config: dict) -> str` creates a draft run and item rows.
- `save_item_upload(run_id: str, item_id: int, upload: UploadFile) -> ArtifactRecord` enforces configured byte limits, safe server-generated filenames, task/domain extension rules, validation, and immutable input snapshot storage.
- `start_run(run_id: str) -> None` atomically validates all task-specific uploads/confirmations and transitions `draft -> queued`.
- `ModelReadinessService.start() -> None` launches a background readiness check/model pull; `is_ready() -> bool` becomes true only after Ollama reports `embeddinggemma` available. The web process serves pages before this is ready, while the evaluation worker leaves jobs queued.
- `EvaluationWorker.run_forever(stop_event: threading.Event) -> None` claims queued runs transactionally in FIFO order, executes each run item, records stage events and artifacts/metrics, and persists `completed`, `partial`, or `failed` status.
- HTTP routes: `GET /health`; `GET /api/catalog`; `GET /api/catalog/{task}/{domain}`; `GET /api/catalog/{task}/{domain}/bundle`; `GET/POST /api/agents`; `PATCH/DELETE /api/agents/{agent_id}`; `GET/POST /api/agents/{agent_id}/models`; `PATCH/DELETE /api/models/{model_id}`; `POST /api/runs`; `PUT /api/runs/{run_id}/items/{item_id}/confirmation`; `POST /api/runs/{run_id}/items/{item_id}/upload`; `POST /api/runs/{run_id}/start`; `GET /api/runs`; `GET /api/runs/{run_id}`; `GET /api/runs/{run_id}/events`; `GET /api/artifacts/{artifact_id}`.

- [ ] **Step 1: Write failing run-service tests for upload and state transitions**

Assert a run cannot start with no upload, malformed CQ2Term JSON, unconfirmed CQ2Onto IDs, or one missing item in a multi-item run. Assert valid input snapshots are immutable copies under that run and a second run cannot overwrite the first.

- [ ] **Step 2: Run the run-service tests and verify they fail**

Run: `pytest web/tests/test_run_service.py -q`
Expected: FAIL because run service and worker do not exist.

- [ ] **Step 3: Implement draft/upload/start services with transaction boundaries**

Store the CQ2Onto confirmed ID list and CQ bundle SHA-256 with the run item. Reject unsafe names, oversized uploads, unsupported extensions, missing CQs, and files that cannot be parsed before queueing.

The start transaction must verify all run items before changing the run state:

```python
with conn:
    items = repository.get_run_items(conn, run_id)
    for item in items:
        require_valid_upload(item)
        require_complete_cq_confirmation(item)
    repository.transition_run(conn, run_id, expected="draft", new="queued")
```

- [ ] **Step 4: Write failing worker readiness, recovery, and ordering tests**

Use a fake evaluator/readiness service and temporary DB. Assert the worker leaves queued runs untouched while readiness is false, claims them once readiness becomes true, oldest queued run is claimed first, stage events persist in order, partial failure keeps completed task/domain items, and a run left `running` at startup becomes failed with an interruption event while queued work remains eligible.

- [ ] **Step 5: Implement readiness-gated background work**

Start a model-readiness thread and the daemon run worker from FastAPI lifespan. The model thread retries Ollama startup and pulls `embeddinggemma` through `POST /api/pull`; it records ready/failed state without blocking the Web server. The run worker leaves jobs queued until `is_ready()` is true. On startup recover interrupted runs; on shutdown signal both threads and wait within the configured grace period.

Claim only one queued run inside an immediate transaction, then perform evaluation outside the transaction:

```python
with conn:
    conn.execute("BEGIN IMMEDIATE")
    run = repository.claim_oldest_queued_run(conn)
if run is not None:
    evaluator.evaluate_run(run)
```

- [ ] **Step 6: Write API tests for catalog, bundles, Agents, uploads, runs, events, and artifacts**

Use FastAPI `TestClient`, a temporary project-data root, and a fake worker. Assert download content types, upload errors return useful 4xx JSON, artifact download is restricted to indexed run files, and route paths never expose arbitrary filesystem access.

- [ ] **Step 7: Implement FastAPI routes and run the backend test suite**

Create `FastAPI(lifespan=...)`, mount static files, initialize the database on startup, and inject config/repositories/queue through app state for tests.

Keep app construction injectable so tests can pass temporary paths and a fake evaluator:

```python
def create_app(settings: Settings, worker_factory: Callable[..., EvaluationWorker]) -> FastAPI:
    app = FastAPI(lifespan=build_lifespan(settings, worker_factory))
    app.state.settings = settings
    app.include_router(api_router, prefix="/api")
    return app
```

Run: `pytest web/tests -q`
Expected: PASS, including domain, database, adapter, run-service, worker, and API tests.

Commit: `git add web/app.py web/routes/api.py web/services/run_service.py web/services/worker.py web/tests && git commit -m "feat(web): expose durable local evaluation runs"`

## Task 5: Agent, Domain, and Run Interface

**Files:**
- Create: `web/routes/pages.py`
- Create: `web/templates/base.html`
- Create: `web/templates/agents.html`
- Create: `web/templates/runs_new.html`
- Create: `web/templates/domains.html`
- Create: `web/templates/domain_detail.html`
- Create: `web/static/app.css`
- Create: `web/static/app.js`
- Create: `web/tests/test_pages.py`
- Modify: `web/app.py`

**Interfaces:**
- Page routes in this task: `/agents`, `/runs/new`, `/domains`, `/domains/{domain}`. Task 6 adds `/records`, `/runs/{run_id}`, and `/compare`.
- Agent screen supports creating/editing an Agent and managing one or more model rows using the API from Task 4.
- Run screen selects Agent/model, one or more task/domain items, shows the per-task CQ count prominently, provides CQ bundle downloads, and accepts one prediction file per item.
- Domain detail uses a drawer with task tabs, all CQ IDs/questions, count, input format, and task-specific bundle download.
- Before CQ2Onto upload submission, a modal shows the total CQ count and completed count; it links to the drawer checklist and blocks submission until every CQ ID is marked provided to the Agent.
- CQ2Term JSON upload validation is shown inline from API feedback; do not require a duplicate client-only validator.

- [ ] **Step 1: Write page route tests and static template contract tests**

Assert the route pages return 200, the domain list has no inline full question dump, run form contains task-specific CQ count targets, and domain drawer renders task-specific CQs and package links.

- [ ] **Step 2: Implement server-rendered page routes and shared navigation**

Use Jinja2 templates and escape all user-provided Agent/model labels. Keep the first screen on the actual run/records workflow rather than a marketing introduction.

Configure templates from the app package and pass only the required view model:

```python
templates = Jinja2Templates(directory=str(settings.web_root / "templates"))

@router.get("/domains", response_class=HTMLResponse)
def domains_page(request: Request):
    return templates.TemplateResponse(
        request, "domains.html", {"domains": catalog.list_domains(settings.project_root)}
    )
```

- [ ] **Step 3: Add visual styles for the local evaluation console**

Use restrained operational styling, compact tables, clear task/domain sections, semantic status colors, accessible focus states, stable icon/button sizes, and responsive navigation. Keep full CQ text in the drawer.

Keep page regions in normal flow and make tabular controls stable at small widths:

```css
.app-shell { display: grid; grid-template-columns: 220px minmax(0, 1fr); min-height: 100vh; }
.data-table { width: 100%; table-layout: fixed; border-collapse: collapse; }
.cq-drawer { position: fixed; inset: 0 0 0 auto; width: min(560px, 100vw); overflow-y: auto; }
@media (max-width: 760px) { .app-shell { grid-template-columns: 1fr; } }
```

- [ ] **Step 4: Implement Agent CRUD and run-form selection in vanilla JavaScript**

Load Agents/models and domain/task counts from APIs; when task/domain changes, request catalog data and update counts and bundle links. Keep file controls associated with their `(task, domain)` item IDs.

Use task/domain as the stable key for each upload control:

```javascript
const itemKey = ({ task, domain }) => `${task}:${domain}`;
const response = await fetch(`/api/catalog/${task}/${domain}`);
const detail = await response.json();
countNode.textContent = `${detail.cq_count} CQs`;
bundleLink.href = `/api/catalog/${task}/${domain}/bundle`;
```

- [ ] **Step 5: Implement the CQ detail drawer and CQ2Onto confirmation modal**

Maintain confirmed CQ IDs per run item. The modal displays `confirmed_count / total_count`; its confirm action remains disabled unless the set exactly equals expected IDs. Store confirmations through the API before enabling upload.

Use set equality for the gate so duplicates or stale IDs cannot satisfy it:

```javascript
const allConfirmed = expectedIds.length > 0 &&
  expectedIds.every((id) => confirmedIds.has(id)) &&
  confirmedIds.size === expectedIds.length;
confirmButton.disabled = !allConfirmed;
countLabel.textContent = `${confirmedIds.size} / ${expectedIds.length}`;
```

- [ ] **Step 6: Implement submission feedback and verify rendered page tests**

Show validation errors next to the selected file, preserve other selected task/domain files when one fails, and route a successfully queued run to its record detail page.

Upload each item to its draft after the server has accepted its CQ confirmation:

```javascript
const body = new FormData();
body.append("file", fileInput.files[0]);
const result = await fetch(`/api/runs/${runId}/items/${itemId}/upload`, {
  method: "POST", body,
});
```

Run: `pytest web/tests/test_pages.py web/tests/test_api.py -q`
Expected: PASS for route contracts, task-specific counts, confirmation gating, and upload feedback.

Commit: `git add web/routes/pages.py web/templates web/static web/tests/test_pages.py web/app.py && git commit -m "feat(web): add Agent and benchmark run screens"`

## Task 6: Run Records, Reports, Trends, and Comparison

**Files:**
- Create: `web/templates/records.html`
- Create: `web/templates/run_detail.html`
- Create: `web/templates/compare.html`
- Create: `web/services/comparison.py`
- Create: `web/tests/services/test_comparison.py`
- Create: `web/tests/test_records_api.py`
- Modify: `web/routes/api.py`
- Modify: `web/routes/pages.py`
- Modify: `web/static/app.js`
- Modify: `web/static/app.css`

**Interfaces:**
- `compare_runs(run_records: list[RunSummary]) -> ComparisonResult` accepts two to four selected runs, matches metrics by task, domain, dimension, layer, name, unit, and scope, and gives only compatible metrics delta values.
- `find_previous_comparable_run(current_run: RunSummary, candidates: list[RunSummary]) -> RunSummary | None` requires same Agent, model, item set, evaluator/gold fingerprints, and canonical evaluation configuration; skips incomplete/failed runs.
- Page routes: `/records`, `/runs/{run_id}`, and `/compare?run_ids=<id1>,<id2>`.
- API additions: `GET /api/runs?agent_id=&model_id=&task=&domain=&status=&from=&to=&page=&page_size=`; `POST /api/runs/compare` with two to four run IDs; previous-comparable lookup is returned as trend metadata in each record row.
- Records filters: Agent, model, task, domain, state, and time range; default trend is against the prior comparable successful run and can be toggled off.
- Detail page shows run inputs, CQ confirmations/package version, config, ordered stage events/logs, structured metrics, complete Markdown report rendered as escaped/sanitized Markdown, and downloadable artifact links.
- Explicit comparison supports selecting 2-4 run IDs, labels model/config differences, and aggregates domains only on their intersection while showing the intersection count.

- [ ] **Step 1: Write comparison tests for compatible metrics and ineligible trends**

Test equal scope produces numeric deltas, a changed threshold/gold fingerprint prevents default trend arrows, changed task/domain omits deltas, lower error counts are marked as improvement, and global aggregates use only shared domains.

- [ ] **Step 2: Implement canonical config comparison and metric delta rules**

Treat higher F1/precision/recall/coverage as improvement and lower FP/FN/mismatch as improvement; do not color raw cosine or diagnostic candidate metrics as benchmark correctness unless the selected metric's direction is explicitly configured.

Require matching metric keys and config fingerprints before computing deltas:

```python
if current.metric_key != previous.metric_key:
    return MetricDelta(current=current, previous=previous, delta=None, comparable=False)
delta = current.value - previous.value
return MetricDelta(current, previous, delta, comparable=True)
```

- [ ] **Step 3: Add filtered record and comparison API endpoints**

Validate filter values and selected run count; return paginated records with trend metadata and comparison results with per-metric compatibility reasons.

Return the comparable-run identity with the row so the client only formats server-approved deltas:

```python
@router.get("/runs")
def list_runs(agent_id: int | None = None, model_id: int | None = None,
              task: str | None = None, domain: str | None = None,
              status: str | None = None, page: int = 1, page_size: int = 50):
    return run_service.list_runs_with_trends(
        agent_id=agent_id, model_id=model_id, task=task, domain=domain,
        status=status, page=page, page_size=min(page_size, 100),
    )
```

- [ ] **Step 4: Write record/detail API tests**

Assert filter composition, stable pagination, prior comparable lookup, per-item status in partial runs, complete report and artifact indexing, and artifact access restricted to a selected run.

- [ ] **Step 5: Implement records, detail, and compare pages**

Use one row per `run_id`; show a compact headline metric set without collapsing CQ2Onto to one total score. Add trend toggle and multi-row selection for explicit comparison.

Render a stable record key and separate trend metadata:

```html
<tr data-run-id="{{ run.run_id }}">
  <td><a href="/runs/{{ run.run_id }}">{{ run.run_id }}</a></td>
  <td>{{ run.agent_name }} / {{ run.model_name }}</td>
  <td>{{ run.item_summary }}</td>
  <td data-trend="{{ run.trend.status }}">{{ run.headline_metric }}</td>
</tr>
```

- [ ] **Step 6: Implement report and artifact browsing**

Render the complete `report.md` in the detail page with section navigation for Class, Property, Triple, Axiom, and Hierarchy; provide the original Markdown download and individually labeled JSON/CSV/TXT/XLSX/input downloads. Add `Markdown` and `bleach` as runtime dependencies, render with the tables extension, and sanitize generated HTML with an explicit allowlist before marking it safe for Jinja.

Only render sanitized output, and keep the original Markdown available as a separate download:

```python
raw_html = markdown.markdown(report_text, extensions=["tables"])
safe_html = bleach.clean(
    raw_html,
    tags={"h1", "h2", "h3", "p", "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td", "pre", "code", "strong", "em", "a", "hr", "blockquote"},
    attributes={"a": ["href", "title"]},
    protocols={"http", "https", "mailto"},
)
```

- [ ] **Step 7: Run UI/API regression tests and commit the record slice**

Run: `pytest web/tests -q`
Expected: PASS, including comparison compatibility, report rendering routes, pagination, filters, and file download authorization.

Commit: `git add web/services/comparison.py web/routes web/templates web/static web/tests && git commit -m "feat(web): browse and compare evaluation runs"`

## Task 7: Docker Compose, Documentation, and End-to-End Verification

**Files:**
- Create: `.dockerignore`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `docker/entrypoint.sh`
- Create: `web/tests/test_smoke.py`
- Modify: `requirements.txt`
- Modify: `pyproject.toml`
- Modify: `README.md`

**Interfaces:**
- `docker compose up --build` serves the app on `http://127.0.0.1:8000` and bind-mounts host `./data` to `/app/data`.
- The app container includes Python 3.10, project evaluator dependencies, and a Java runtime for HermiT.
- Ollama runs as a Compose service with a persistent model volume; the app starts independently and ensures `embeddinggemma` is available in a background task before semantic evaluation begins.
- The health endpoint `GET /health` reports app/database status and embedding service readiness without exposing secrets; pages remain available while embedding readiness is `starting`.
- README documents Docker prerequisite, first model download, CQ package download, upload/confirmation, local data location, stop/start persistence, backup, and reset instructions.

- [ ] **Step 1: Add and test runtime dependency declarations**

Add FastAPI, Uvicorn, Jinja2, `Markdown`, `bleach`, and `python-multipart` to `requirements.txt` and matching project dependencies in `pyproject.toml`; add HTTPX to the development group for `TestClient`. Keep Python `>=3.10,<3.11` and run `python -m pip check` in the built image.

- [ ] **Step 2: Create the Python/Java application image**

Build from a Python 3.10 slim base, install the project's Java runtime package, install `requirements.txt`, copy the evaluator and Web sources, create a non-root runtime user, and store persistent application state under `/app/data`.

Use a health-aware entrypoint and never bake runtime data into the image:

```dockerfile
FROM python:3.10-slim
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY CQ2Term ./CQ2Term
COPY CQ2Onto ./CQ2Onto
COPY web ./web
```

The `.dockerignore` must exclude `.git/`, `old_version/`, `submissions/`, `leaderboard/`, root `data/`, `.venv/`, `**/__pycache__/`, `**/.embed_cache.json`, and the generated trees `CQ2Term/01_predictions/`, `CQ2Term/03_evaluation_results/`, `CQ2Term/04_summary/`, `CQ2Onto/01_predictions/`, `CQ2Onto/02_atomic_axioms/`, `CQ2Onto/03_evaluation_results/`, and `CQ2Onto/04_summary/`. Keep both task `00_gold_standard/`, `competency_question/`, and `scripts/` in the build context.

- [ ] **Step 3: Add Compose services and persistent volumes**

Define `app` and `ollama`; expose only the app port on `127.0.0.1`; persist host `./data`, SQLite, and Ollama models; pass only service URLs and paths as environment variables; add health checks and make the app depend on Ollama `service_started`, not `service_healthy`, so page browsing is available during model initialization.

Bind the app only to loopback and persist run files separately from the container layer:

```yaml
services:
  app:
    build: .
    ports: ["127.0.0.1:8000:8000"]
    volumes: ["./data:/app/data"]
    environment:
      CQ4OE_DATA_DIR: /app/data
      OLLAMA_BASE_URL: http://ollama:11434
```

- [ ] **Step 4: Add background model readiness and health reporting**

Keep `docker/entrypoint.sh` limited to launching Uvicorn. In FastAPI lifespan, start `ModelReadinessService` in a background thread: retry the Ollama API, inspect `/api/tags`, and call `POST /api/pull` if `embeddinggemma` is missing. Return unhealthy from `/health` only when the DB is unavailable; report embedding readiness separately. The worker must not claim queued evaluation runs until the model is ready.

Use the Ollama HTTP API because `ollama` runs in a different Compose container; bound retries and keep the server process available immediately:

```sh
exec uvicorn web.app:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 5: Write a smoke test around a fake evaluator run**

Start the app with temporary paths, create an Agent and model, fetch a CQ package, upload a valid test fixture, pass CQ2Onto completion confirmation where applicable, queue the run with a fake evaluator, wait for its terminal state, and assert report/metrics/artifacts remain after app restart.

- [ ] **Step 6: Implement smoke coverage and verify all tests**

Run: `pytest web/tests -q`
Expected: PASS with no real Ollama model download, HermiT process, or external network dependency.

- [ ] **Step 7: Build and smoke-test Docker Compose**

Run: `docker compose config --quiet`
Expected: exit code 0.

Run: `docker compose build app`
Expected: image build succeeds and `python -m pip check` reports no broken requirements.

Run: `docker compose up -d app`
Expected: `/health` becomes ready at `http://127.0.0.1:8000/health` before the first model pull completes and reports embedding readiness separately; verify `./data` contains the SQLite database after creating an Agent, then stop Compose and confirm the same Agent remains after restart. Open the run, domain drawer, records, report, and compare pages at desktop and mobile viewport sizes and check that tables, CQ text, dialogs, and navigation remain readable without overlap.

- [ ] **Step 8: Document launch and user workflow; run final validation**

Update README with exact Compose commands, first-run model download behavior, supported CQ package formats, report/artifact inventory, and backup location. Run `git diff --check`, `pytest web/tests -q`, and `docker compose config --quiet` before committing.

Commit: `git add Dockerfile docker-compose.yml docker/entrypoint.sh requirements.txt pyproject.toml README.md web/tests/test_smoke.py && git commit -m "feat(web): package local evaluator with Docker Compose"`

## Acceptance Checklist

- A clean checkout launches with Docker Compose at `http://127.0.0.1:8000` and retains SQLite plus run files in host `./data` across restarts.
- CQ bundles are task/domain-specific, include a manifest/version/count, contain no gold answers, and CQ2Term includes a full-ID template.
- CQ counts are prominent in the run form; complete questions live in the domain drawer; CQ2Onto upload requires a modal confirmation backed by a complete CQ-ID set.
- Each task/domain evaluation uses its own `run_id` paths and cannot overwrite or read another run's input or outputs.
- Records have one row per `run_id`, support required filters, and show trends only for comparable runs; users can select 2-4 specific records for comparison.
- Detail pages show stage progress/logs, full Markdown report, structured metrics, original JSON/CSV/TXT/XLSX, Atomic TBox outputs, and input snapshots.
- CQ2Onto displays Class, Property, Triple, Axiom, and Hierarchy metrics with distinct diagnostic, AC/Global, strict, and closure scopes, with no synthetic overall score.
- All backend and smoke tests pass without requiring a live embedding service or Java reasoner; Docker health/startup checks cover those runtime dependencies.
