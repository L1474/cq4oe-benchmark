# Task 6 RED/GREEN Report

## Scope

Added run records, detail, and comparison pages. The records API supports composed Agent, model, task/domain item, status, and inclusive date filters with stable pagination. A default trend only selects an earlier completed run with the same Agent, model, item set, evaluator and gold fingerprints, and canonical configuration. The UI formats server-approved deltas with directional colors and arrows, while CQ2Onto metrics remain separate by dimension and layer.

Explicit comparison accepts two to four distinct runs with matching task sets, configuration, evaluator version, and gold fingerprint. It compares only shared domains and metrics with matching task/domain/dimension/layer/name/unit/scope keys. The API labels each run's model and configuration. Unknown diagnostic metrics and unchanged values have neutral direction.

The detail page shows item status, CQ confirmations and package fingerprint, configuration, structured metrics, stages, ordered events, every indexed Markdown report, and indexed artifact downloads. Reports use Markdown tables and Bleach sanitization. Heading IDs are preserved only on headings and prefixed per report, so section links target unique sanitized headings. Artifact links are scoped by both run ID and artifact ID; public API records omit storage paths.

## RED

- New comparison tests first failed because `web.services.comparison` did not exist.
- Records API tests failed on the old unfiltered array response, missing compare endpoint, and artifact paths in the public detail response.
- Page tests exposed a Jinja dictionary-method collision and missing report anchors.
- Filter composition test caught task and domain matching different items within one run.
- Multi-task compare test caught an overly narrow single-task check.
- Neutral-direction test caught unchanged F1 being marked as a decline.

## GREEN

- Focused comparison, records, and page tests passed after the implementation.
- Full `web/tests` suite: **82 passed**, with one existing Starlette/AnyIO deprecation warning.
- `node --check web/static/app.js`: passed.
- `git diff --check`: passed.
- Playwright desktop (1280x800) and mobile (390x700) review: the records page rendered server-approved green up/red down trend indicators, and the mobile table scrolled within the page without document overflow. Screenshots: `C:/Users/14742/AppData/Local/Temp/task6-records-desktop.png` and `C:/Users/14742/AppData/Local/Temp/task6-records-mobile-final.png`.

The task venv initially lacked Markdown and Bleach. Pip could not use the machine's inherited SOCKS proxy without extra support, so the declared runtime packages were downloaded as official wheels and installed locally into the task venv. No repository or user pip configuration was changed.

## Review Fix Round 1

### RED

- Real draft runs with item sets `{alpha,beta}` and `{beta,gamma}` exposed that a run-wide gold fingerprint rejects a valid shared `beta` comparison. A second test changed only `beta` gold between runs and required rejection. A missing per-item fingerprint test ensured a matching synthetic aggregate hash cannot authorize comparison.
- A report detail test created two item artifacts both named `report.md` and required task/domain plus item-relative path in each label.
- A real `{alpha,beta}` versus `{beta}` test with a task script showed evaluator fingerprints differed solely because the script was hashed once per item.

### GREEN

- Schema version 6 adds nullable `run_items.gold_fingerprint`; version-5 migration preserves existing items with unknown per-item provenance. Draft creation persists a separate hash for each task/domain's gold inputs while retaining the strict run-wide hash for default trends.
- Manual comparison requires matching evaluator version and configuration, then compares nonempty shared task/domain items only when each has an equal, present gold fingerprint. Nonshared item gold may differ. Evaluator scripts are hashed once per task, independent of item count.
- Artifact labels now include the owning task/domain and path within that item; duplicate report names are distinguishable.
- Focused suite: 31 passed. Final full `web/tests` suite: **87 passed**, with one existing Starlette/AnyIO deprecation warning. `node --check web/static/app.js` and `git diff --check` passed.
