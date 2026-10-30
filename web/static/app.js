(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const itemKey = ({ task, domain }) => `${task}:${domain}`;
  const cqCount = (detail) => detail.cq_count ?? detail.count;

  async function request(url, options = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      try {
        const body = await response.json();
        message = body.detail || body.message || message;
      } catch (_) {}
      throw new Error(message);
    }
    if (response.status === 204) return null;
    return response.json();
  }

  function showNotice(node, message) {
    node.textContent = message;
    node.hidden = false;
  }

  function hideNotice(node) {
    if (node) {
      node.textContent = "";
      node.hidden = true;
    }
  }

  function setupDomainDrawer() {
    const drawer = $("#cq-drawer");
    if (!drawer || !$("#domain-data")) return;
    const scrim = $("#drawer-scrim");
    const close = () => {
      drawer.hidden = true;
      scrim.hidden = true;
    };
    const open = () => {
      drawer.hidden = false;
      scrim.hidden = false;
      const first = $("[role=tab]", drawer);
      if (first) first.focus();
    };
    $$('[data-close-drawer]', drawer).forEach((button) => button.addEventListener("click", close));
    scrim.addEventListener("click", close);
    $$('[data-open-task]').forEach((button) => button.addEventListener("click", () => {
      open();
      selectTask(button.dataset.openTask);
    }));
    const selectTask = (task) => {
      $$('[data-task-tab]', drawer).forEach((tab) => {
        const selected = tab.dataset.taskTab === task;
        tab.setAttribute("aria-selected", String(selected));
      });
      $$('[data-task-panel]', drawer).forEach((panel) => {
        panel.hidden = panel.dataset.taskPanel !== task;
      });
    };
    $$('[data-task-tab]', drawer).forEach((tab) => tab.addEventListener("click", () => selectTask(tab.dataset.taskTab)));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !drawer.hidden) close();
    });
  }

  function setupAgents() {
    const list = $("#agents-list");
    const form = $("#agent-form");
    if (!list || !form) return;
    const error = $("#agent-error");
    const nameInput = $("#agent-name");
    const descriptionInput = $("#agent-description");
    const idInput = $("#agent-id");

    const button = (label, className, action) => {
      const element = document.createElement("button");
      element.type = "button";
      element.className = className;
      element.textContent = label;
      element.addEventListener("click", action);
      return element;
    };

    const openForm = (agent = null) => {
      idInput.value = agent?.id || "";
      nameInput.value = agent?.name || "";
      descriptionInput.value = agent?.description || "";
      $("#agent-form-title").textContent = agent ? "Edit Agent" : "New Agent";
      form.hidden = false;
      nameInput.focus();
    };
    const closeForm = () => { form.hidden = true; };
    $("#new-agent").addEventListener("click", () => openForm());
    $("#cancel-agent").addEventListener("click", closeForm);
    $("#cancel-agent-secondary").addEventListener("click", closeForm);

    async function render() {
      list.replaceChildren();
      try {
        const agents = await request("/api/agents");
        if (!agents.length) {
          const empty = document.createElement("p");
          empty.className = "muted";
          empty.textContent = "No Agents configured.";
          list.append(empty);
          return;
        }
        for (const agent of agents) {
          const card = document.createElement("section");
          card.className = "agent-card";
          const header = document.createElement("div");
          header.className = "agent-card-header";
          const title = document.createElement("div");
          const heading = document.createElement("h2");
          heading.textContent = agent.name;
          title.append(heading);
          if (agent.description) {
            const description = document.createElement("p");
            description.className = "agent-description";
            description.textContent = agent.description;
            title.append(description);
          }
          const actions = document.createElement("div");
          actions.className = "agent-card-actions";
          actions.append(button("Edit", "button small", () => openForm(agent)));
          actions.append(button("Delete", "button small", async () => {
            if (!window.confirm(`Delete Agent “${agent.name}” and its models?`)) return;
            try { await request(`/api/agents/${encodeURIComponent(agent.id)}`, { method: "DELETE" }); await render(); }
            catch (err) { showNotice(error, err.message); }
          }));
          header.append(title, actions);
          card.append(header);
          const modelHeading = document.createElement("div");
          modelHeading.className = "model-heading";
          const modelTitle = document.createElement("h3");
          modelTitle.textContent = "Models";
          modelHeading.append(modelTitle, button("＋ Add model", "text-button", () => addModel(agent.id)));
          card.append(modelHeading);
          const modelList = document.createElement("div");
          try {
            const models = await request(`/api/agents/${encodeURIComponent(agent.id)}/models`);
            for (const model of models) modelList.append(modelRow(agent.id, model));
            if (!models.length) {
              const empty = document.createElement("p");
              empty.className = "muted";
              empty.textContent = "No models configured.";
              modelList.append(empty);
            }
          } catch (err) {
            const message = document.createElement("p");
            message.className = "notice error";
            message.textContent = err.message;
            modelList.append(message);
          }
          card.append(modelList);
          list.append(card);
        }
      } catch (err) {
        showNotice(error, err.message);
      }
    }

    function modelRow(agentId, model) {
      const row = document.createElement("div");
      row.className = "model-row";
      [model.name, model.model_id, model.provider].forEach((value) => {
        const cell = document.createElement("span");
        cell.textContent = value;
        row.append(cell);
      });
      const actions = document.createElement("div");
      actions.className = "model-row-actions";
      actions.append(button("Edit", "button small", () => editModel(model)));
      actions.append(button("Remove", "button small", async () => {
        try { await request(`/api/models/${encodeURIComponent(model.id)}`, { method: "DELETE" }); await render(); }
        catch (err) { showNotice(error, err.message); }
      }));
      row.append(actions);
      return row;
    }

    async function addModel(agentId, existing = null) {
      const modelName = window.prompt("Model name", existing?.name || "");
      if (modelName === null) return;
      const modelId = window.prompt("Model ID", existing?.model_id || "");
      if (modelId === null) return;
      const provider = window.prompt("Provider", existing?.provider || "ollama");
      if (provider === null) return;
      try {
        const body = { name: modelName.trim(), model_id: modelId.trim(), provider: provider.trim() || "ollama" };
        if (existing) await request(`/api/models/${encodeURIComponent(existing.id)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        else await request(`/api/agents/${encodeURIComponent(agentId)}/models`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        await render();
      } catch (err) { showNotice(error, err.message); }
    }

    function editModel(model) { addModel(model.agent_id, model); }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      hideNotice(error);
      const body = { name: nameInput.value.trim(), description: descriptionInput.value.trim() };
      try {
        if (idInput.value) await request(`/api/agents/${encodeURIComponent(idInput.value)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        else await request("/api/agents", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        closeForm();
        await render();
      } catch (err) { showNotice(error, err.message); }
    });
    render();
  }

  function setupRunForm() {
    const form = $("#run-form");
    if (!form) return;
    const agentSelect = $("#run-agent");
    const modelSelect = $("#run-model");
    const selectedItemsNode = $("#selected-items");
    const errorNode = $("#run-error");
    const noticeNode = $("#run-notice");
    const taskSelect = $("#run-task");
    const domainSelect = $("#run-domain");
    let domainIndex = JSON.parse($("#domain-index").textContent);
    const selectedItems = new Map();
    const files = new Map();
    const uploaded = new Set();
    const confirmedItems = new Set();
    const details = new Map();
    let activeRun = null;
    let runItems = new Map();
    let ontoQueue = [];
    let ontoIndex = 0;
    let activeConfirmation = null;

    async function loadAgents() {
      const agents = await request("/api/agents");
      for (const agent of agents) {
        const option = document.createElement("option");
        option.value = agent.id;
        option.textContent = agent.name;
        agentSelect.append(option);
      }
    }

    agentSelect.addEventListener("change", async () => {
      modelSelect.replaceChildren(new Option("Select model", ""));
      modelSelect.disabled = !agentSelect.value;
      if (!agentSelect.value) return;
      try {
        const models = await request(`/api/agents/${encodeURIComponent(agentSelect.value)}/models`);
        for (const model of models) modelSelect.add(new Option(`${model.name} (${model.model_id})`, model.id));
      } catch (err) { showNotice(errorNode, err.message); }
    });

    function selection() {
      return [...selectedItems.values()];
    }

    async function loadCount(item) {
      const key = itemKey(item);
      try {
        const detail = await request(`/api/catalog/${encodeURIComponent(item.task)}/${encodeURIComponent(item.domain)}`);
        details.set(key, detail);
        refreshSelectedCounts();
        renderSelected();
      } catch (err) { showNotice(errorNode, err.message); }
    }

    function renderSelected() {
      const current = selection();
      selectedItemsNode.replaceChildren();
      if (!current.length) {
        const empty = document.createElement("p");
        empty.className = "muted";
        empty.textContent = "Select one or more benchmark items.";
        selectedItemsNode.append(empty);
        return;
      }
      for (const item of current) {
        const key = itemKey(item);
        const detail = details.get(key);
        const row = document.createElement("div");
        row.className = "selected-item";
        row.dataset.itemKey = key;
        const title = document.createElement("div");
        title.className = "selected-item-title";
        const strong = document.createElement("strong");
        strong.textContent = `${item.domain.replaceAll("_", " ")} · ${item.task.toUpperCase()}`;
        const count = document.createElement("span");
        count.dataset.itemCount = item.task;
        count.textContent = detail ? `${cqCount(detail)} CQs` : "Loading CQ count…";
        title.append(strong, count);
        const uploadLabel = document.createElement("label");
        uploadLabel.textContent = item.task === "cq2term" ? "Prediction JSON" : "Ontology file";
        const upload = document.createElement("input");
        upload.type = "file";
        upload.required = true;
        upload.accept = item.task === "cq2term" ? ".json,application/json" : ".owl,.rdf,.xml,.ttl,.nt,.n3";
        upload.dataset.itemUpload = item.task;
        upload.dataset.uploadDomain = item.domain;
        upload.setAttribute("aria-label", `${item.task.toUpperCase()} prediction file for ${item.domain}`);
        upload.addEventListener("change", () => {
          if (upload.files[0]) files.set(key, upload.files[0]);
          else files.delete(key);
          const oldError = $(".upload-error", row);
          if (oldError) oldError.remove();
        });
        if (files.has(key)) {
          const transfer = new DataTransfer();
          transfer.items.add(files.get(key));
          upload.files = transfer.files;
        }
        uploadLabel.append(upload);
        const cqButton = document.createElement("button");
        cqButton.type = "button";
        cqButton.className = "text-button";
        cqButton.textContent = "View CQs";
        cqButton.addEventListener("click", () => openDrawer(item));
        const bundle = document.createElement("a");
        bundle.className = "button small";
        bundle.href = `/api/catalog/${encodeURIComponent(item.task)}/${encodeURIComponent(item.domain)}/bundle`;
        bundle.textContent = "Download CQs";
        bundle.setAttribute("aria-label", `Download ${item.task} CQ bundle for ${item.domain}`);
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "icon-button remove-item";
        remove.textContent = "×";
        remove.setAttribute("aria-label", `Remove ${item.task} ${item.domain}`);
        remove.disabled = Boolean(activeRun);
        remove.addEventListener("click", () => {
          selectedItems.delete(key);
          files.delete(key);
          renderSelected();
          refreshSelectedCounts();
        });
        const itemActions = document.createElement("div");
        itemActions.className = "selected-item-actions";
        itemActions.append(cqButton, bundle, remove);
        row.append(title, uploadLabel, itemActions);
        selectedItemsNode.append(row);
      }
    }

    function refreshSelectedCounts() {
      for (const task of ["cq2term", "cq2onto"]) {
        const total = selection().filter((item) => item.task === task).reduce((sum, item) => {
          const detail = details.get(itemKey(item));
          return sum + (detail ? cqCount(detail) : 0);
        }, 0);
        const target = $(`[data-cq-count-for="${task}"]`);
        if (target) target.textContent = `${total} CQs`;
      }
    }

    function refreshDomainOptions() {
      const prior = domainSelect.value;
      domainSelect.replaceChildren(new Option("Select domain", ""));
      for (const domain of domainIndex) {
        if (!domain.counts[taskSelect.value]) continue;
        domainSelect.add(new Option(domain.name, domain.slug));
      }
      if ([...domainSelect.options].some((option) => option.value === prior)) domainSelect.value = prior;
    }

    async function loadDomainIndex() {
      try {
        domainIndex = await request("/api/catalog");
        refreshDomainOptions();
        const requestedDomain = new URLSearchParams(window.location.search).get("domain");
        if (requestedDomain && [...domainSelect.options].some((option) => option.value === requestedDomain)) domainSelect.value = requestedDomain;
      } catch (err) { showNotice(errorNode, err.message); }
    }

    $("#add-item").addEventListener("click", async () => {
      hideNotice(errorNode);
      const item = { task: taskSelect.value, domain: domainSelect.value };
      if (!item.domain) { showNotice(errorNode, "Select a domain."); return; }
      const key = itemKey(item);
      if (selectedItems.has(key)) { showNotice(errorNode, "That task and domain are already selected."); return; }
      selectedItems.set(key, item);
      renderSelected();
      refreshSelectedCounts();
      await loadCount(item);
    });
    taskSelect.addEventListener("change", refreshDomainOptions);

    const drawer = $("#cq-drawer");
    const scrim = $("#drawer-scrim");
    const modal = $("#confirmation-modal");
    const closeDrawer = () => { drawer.hidden = true; scrim.hidden = true; };
    const showModal = () => { modal.hidden = false; };
    const closeModal = () => { modal.hidden = true; };
    $$('[data-close-drawer]', drawer).forEach((button) => button.addEventListener("click", closeDrawer));
    scrim.addEventListener("click", closeDrawer);
    $("#close-confirmation").addEventListener("click", closeModal);
    $("#cancel-confirmation").addEventListener("click", closeModal);
    $("#open-checklist").addEventListener("click", (event) => {
      event.preventDefault();
      if (activeConfirmation) openDrawer(activeConfirmation.item);
    });

    async function openDrawer(item) {
      hideNotice(errorNode);
      closeModal();
      drawer.hidden = false;
      scrim.hidden = false;
      $("#drawer-domain").textContent = item.domain;
      $("#drawer-tabs").replaceChildren();
      $("#drawer-content").replaceChildren();
      const tasks = selection().filter((selected) => selected.domain === item.domain).map((selected) => selected.task);
      if (!tasks.includes(item.task)) tasks.unshift(item.task);
      const uniqueTasks = [...new Set(tasks)];
      for (const task of uniqueTasks) {
        const detail = details.get(itemKey({ task, domain: item.domain })) || await request(`/api/catalog/${encodeURIComponent(task)}/${encodeURIComponent(item.domain)}`);
        details.set(itemKey({ task, domain: item.domain }), detail);
        const tab = document.createElement("button");
        tab.type = "button";
        tab.setAttribute("role", "tab");
        tab.dataset.drawerTask = task;
        tab.setAttribute("aria-selected", String(task === item.task));
        tab.textContent = `${task.toUpperCase()} ${cqCount(detail)}`;
        tab.addEventListener("click", () => showDrawerTask(task, item.domain));
        $("#drawer-tabs").append(tab);
      }
      showDrawerTask(item.task, item.domain);
    }

    function showDrawerTask(task, domain) {
      const detail = details.get(itemKey({ task, domain }));
      const host = $("#drawer-content");
      host.replaceChildren();
      $$('[data-drawer-task]', $("#drawer-tabs")).forEach((tab) => tab.setAttribute("aria-selected", String(tab.dataset.drawerTask === task)));
      const meta = document.createElement("div");
      meta.className = "cq-panel-meta";
      const count = document.createElement("strong");
      count.textContent = `${cqCount(detail)} CQs`;
      const bundle = document.createElement("a");
      bundle.className = "button small";
      bundle.href = `/api/catalog/${encodeURIComponent(task)}/${encodeURIComponent(domain)}/bundle`;
      bundle.textContent = "Download bundle";
      meta.append(count, bundle);
      host.append(meta);
      const list = document.createElement("ol");
      list.className = task === "cq2onto" && activeConfirmation?.item.domain === domain ? "cq-checklist" : "cq-list";
      for (const cq of detail.cqs) {
        const li = document.createElement("li");
        if (task === "cq2onto" && activeConfirmation?.item.domain === domain) {
          li.className = "cq-check";
          const checkbox = document.createElement("input");
          checkbox.type = "checkbox";
          checkbox.value = cq.id;
          checkbox.checked = activeConfirmation.confirmedIds.has(cq.id);
          checkbox.addEventListener("change", () => {
            checkbox.checked ? activeConfirmation.confirmedIds.add(cq.id) : activeConfirmation.confirmedIds.delete(cq.id);
            activeConfirmation.saved = false;
            updateConfirmationProgress();
          });
          const text = document.createElement("div");
          const id = document.createElement("code");
          id.textContent = cq.id;
          const question = document.createElement("p");
          question.textContent = cq.question;
          text.append(id, question);
          li.append(checkbox, text);
        } else {
          const id = document.createElement("code");
          id.textContent = cq.id;
          const question = document.createElement("p");
          question.textContent = cq.question;
          li.append(id, question);
        }
        list.append(li);
      }
      host.append(list);
      const footer = $(".drawer-footer");
      const confirmButton = $("#save-confirmation");
      const isConfirmList = task === "cq2onto" && activeConfirmation?.item.domain === domain;
      footer.hidden = !isConfirmList;
      confirmButton.disabled = !allConfirmed(detail.cqs, activeConfirmation?.confirmedIds || new Set());
      updateConfirmationProgress();
    }

    function allConfirmed(cqs, confirmedIds) {
      const expectedIds = cqs.map((cq) => cq.id);
      return expectedIds.length > 0 && expectedIds.every((id) => confirmedIds.has(id)) && confirmedIds.size === expectedIds.length;
    }

    function updateConfirmationProgress() {
      const item = activeConfirmation?.item;
      if (!item) return;
      const detail = details.get(itemKey(item));
      const count = activeConfirmation.confirmedIds.size;
      $("#drawer-progress").textContent = `${count} / ${cqCount(detail)} provided`;
      $("#confirmation-count").textContent = `${count} / ${cqCount(detail)}`;
      $("#save-confirmation").disabled = !allConfirmed(detail.cqs, activeConfirmation.confirmedIds);
      $("#accept-confirmation").disabled = !activeConfirmation.saved;
    }

    $("#save-confirmation").addEventListener("click", async () => {
      if (!activeConfirmation) return;
      const { item, runItem } = activeConfirmation;
      try {
        await request(`/api/runs/${encodeURIComponent(activeRun.id)}/items/${encodeURIComponent(runItem.id)}/confirmation`, {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirmed_ids: [...activeConfirmation.confirmedIds] }),
        });
        activeConfirmation.saved = true;
        confirmedItems.add(itemKey(item));
        updateConfirmationProgress();
        closeDrawer();
        showModal();
      } catch (err) { showNotice(errorNode, err.message); }
    });

    async function beginConfirmations() {
      ontoQueue = [...runItems.entries()].filter(([key]) => key.startsWith("cq2onto:") && !confirmedItems.has(key));
      ontoIndex = 0;
      if (!ontoQueue.length) return uploadAndStart();
      presentConfirmation();
    }

    function presentConfirmation() {
      if (ontoIndex >= ontoQueue.length) {
        closeModal();
        activeConfirmation = null;
        uploadAndStart();
        return;
      }
      const [key, runItem] = ontoQueue[ontoIndex];
      const [task, domain] = key.split(":");
      const item = { task, domain };
      const detail = details.get(key);
      activeConfirmation = { item, runItem, confirmedIds: new Set(), saved: false };
      $("#confirmation-title").textContent = `Confirm ${domain.replaceAll("_", " ")} CQs provided`;
      updateConfirmationProgress();
      showModal();
    }

    $("#accept-confirmation").addEventListener("click", () => {
      if (!activeConfirmation?.saved) return;
      ontoIndex += 1;
      presentConfirmation();
    });

    async function uploadAndStart() {
      hideNotice(errorNode);
      const button = $("#prepare-run");
      button.disabled = true;
      const pickerButton = $("#add-item");
      pickerButton.disabled = Boolean(activeRun);
      let currentKey = null;
      try {
        for (const [key, runItem] of runItems) {
          currentKey = key;
          if (uploaded.has(key)) continue;
          const file = files.get(key);
          if (!file) throw new Error(`Choose a file for ${key.replace(":", " · ")}.`);
          const body = new FormData();
          body.append("file", file);
          await request(`/api/runs/${encodeURIComponent(activeRun.id)}/items/${encodeURIComponent(runItem.id)}/upload`, { method: "POST", body });
          uploaded.add(key);
        }
        const queued = await request(`/api/runs/${encodeURIComponent(activeRun.id)}/start`, { method: "POST" });
        showNotice(noticeNode, "Run queued.");
        window.location.assign(`/runs/${encodeURIComponent(queued.id)}`);
      } catch (err) {
        showNotice(errorNode, err.message);
        if (currentKey) {
          const row = $(`[data-item-key="${currentKey}"]`, selectedItemsNode);
          if (row) {
            const message = document.createElement("span");
            message.className = "upload-error";
            message.textContent = err.message;
            row.append(message);
          }
        }
      } finally { button.disabled = false; }
    }

    $("#prepare-run").addEventListener("click", async () => {
      hideNotice(errorNode);
      hideNotice(noticeNode);
      if (activeRun) {
        const incomplete = [...runItems.keys()].filter((key) => key.startsWith("cq2onto:") && !files.has(key));
        if (incomplete.length) {
          showNotice(errorNode, `Choose a file for ${incomplete[0].replace(":", " · ")}.`);
          return;
        }
        beginConfirmations();
        return;
      }
      const items = selection();
      if (!agentSelect.value || !modelSelect.value) { showNotice(errorNode, "Select an Agent and model."); return; }
      if (!items.length) { showNotice(errorNode, "Select at least one benchmark item."); return; }
      const missing = items.find((item) => !files.has(itemKey(item)));
      if (missing) { showNotice(errorNode, `Choose a file for ${itemKey(missing)}.`); return; }
      if (items.some((item) => !details.has(itemKey(item)))) {
        await Promise.all(items.map((item) => details.has(itemKey(item)) ? Promise.resolve() : loadCount(item)));
      }
      try {
        activeRun = await request("/api/runs", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ agent_id: agentSelect.value, model_id: modelSelect.value, items, config: {} }),
        });
        runItems = new Map(activeRun.items.map((item) => [itemKey(item), item]));
        agentSelect.disabled = true;
        modelSelect.disabled = true;
        taskSelect.disabled = true;
        domainSelect.disabled = true;
        renderSelected();
        await beginConfirmations();
      } catch (err) { showNotice(errorNode, err.message); activeRun = null; }
    });

    loadAgents().catch((err) => showNotice(errorNode, err.message));
    refreshDomainOptions();
    loadDomainIndex();
    const requestedDomain = new URLSearchParams(window.location.search).get("domain");
    if (requestedDomain && [...domainSelect.options].some((option) => option.value === requestedDomain)) domainSelect.value = requestedDomain;
    renderSelected();
  }

  setupDomainDrawer();
  setupAgents();
  setupRunForm();
})();
