# Task 5 RED/GREEN Report

## Scope

Added the Agent, run creation, and domain catalog screens using FastAPI page routes, Jinja templates, and vanilla CSS/JavaScript. The desktop shell uses a persistent sidebar with Run, Records, Domains, and Agent Management; the narrow layout turns it into a horizontally scrollable navigation bar. The run form uses task/domain selectors and an Add item action, then renders only selected items with their task CQ totals, CQ bundle link, and per-item file input.

The domain list displays counts without embedding question text. Domain detail and the run review drawer show task-specific CQ tabs, IDs, questions, and bundle downloads. The CQ2Onto modal gates progress on a complete CQ ID set and a successful confirmation API response. Confirmed items are remembered for the current draft and skipped when an upload retry resumes.

Agent creation/edit/delete and model create/edit/delete use the Task 4 API. Agent and model labels enter the DOM with `textContent`; server-rendered fields use Jinja autoescaping. CQ2Term upload validation remains server-authoritative and is reported beside the affected item file control.

## RED

Added `web/tests/test_pages.py` before the page implementation. After correcting a test syntax typo, the tests failed as expected because `/agents` returned 404 and the other page routes were absent. The run page contracts cover task-specific count targets, task/domain selectors, Add item, selected-item region, and the CQ2Onto modal gate. The domain contracts verify question text is absent from the catalog list and present with both task bundle links on the detail page.

## GREEN

- Focused `web/tests/test_pages.py web/tests/test_api.py`: 9 passed.
- Full `web/tests`: 66 passed, 1 existing Starlette/AnyIO deprecation warning.
- `node --check web/static/app.js`: passed.
- `git diff --check`: passed; Git only reported line-ending normalization warnings for files already modified in the worktree.
- Browser smoke check: `/runs/new` rendered with a 220px desktop sidebar at 1280px, and the mobile layout at 390px had no horizontal document overflow. Adding CQ2Onto / `water` created one selected row, displayed 21 CQs from the catalog API, and linked to `/api/catalog/cq2onto/water/bundle`.

The task venv initially lacked Jinja2 despite the task brief's dependency note. Pip installation was blocked by the machine's configured SOCKS proxy support. Jinja2 and MarkupSafe already existed in the local Python 3.10 environment, so those installed packages were copied into the task-only venv to run the requested pytest command without a `PYTHONPATH` override. Jinja2 is now declared in both `requirements.txt` and `pyproject.toml` so normal installs include it.

## Notes

The browser smoke check exercised layout, domain selection, API count loading, and bundle URL generation. The end-to-end file submission and confirmation interaction remains covered by the web API tests rather than a browser-driven upload session. Task 6 supplies the `/records` and `/runs/{run_id}` destination pages referenced by navigation and queued-run redirection.
