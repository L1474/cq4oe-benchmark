async (page) => {
  const failures = [];
  const check = (condition, message) => { if (!condition) failures.push(message); };
  let pageRequests = 0;
  let apiRequests = 0;
  const html = (status, stage, extra = "") => `<!doctype html><html><head><script src="/static/app.js" defer></script></head>
    <body><main class="page-content"><section class="detail-summary" data-run-id="live-run" data-run-status="${status}">
    <span class="state-pill">${status}</span></section><section class="detail-section" id="run-inputs">${status} input</section>
    <section class="detail-section" id="run-metrics">${status} metric</section>
    <section class="detail-section" id="run-stages">${stage} stage</section>
    <section class="detail-section" id="report">${extra || "No Markdown report is available for this run."}</section>
    <section class="detail-section" id="run-artifacts">${extra || "No artifacts recorded."}</section></main></body></html>`;
  await page.route("**/runs/live-run", (route) => {
    pageRequests += 1;
    const body = pageRequests === 1 ? html("queued", "queued")
      : pageRequests === 2 ? html("running", "class", "partial log")
      : html("completed", "completed", "Final report and artifact");
    route.fulfill({ contentType: "text/html", body });
  });
  await page.route("**/api/runs/live-run", (route) => { apiRequests += 1; route.fulfill({ json: { status: "completed" } }); });
  await page.goto("http://127.0.0.1:8766/runs/live-run");
  await page.waitForFunction(() => document.querySelector(".detail-summary")?.dataset.runStatus === "completed", null, { timeout: 10000 });
  check(await page.locator("#run-inputs").textContent() === "completed input", "item status should refresh");
  check(await page.locator("#run-metrics").textContent() === "completed metric", "metrics should refresh");
  check(await page.locator("#run-stages").textContent() === "completed stage", "stages and logs should refresh");
  check((await page.locator("#report").textContent()).includes("Final report"), "report should refresh");
  check((await page.locator("#run-artifacts").textContent()).includes("artifact"), "artifacts should refresh");
  check(pageRequests === 3 && apiRequests === 0, "polling should stop at terminal state and use page refresh only");
  await page.waitForTimeout(2500);
  check(pageRequests === 3, "terminal run should remain idle");
  if (failures.length) throw Error(failures.join("\n"));
  return "live run detail checks passed";
}
