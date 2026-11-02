async (page) => {
  const failures = [];
  const check = (condition, message) => { if (!condition) failures.push(message); };
  const answers = Array.from({ length: 35 }, (_, index) => ({ id: `Q${index + 1}`, question: `Competency question ${index + 1}?` }));
  let draftRequests = 0;
  let delayDraft = false;
  let reviewFails = false;
  const draftReleases = [];
  const uploadAttempts = new Map();
  const reviewed = [];

  await page.route("**/api/agents", (route) => route.fulfill({ json: [
    { id: "agent-a", name: "Agent A" }, { id: "agent-b", name: "Agent B" },
  ] }));
  await page.route("**/api/agents/agent-a/models", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 180));
    await route.fulfill({ json: [{ id: "model-a", name: "Model A" }] });
  });
  await page.route("**/api/agents/agent-b/models", (route) => route.fulfill({ json: [
    { id: "model-b", name: "Model B" },
  ] }));
  await page.route("**/api/catalog", (route) => route.fulfill({ json: [
    { slug: "swo", name: "Swo", counts: { cq2onto: 35, cq2term: 26 } },
    { slug: "water", name: "Water", counts: { cq2onto: 21, cq2term: 20 } },
  ] }));
  await page.route("**/api/catalog/cq2onto/*", (route) => {
    const domain = route.request().url().split("/").pop();
    const cqs = domain === "water" ? answers.slice(0, 21) : answers;
    route.fulfill({ json: { count: cqs.length, cqs, input_requirements: {} } });
  });
  await page.route("**/api/runs", async (route) => {
    draftRequests += 1;
    const body = route.request().postDataJSON();
    if (delayDraft) await new Promise((resolve) => { draftReleases.push(resolve); });
    route.fulfill({ json: { id: `run-${draftRequests}`, status: "draft", items: body.items.map((item, index) => ({ id: `item-${index}`, ...item })) }, status: 201 });
  });
  await page.route("**/api/runs/*/items/*/review", (route) => {
    reviewed.push(route.request().url());
    if (reviewFails) route.fulfill({ status: 400, json: { detail: "Review failed" } });
    else route.fulfill({ json: { reviewed: true, cq_count: 21 } });
  });
  await page.route("**/api/runs/*/items/*/upload", (route) => {
    const itemId = route.request().url().split("/").at(-2);
    uploadAttempts.set(itemId, (uploadAttempts.get(itemId) || 0) + 1);
    route.fulfill(itemId === "item-0" ? { status: 201, json: { uploaded: true } }
      : { status: 400, json: { detail: "Keep draft for retry" } });
  });

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("http://127.0.0.1:8000/runs/new");
  await page.waitForSelector("#run-agent option[value='agent-b']", { state: "attached" });
  await page.selectOption("#run-agent", "agent-a");
  await page.selectOption("#run-agent", "agent-b");
  await page.waitForTimeout(250);
  check((await page.locator("#run-model option").allTextContents()).join(" ").includes("Model B"), "model B should remain after out-of-order responses");
  check(!(await page.locator("#run-model option").allTextContents()).join(" ").includes("Model A"), "stale model A should not appear");

  for (const domain of ["water", "swo"]) {
    await page.selectOption("#run-task", "cq2onto");
    await page.selectOption("#run-domain", domain);
    await page.click("#add-item");
    await page.waitForSelector(`[data-item-key='cq2onto:${domain}'] [data-item-count]`);
    await page.locator(`[data-item-key='cq2onto:${domain}'] .text-button`).click();
    await page.waitForSelector("#drawer-content .cq-list li:last-child");
    const count = await page.locator("#drawer-content .cq-list li").count();
    check(count === (domain === "water" ? 21 : 35), `${domain}: drawer should show every CQ`);
    check(await page.locator("#drawer-content input[type=checkbox]").count() === 0, `${domain}: drawer should be read only`);
    const measure = await page.evaluate(() => {
      const host = document.querySelector("#drawer-content");
      host.scrollTop = host.scrollHeight;
      return { scrollable: host.scrollHeight > host.clientHeight,
        lastBottom: host.querySelector("li:last-child").getBoundingClientRect().bottom,
        viewport: innerHeight };
    });
    check(measure.scrollable && measure.lastBottom <= measure.viewport, `${domain}: drawer should scroll to last CQ`);
    await page.keyboard.press("Escape");
    check(await page.locator("#cq-drawer").isHidden(), "Escape should close drawer");
  }

  await page.selectOption("#run-model", "model-b");
  for (const domain of ["water", "swo"]) {
    await page.locator(`[data-item-key='cq2onto:${domain}'] input[type=file]`).setInputFiles({
      name: `${domain}.owl`, mimeType: "application/rdf+xml", buffer: Buffer.from("<rdf:RDF/>"),
    });
  }
  delayDraft = true;
  await page.click("#prepare-run");
  await page.waitForTimeout(100);
  await page.locator("#prepare-run").dispatchEvent("click");
  check(draftRequests === 1, "rapid Prepare clicks should create one draft");
  draftReleases.forEach((release) => release());
  await page.waitForSelector("#confirmation-modal:not([hidden])");
  check(await page.locator("#review-list .cq-list li").count() === 21, "water modal should show all 21 questions");
  check(await page.locator("#confirmation-modal input[type=checkbox]").count() === 0, "modal should not ask for per-CQ checks");
  check(await page.locator("#accept-confirmation").isEnabled(), "one action should allow continuing");
  check(await page.evaluate(() => document.activeElement?.id === "review-list"), "modal should focus readable list");

  await page.click("#open-checklist");
  await page.waitForSelector("#cq-drawer:not([hidden])");
  await page.keyboard.press("Escape");
  check(await page.locator("#cq-drawer").isHidden(), "Escape should return from drawer to modal");
  check(await page.evaluate(() => document.activeElement?.id === "open-checklist"), "drawer should restore focus to modal link");

  reviewFails = true;
  await page.click("#accept-confirmation");
  await page.waitForSelector("#confirmation-error:not([hidden])");
  check(await page.locator("#confirmation-modal").isVisible(), "review failure should keep modal open");
  check(await page.evaluate(() => document.activeElement?.id === "confirmation-error"), "review error should receive focus");
  reviewFails = false;
  await page.click("#accept-confirmation");
  await page.waitForFunction(() => document.querySelector("#confirmation-title")?.textContent.includes("swo"));
  check(await page.locator("#review-list .cq-list li").count() === 35, "SWO modal should show all 35 questions");

  await page.setViewportSize({ width: 390, height: 700 });
  const mobile = await page.evaluate(() => {
    const host = document.querySelector("#review-list");
    host.scrollTop = host.scrollHeight;
    return { scrollable: host.scrollHeight > host.clientHeight,
      lastBottom: host.querySelector("li:last-child").getBoundingClientRect().bottom,
      pageWidth: document.documentElement.scrollWidth, viewportWidth: innerWidth,
      panelBottom: document.querySelector(".review-panel").getBoundingClientRect().bottom };
  });
  check(mobile.scrollable && mobile.lastBottom <= 700, "mobile review list should scroll to final CQ");
  check(mobile.pageWidth <= mobile.viewportWidth && mobile.panelBottom <= 700, "mobile modal should fit viewport");
  await page.click("#close-confirmation");
  await page.click("#prepare-run");
  await page.waitForSelector("#confirmation-modal:not([hidden])");
  check((await page.locator("#confirmation-title").textContent()).includes("swo"), "retry should skip already reviewed water");
  await page.click("#accept-confirmation");
  await page.waitForSelector("#run-error:not([hidden])");
  check(await page.locator("#confirmation-modal").isHidden(), "reviewed items should proceed to upload");
  check(uploadAttempts.get("item-0") === 1 && uploadAttempts.get("item-1") === 1, "first upload pass should reach both items");
  await page.locator("[data-item-key='cq2onto:water'] input[type=file]").setInputFiles({
    name: "water-replacement.owl", mimeType: "application/rdf+xml", buffer: Buffer.from("<rdf:RDF replacement='true'/>"),
  });
  await page.click("#prepare-run");
  await page.waitForSelector("#run-error:not([hidden])");
  check(await page.locator("#confirmation-modal").isHidden(), "upload retry should not repeat completed CQ review");
  check(uploadAttempts.get("item-0") === 2, "replacement file should upload again");
  check(draftRequests === 1, "upload retry should reuse original draft");
  check(reviewed.length === 3, "each item should need only one successful review action");

  if (failures.length) throw Error(failures.join("\n"));
  return "read-only CQ review checks passed";
}
