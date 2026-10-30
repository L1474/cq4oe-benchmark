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

## Review Fix Round 1/5

### RED

Added `web/tests/page_interactions.playwright.js`, which drives the page with delayed and rejected API responses. Before the fixes, it failed on stale Agent A model rows after switching to Agent B, unreachable last entries in the water and SWO CQ drawers, Escape not closing the drawer, missing focus in the modal/drawer, unlabelled CQ checkboxes, a confirmation error hidden behind the drawer, and duplicate draft creation from rapid Prepare clicks.

### GREEN

- The same browser interaction script passes after the fixes.
- Agent model requests use a monotonically increasing request token and verify the selected Agent before rendering.
- CQ detail and confirmation lists scroll inside a `min-height: 0` flex child. The footer stays outside that scroller. Water's 21-item and SWO's 35-item CQ2Onto checklists were each reached at the end of the desktop viewport; SWO's 35-item list was also reached at 390x700 mobile size. The footer remained in the viewport and the mobile document had no horizontal overflow.
- Drawer and modal focus an initial control, trap Tab navigation, close on Escape, and restore focus to the checklist link when returning from its drawer. CQ checkboxes use explicit `<label for>` associations containing their IDs/questions. Only one dialog is open at a time, so `aria-modal` remains accurate.
- Confirmation API errors render and receive focus inside the drawer. Prepare is disabled during draft creation/upload, with a pending-state guard against duplicate clicks. Failed uploads leave the draft available for retry, and completed CQ2Onto confirmations do not reappear.
- The domain detail drawer includes each task's prediction input format.

### Visual Evidence

Playwright captures: `.playwright-mcp/task5-drawer-desktop.png` (1280x800) and `.playwright-mcp/task5-drawer-mobile.png` (390x700). The interaction test separately scrolled to the final CQ in each requested dataset/viewport and verified the footer remained reachable.

### Verification

Round 1 verification:

- Focused `web/tests/test_pages.py web/tests/test_api.py`: 9 passed.
- Full `web/tests`: 66 passed, 1 existing Starlette/AnyIO deprecation warning.
- `node --check web/static/app.js`: passed.
- `git diff --check`: passed, with line-ending normalization warnings only.
- The Playwright interaction test passed with the 21- and 35-question checklists at desktop and mobile sizes, delayed Agent responses, rejected confirmation, focus checks, and retry behavior. Browser console errors are the expected mocked 400 responses; no JavaScript runtime errors were reported.

## Notes

The browser smoke check exercised layout, domain selection, API count loading, and bundle URL generation. The end-to-end file submission and confirmation interaction remains covered by the web API tests rather than a browser-driven upload session. Task 6 supplies the `/records` and `/runs/{run_id}` destination pages referenced by navigation and queued-run redirection.
