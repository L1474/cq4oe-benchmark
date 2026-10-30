async (page) => {
  const failures = [];
  const check = (condition, message) => { if (!condition) failures.push(message); };
  const answers = Array.from({ length: 35 }, (_, index) => ({ id: `Q${index + 1}`, question: `Competency question ${index + 1}?` }));
  let draftRequests = 0;
  const draftReleases = [];
  let delayDraft = false;
  let confirmFails = false;

  await page.route("**/api/agents", (route) => route.fulfill({ json: [
    { id: "agent-a", name: "Agent A" }, { id: "agent-b", name: "Agent B" },
  ] }));
  await page.route("**/api/agents/agent-a/models", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 180));
    await route.fulfill({ json: [{ id: "model-a", name: "Model A", model_id: "a", provider: "ollama" }] });
  });
  await page.route("**/api/agents/agent-b/models", (route) => route.fulfill({ json: [
    { id: "model-b", name: "Model B", model_id: "b", provider: "ollama" },
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
  await page.route("**/api/runs/*/items/*/confirmation", (route) => {
    if (confirmFails) route.fulfill({ status: 400, json: { detail: "Server rejected confirmation" } });
    else route.fulfill({ json: { confirmed: true } });
  });
  await page.route("**/api/runs/*/items/*/upload", (route) => route.fulfill({ status: 400, json: { detail: "Keep draft for retry" } }));

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("http://127.0.0.1:8766/runs/new");
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
    const measure = await page.evaluate(() => {
      const host = document.querySelector("#drawer-content");
      const last = host.querySelector("li:last-child");
      const footer = document.querySelector(".drawer-footer");
      host.scrollTop = host.scrollHeight;
      return { scrollHeight: host.scrollHeight, clientHeight: host.clientHeight,
        lastBottom: last.getBoundingClientRect().bottom, footerTop: footer.getBoundingClientRect().top,
        hostBottom: host.getBoundingClientRect().bottom };
    });
    check(measure.scrollHeight > measure.clientHeight && measure.lastBottom <= 800, `${domain}: last CQ should be reachable by scrolling inside drawer`);
    await page.keyboard.press("Escape");
    check(await page.locator("#cq-drawer").isHidden(), "Escape should close drawer");
    if (!(await page.locator("#cq-drawer").isHidden())) await page.locator("#cq-drawer [data-close-drawer]").click();
  }

  await page.selectOption("#run-model", "model-b");
  await page.locator("[data-item-key='cq2onto:swo'] input[type=file]").setInputFiles({ name: "swo.owl", mimeType: "application/rdf+xml", buffer: Buffer.from("<rdf:RDF/>") });
  await page.locator("[data-item-key='cq2onto:water'] input[type=file]").setInputFiles({ name: "water.owl", mimeType: "application/rdf+xml", buffer: Buffer.from("<rdf:RDF/>") });
  delayDraft = true;
  await page.click("#prepare-run");
  await page.waitForTimeout(100);
  await page.locator("#prepare-run").dispatchEvent("click");
  await page.waitForTimeout(100);
  check(draftRequests === 1, "rapid Prepare clicks should create one draft");
  draftReleases.forEach((release) => release());
  await page.waitForSelector("#confirmation-modal:not([hidden])");
  check((await page.evaluate(() => document.activeElement?.closest("#confirmation-modal") !== null)), "modal should own initial focus");
  await page.click("#open-checklist");
  await page.waitForSelector("#cq-drawer:not([hidden])");
  check((await page.evaluate(() => document.activeElement?.closest("#cq-drawer") !== null)), "drawer should own initial focus");
  check(await page.locator("#drawer-content input[type=checkbox]").count() === 21, "water should show all 21 CQ checkboxes");
  const desktopWater = await page.evaluate(() => {
    const host = document.querySelector("#drawer-content");
    const last = host.querySelector(".cq-check:last-child");
    host.scrollTop = host.scrollHeight;
    return { scrollHeight: host.scrollHeight, clientHeight: host.clientHeight, lastBottom: last.getBoundingClientRect().bottom,
      footerBottom: document.querySelector(".drawer-footer").getBoundingClientRect().bottom };
  });
  check(desktopWater.scrollHeight > desktopWater.clientHeight && desktopWater.lastBottom <= 800, "water desktop: last CQ checkbox should be reachable");
  check(desktopWater.footerBottom <= 800, "water desktop: confirmation footer should remain reachable");
  await page.setViewportSize({ width: 390, height: 700 });
  const mobileWater = await page.evaluate(() => {
    const host = document.querySelector("#drawer-content");
    const last = host.querySelector(".cq-check:last-child");
    host.scrollTop = host.scrollHeight;
    return { scrollHeight: host.scrollHeight, clientHeight: host.clientHeight,
      lastBottom: last.getBoundingClientRect().bottom, footerBottom: document.querySelector(".drawer-footer").getBoundingClientRect().bottom,
      pageWidth: document.documentElement.scrollWidth, viewport: innerWidth };
  });
  check(mobileWater.scrollHeight > mobileWater.clientHeight && mobileWater.lastBottom <= 700, "water mobile: last CQ checkbox should be reachable");
  check(mobileWater.footerBottom <= 700 && mobileWater.pageWidth <= mobileWater.viewport, "water mobile: footer should remain reachable without page overflow");
  await page.setViewportSize({ width: 1280, height: 800 });
  const checkbox = page.locator("#drawer-content input[type=checkbox]").first();
  check(await checkbox.evaluate((node) => node.labels.length > 0 && node.labels[0].textContent.includes(node.value)), "CQ checkbox should have an accessible CQ label");
  await page.locator("#drawer-content input[type=checkbox]").evaluateAll((nodes) => nodes.forEach((node) => { node.checked = true; node.dispatchEvent(new Event("change", { bubbles: true })); }));
  confirmFails = true;
  await page.click("#save-confirmation");
  await page.waitForTimeout(100);
  const drawerError = page.locator("#drawer-error");
  check(await drawerError.isVisible(), "server confirmation error should be visible inside drawer");
  check((await page.evaluate(() => document.activeElement?.id)) === "drawer-error", "confirmation error should receive focus");

  confirmFails = false;
  await page.click("#save-confirmation");
  await page.waitForSelector("#confirmation-modal:not([hidden])");
  check(await page.locator("#drawer-error").isHidden(), "successful confirmation should clear drawer error on next open");
  await page.click("#accept-confirmation");
  await page.waitForSelector("#confirmation-modal:not([hidden])");
  check((await page.locator("#confirmation-title").textContent()).includes("swo"), "next CQ2Onto item should be SWO");
  await page.setViewportSize({ width: 390, height: 700 });
  await page.click("#open-checklist");
  await page.waitForSelector("#drawer-content input[type=checkbox]");
  check(await page.locator("#drawer-content input[type=checkbox]").count() === 35, "SWO should show all 35 CQ checkboxes");
  const desktopSwo = await page.evaluate(() => {
    const host = document.querySelector("#drawer-content");
    const last = host.querySelector(".cq-check:last-child");
    host.scrollTop = host.scrollHeight;
    return { scrollHeight: host.scrollHeight, clientHeight: host.clientHeight, lastBottom: last.getBoundingClientRect().bottom,
      footerBottom: document.querySelector(".drawer-footer").getBoundingClientRect().bottom };
  });
  check(desktopSwo.scrollHeight > desktopSwo.clientHeight && desktopSwo.lastBottom <= 800, "SWO desktop: last CQ checkbox should be reachable");
  check(desktopSwo.footerBottom <= 800, "SWO desktop: confirmation footer should remain reachable");
  const mobile = await page.evaluate(() => {
    const host = document.querySelector("#drawer-content");
    const last = host.querySelector(".cq-check:last-child");
    host.scrollTop = host.scrollHeight;
    return { scrollHeight: host.scrollHeight, clientHeight: host.clientHeight,
      lastBottom: last.getBoundingClientRect().bottom,
      footerBottom: document.querySelector(".drawer-footer").getBoundingClientRect().bottom,
      pageWidth: document.documentElement.scrollWidth, viewport: innerWidth };
  });
  check(mobile.scrollHeight > mobile.clientHeight && mobile.lastBottom <= 700, "SWO mobile: last CQ checkbox should be reachable");
  check(mobile.footerBottom <= 700 && mobile.pageWidth <= mobile.viewport, "SWO mobile: footer should remain reachable without page overflow");
  await page.locator("#cq-drawer [data-close-drawer]").focus();
  await page.keyboard.press("Shift+Tab");
  check((await page.evaluate(() => document.activeElement?.closest("#cq-drawer") !== null)), "drawer should trap backward Tab");
  await page.keyboard.press("Escape");
  check(await page.locator("#cq-drawer").isHidden(), "Escape should return from drawer to modal");
  check((await page.evaluate(() => document.activeElement?.id)) === "open-checklist", "drawer should restore focus to modal checklist link");
  await page.keyboard.press("Shift+Tab");
  check((await page.evaluate(() => document.activeElement?.closest("#confirmation-modal") !== null)), "modal should trap backward Tab");
  await page.click("#open-checklist");
  await page.locator("#drawer-content input[type=checkbox]").evaluateAll((nodes) => nodes.forEach((node) => { node.checked = true; node.dispatchEvent(new Event("change", { bubbles: true })); }));
  await page.click("#save-confirmation");
  await page.click("#accept-confirmation");
  await page.waitForSelector("#run-error:not([hidden])");
  check(await page.locator("#confirmation-modal").isHidden(), "completed confirmations should close modal");
  await page.click("#prepare-run");
  await page.waitForTimeout(100);
  check(await page.locator("#confirmation-modal").isHidden(), "upload retry should not reopen confirmed checklists");
  check(draftRequests === 1, "upload retry should reuse original draft");

  if (failures.length) throw Error(failures.join("\n"));
  return "interaction checks passed";
}
