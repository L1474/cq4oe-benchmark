(() => {
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const itemKey = ({ task, domain }) => `${task}:${domain}`;
  const cqCount = (detail) => detail.cq_count ?? detail.count;
  const TASK_LABELS = { cq2term: "CQ2Term", cq2onto: "CQ2Onto" };
  const STATUS_LABELS = {
    draft: "草稿", queued: "排队中", running: "运行中", completed: "已完成", partial: "部分完成", failed: "失败",
    pending: "待处理", blocked: "已阻塞", started: "已开始",
  };
  const STAGE_LABELS = {
    evaluate: "评测", class: "类评测", property: "属性评测", triple: "三元组评测",
    atomic: "原子 TBox 提取", axiom: "公理评测", hierarchy: "层级闭包评测",
  };
  const DIMENSION_LABELS = {
    term: "词项", class: "类", property: "属性", property_characteristic: "属性特征",
    class_hierarchy: "类层级", property_hierarchy: "属性层级",
    ClassProperty: "类与属性", PropertyCharacteristics: "属性特征", Triple: "三元组", Axiom: "公理",
    HierarchyClosure: "层级闭包", CQCoverage: "CQ 覆盖率", class_property: "类与属性",
    property_characteristics: "属性特征", triple: "三元组", axiom: "公理", hierarchy: "层级闭包", cq_coverage: "CQ 覆盖率",
  };
  const METRIC_LABELS = {
    any_cq_coverage: "至少一项 CQ 覆盖率", fully_cq_coverage: "完全 CQ 覆盖率",
    average_cq_coverage: "平均 CQ 覆盖率",
    hard_match: "硬匹配", sequence_match: "序列匹配", levenshtein_distance: "Levenshtein 距离",
    jaro_winkler_distance: "Jaro-Winkler 距离", semantic_cosine_similarity: "语义余弦相似度",
    aggregated_top3: "Top-3 聚合", precision: "精确率", recall: "召回率", f1: "F1",
    embedding_diagnostic: "嵌入诊断", at_least_one_coverage: "至少一项覆盖率", mean_coverage: "平均覆盖率",
    full_coverage: "完整覆盖率", closure_rescue_coverage: "闭包补救覆盖率", coverage: "覆盖率",
  };
  const LAYER_LABELS = {
    terms: "全领域词项", aggregated: "综合对齐", characteristics: "属性特征", cq_coverage: "CQ 覆盖",
    closure: "推理闭包", layer2_semantic: "第 2 层（语义诊断）", layer4_global: "第 4 层（全局）",
    layer1: "第 1 层", layer2: "第 2 层", layer3: "第 3 层", layer4: "第 4 层", layer5: "第 5 层", layer6: "第 6 层",
    layer1_exact: "第 1 层（精确）", layer2_pair: "第 2 层（配对）", layer3_strict: "第 3 层（严格）",
    layer4_atomic: "第 4 层（原子）", layer5_closure: "第 5 层（闭包）", layer6_cq: "第 6 层（CQ）",
  };
  const SCOPE_LABELS = {
    combined: "类与属性合并", class_only: "仅类", property_only: "仅属性", aggregate: "综合",
    semantic: "语义诊断", strict: "严格匹配", per_cq_mean: "逐题平均",
    global: "整体", per_cq: "按 CQ", per_item: "按条目", alignment_conditioned: "在对齐条件下",
    gold_vocabulary: "金标准词汇", predicted_vocabulary: "预测词汇", closure: "推理闭包",
  };
  const label = (value, mapping) => mapping[value] || value || "";
  const taskLabel = (value) => label(value, TASK_LABELS);
  const statusLabel = (value) => label(value, STATUS_LABELS);
  const dimensionLabel = (value) => label(value, DIMENSION_LABELS);
  const metricLabel = (value) => label(value, METRIC_LABELS);
  const layerLabel = (value) => label(value, LAYER_LABELS);
  const scopeLabel = (value) => value?.startsWith("cq:") ? `${value.slice(3)}（逐题）` : label(value, SCOPE_LABELS);
  const scoreText = (value) => value == null || !Number.isFinite(Number(value)) ? "—" : Number(value).toFixed(2);
  const deltaText = (value) => {
    if (value === 0) return "0.00";
    const sign = value > 0 ? "+" : "−";
    return `${sign}${Math.abs(value) < 0.005 ? "<0.01" : Math.abs(value).toFixed(2)}`;
  };
  const localizeError = (message, status) => {
    const text = String(message || "");
    const replacements = [
      [/Select an Agent and model\./, "请选择 Agent 和模型。"],
      [/Select at least one benchmark item\./, "请至少选择一个评测条目。"],
      [/Select a domain\./, "请选择领域。"],
      [/That task and domain are already selected\./, "该任务和领域已经选择。"],
      [/Choose a file for /, "请选择文件："],
      [/Run queued\./, "运行已进入队列。"],
      [/No runs match these filters\./, "没有符合筛选条件的运行记录。"],
      [/No comparable run/, "没有可对比的运行记录"],
      [/Server rejected confirmation/, "服务器拒绝了 CQ 确认。"],
      [/Keep draft for retry/, "请保留草稿并重试。"],
      [/Missing gold input required for provenance: /, "缺少评测所需的金标准输入："],
      [/A run must contain at least one item\./, "一次运行至少需要一个评测条目。"],
      [/Unsupported task: /, "不支持的任务："],
      [/Invalid task or domain: /, "任务或领域无效："],
      [/Agent not found\./, "找不到 Agent。"],
      [/A model is required for the selected Agent\./, "所选 Agent 必须配置模型。"],
      [/Model does not belong to the selected Agent\./, "该模型不属于所选 Agent。"],
      [/Run item not found\./, "找不到运行条目。"],
      [/Uploads and confirmations are allowed only for draft runs\./, "只有草稿状态的运行可以上传文件或确认 CQ。"],
      [/Invalid upload filename\./, "上传文件名无效。"],
      [/Unsupported file extension for /, "不支持的文件扩展名："],
      [/Upload exceeds configured size limit\./, "上传文件超过大小限制。"],
      [/CQ2Term upload is not valid UTF-8 JSON\./, "CQ2Term 上传文件不是有效的 UTF-8 JSON。"],
      [/CQ2Term upload is invalid: /, "CQ2Term 上传文件无效："],
      [/Ontology upload cannot be parsed: /, "无法解析本体上传文件："],
      [/CQ confirmation applies only to CQ2Onto items\./, "CQ 确认只适用于 CQ2Onto 条目。"],
      [/CQ confirmation is incomplete: /, "CQ 确认未完成："],
      [/CQ review applies only to CQ2Onto items\./, "CQ 清单已阅仅适用于 CQ2Onto 条目。"],
      [/CQ review requires a non-empty question list\./, "该领域没有可供浏览的 CQ。"],
      [/requires CQ review confirmation\./, "需要先浏览 CQ 清单并继续。"],
      [/Run is not a draft\./, "运行不是草稿状态。"],
      [/requires an upload\./, "需要先上传文件。"],
      [/requires complete CQ confirmation\./, "需要完成全部 CQ 确认。"],
      [/Run item upload is not valid: /, "运行条目上传文件无效："],
      [/selected runs must use compatible task and configuration scopes/, "所选运行必须使用兼容的任务和配置范围。"],
      [/selected runs must use matching gold fingerprints/, "所选运行的金标准指纹必须一致。"],
      [/selected runs have no shared task\/domain items/, "所选运行没有共同的任务 / 领域条目。"],
      [/selected runs must use matching evaluator versions/, "所选运行必须使用相同的评测器版本。"],
      [/Domain not found/, "找不到领域。"],
      [/Task not found for domain/, "该领域没有此任务。"],
      [/CQ bundle not found/, "找不到 CQ 包。"],
      [/Artifact file not found/, "找不到产物文件。"],
      [/Artifact not found/, "找不到产物。"],
      [/Request failed \((\d+)\)/, "请求失败（HTTP $1）"],
    ];
    for (const [pattern, replacement] of replacements) if (pattern.test(text)) return text.replace(pattern, replacement);
    return text || `请求失败（HTTP ${status}）`;
  };

  async function request(url, options = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
      let message = `请求失败（HTTP ${response.status}）`;
      try {
        const body = await response.json();
        message = localizeError(body.detail || body.message || message, response.status);
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

  function handleDialogKeys(event, dialog, close) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = $$('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex="0"]', dialog)
      .filter((node) => !node.closest("[hidden]"));
    if (!focusable.length) {
      event.preventDefault();
      dialog.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!dialog.contains(document.activeElement)) {
      event.preventDefault();
      first.focus();
    } else if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function setupDomainDrawer() {
    const drawer = $("#cq-drawer");
    if (!drawer || !$("#domain-data")) return;
    const scrim = $("#drawer-scrim");
    let drawerOpener = null;
    const close = () => {
      drawer.hidden = true;
      scrim.hidden = true;
      drawerOpener?.focus();
    };
    const open = () => {
      drawerOpener = document.activeElement;
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
    document.addEventListener("keydown", (event) => { if (!drawer.hidden) handleDialogKeys(event, drawer, close); });
  }

  function setupEvaluationGuideTabs() {
    $$('[data-guide-tabs] [role="tablist"], .guide-tab-panel [role="tablist"]').forEach((tablist) => {
      const scope = tablist.closest("[role=tabpanel]") || tablist.closest("[data-guide-tabs]");
      const tabs = $$('[role="tab"][aria-controls]', tablist);
      const select = (tab, focus = false) => {
        for (const candidate of tabs) {
          const selected = candidate === tab;
          candidate.setAttribute("aria-selected", String(selected));
          candidate.tabIndex = selected ? 0 : -1;
          const panel = $(`#${candidate.getAttribute("aria-controls")}`, scope);
          if (panel) panel.hidden = !selected;
        }
        if (focus) tab.focus();
      };
      tabs.forEach((tab) => tab.addEventListener("click", () => select(tab)));
      tablist.addEventListener("keydown", (event) => {
        const current = tabs.indexOf(document.activeElement);
        if (current < 0 || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1
          : (current + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length;
        select(tabs[next], true);
      });
      const initiallySelected = tabs.find((tab) => tab.getAttribute("aria-selected") === "true") || tabs[0];
      if (initiallySelected) select(initiallySelected);
    });
  }

  setupEvaluationGuideTabs();

  function setupAgents() {
    const list = $("#agents-list");
    const form = $("#agent-form");
    const modelForm = $("#model-form");
    if (!list || !form || !modelForm) return;
    const error = $("#agent-error");
    const nameInput = $("#agent-name");
    const descriptionInput = $("#agent-description");
    const idInput = $("#agent-id");
    const modelIdInput = $("#model-id");
    const modelAgentIdInput = $("#model-agent-id");
    const modelNameInput = $("#model-name");

    const button = (label, className, action) => {
      const element = document.createElement("button");
      element.type = "button";
      element.className = className;
      element.textContent = label;
      element.addEventListener("click", action);
      return element;
    };

    const openForm = (agent = null) => {
      modelForm.hidden = true;
      idInput.value = agent?.id || "";
      nameInput.value = agent?.name || "";
      descriptionInput.value = agent?.description || "";
      $("#agent-form-title").textContent = agent ? "编辑 Agent" : "新建 Agent";
      form.hidden = false;
      nameInput.focus();
    };
    const closeForm = () => { form.hidden = true; };
    const closeModelForm = () => { modelForm.hidden = true; };
    $("#new-agent").addEventListener("click", () => openForm());
    $("#cancel-agent").addEventListener("click", closeForm);
    $("#cancel-agent-secondary").addEventListener("click", closeForm);
    $("#cancel-model").addEventListener("click", closeModelForm);
    $("#cancel-model-secondary").addEventListener("click", closeModelForm);

    function openModelForm(agentId, existing = null) {
      form.hidden = true;
      modelIdInput.value = existing?.id || "";
      modelAgentIdInput.value = agentId;
      modelNameInput.value = existing?.name || "";
      $("#model-form-title").textContent = existing ? "编辑模型标签" : "添加模型标签";
      modelForm.hidden = false;
      modelNameInput.focus();
    }

    async function render() {
      list.replaceChildren();
      try {
        const agents = await request("/api/agents");
        if (!agents.length) {
          const empty = document.createElement("p");
          empty.className = "muted";
          empty.textContent = "暂未配置 Agent。";
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
          actions.append(button("编辑", "button small", () => openForm(agent)));
          actions.append(button("删除", "button small", async () => {
            if (!window.confirm(`确定删除 Agent“${agent.name}”及其模型吗？`)) return;
            try { await request(`/api/agents/${encodeURIComponent(agent.id)}`, { method: "DELETE" }); await render(); }
            catch (err) { showNotice(error, err.message); }
          }));
          header.append(title, actions);
          card.append(header);
          const modelHeading = document.createElement("div");
          modelHeading.className = "model-heading";
          const modelTitle = document.createElement("h3");
          modelTitle.textContent = "模型";
          modelHeading.append(modelTitle, button("＋ 添加模型标签", "text-button", () => openModelForm(agent.id)));
          card.append(modelHeading);
          const modelList = document.createElement("div");
          try {
            const models = await request(`/api/agents/${encodeURIComponent(agent.id)}/models`);
            for (const model of models) modelList.append(modelRow(agent.id, model));
            if (!models.length) {
              const empty = document.createElement("p");
              empty.className = "muted";
              empty.textContent = "暂未配置模型。";
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
      const name = document.createElement("strong");
      name.textContent = model.name;
      const actions = document.createElement("div");
      actions.className = "model-row-actions";
      actions.append(button("编辑", "button small", () => openModelForm(agentId, model)));
      actions.append(button("移除", "button small", async () => {
        try { await request(`/api/models/${encodeURIComponent(model.id)}`, { method: "DELETE" }); await render(); }
        catch (err) { showNotice(error, err.message); }
      }));
      row.append(name, actions);
      return row;
    }

    modelForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      hideNotice(error);
      const name = modelNameInput.value.trim();
      if (!name) { showNotice(error, "请输入模型名称。 "); return; }
      const body = { name };
      try {
        if (modelIdInput.value) await request(`/api/models/${encodeURIComponent(modelIdInput.value)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        else await request(`/api/agents/${encodeURIComponent(modelAgentIdInput.value)}/models`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        closeModelForm();
        await render();
      } catch (err) { showNotice(error, err.message); }
    });

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
    const reviewedItems = new Set();
    const details = new Map();
    let activeRun = null;
    let runItems = new Map();
    let ontoQueue = [];
    let ontoIndex = 0;
    let activeConfirmation = null;
    let reviewPending = false;
    let modelRequest = 0;
    let submissionPending = false;
    let uploadPending = false;

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
      const selectedAgent = agentSelect.value;
      const requestId = ++modelRequest;
      modelSelect.replaceChildren(new Option("选择模型", ""));
      modelSelect.disabled = true;
      if (!selectedAgent) return;
      try {
        const models = await request(`/api/agents/${encodeURIComponent(selectedAgent)}/models`);
        if (requestId !== modelRequest || agentSelect.value !== selectedAgent) return;
        for (const model of models) modelSelect.add(new Option(model.name, model.id));
        modelSelect.disabled = false;
      } catch (err) {
        if (requestId === modelRequest && agentSelect.value === selectedAgent) showNotice(errorNode, err.message);
      }
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
        empty.textContent = "请先选择一个或多个评测条目。";
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
        strong.textContent = `${item.domain.replaceAll("_", " ")} · ${taskLabel(item.task)}`;
        const count = document.createElement("span");
        count.dataset.itemCount = item.task;
        count.textContent = detail ? `${cqCount(detail)} 个 CQ` : "正在加载 CQ 数量…";
        title.append(strong, count);
        const uploadLabel = document.createElement("label");
        uploadLabel.textContent = item.task === "cq2term" ? "预测 JSON 文件" : "本体文件";
        const upload = document.createElement("input");
        upload.type = "file";
        upload.required = true;
        upload.accept = item.task === "cq2term" ? ".json,application/json" : ".owl,.rdf,.xml,.ttl,.nt,.n3";
        upload.dataset.itemUpload = item.task;
        upload.dataset.uploadDomain = item.domain;
        upload.setAttribute("aria-label", `${taskLabel(item.task)} 在 ${item.domain} 的预测文件`);
        upload.addEventListener("change", () => {
          if (upload.files[0]) files.set(key, upload.files[0]);
          else files.delete(key);
          uploaded.delete(key);
          const oldError = $(".upload-error", row);
          if (oldError) oldError.remove();
        });
        if (files.has(key)) {
          const transfer = new DataTransfer();
          transfer.items.add(files.get(key));
          upload.files = transfer.files;
        }
        uploadLabel.append(upload);
        const uploadHint = document.createElement("span");
        uploadHint.className = "upload-hint";
        uploadHint.textContent = item.task === "cq2term"
          ? "填写 CQ 包中的 prediction_template.json，覆盖全部 CQ ID。"
          : "上传该领域最终合并的本体；normal / cqbycq / agent 只表示生成方法，log 不必上传。";
        uploadLabel.append(uploadHint);
        const cqButton = document.createElement("button");
        cqButton.type = "button";
        cqButton.className = "text-button";
        cqButton.textContent = "查看 CQ";
        cqButton.addEventListener("click", () => openDrawer(item));
        const bundle = document.createElement("a");
        bundle.className = "button small";
        bundle.href = `/api/catalog/${encodeURIComponent(item.task)}/${encodeURIComponent(item.domain)}/bundle`;
        bundle.textContent = "下载 CQ 包";
        bundle.setAttribute("aria-label", `下载 ${item.domain} 的 ${taskLabel(item.task)} CQ 包`);
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "icon-button remove-item";
        remove.textContent = "×";
        remove.setAttribute("aria-label", `移除 ${taskLabel(item.task)} ${item.domain}`);
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
        if (target) target.textContent = `${total} 个 CQ`;
      }
    }

    function refreshDomainOptions() {
      const prior = domainSelect.value;
      domainSelect.replaceChildren(new Option("选择领域", ""));
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
      if (!item.domain) { showNotice(errorNode, "请选择领域。"); return; }
      const key = itemKey(item);
      if (selectedItems.has(key)) { showNotice(errorNode, "该任务和领域已经选择。"); return; }
      selectedItems.set(key, item);
      renderSelected();
      refreshSelectedCounts();
      await loadCount(item);
    });
    taskSelect.addEventListener("change", refreshDomainOptions);

    const drawer = $("#cq-drawer");
    const scrim = $("#drawer-scrim");
    const modal = $("#confirmation-modal");
    let drawerOpener = null;
    let modalOpener = null;
    let drawerReturnsToModal = false;
    const closeDrawer = () => {
      drawer.hidden = true;
      scrim.hidden = true;
      if (drawerReturnsToModal) {
        drawerReturnsToModal = false;
        modal.hidden = false;
        $("#open-checklist").focus();
      } else drawerOpener?.focus();
    };
    const showModal = () => {
      if (modal.hidden) modalOpener = document.activeElement;
      modal.hidden = false;
      $("#review-list").focus();
    };
    const closeModal = (restoreFocus = true) => {
      if (reviewPending) return;
      modal.hidden = true;
      if (restoreFocus) {
        $("#prepare-run").disabled = submissionPending || uploadPending;
        modalOpener?.focus();
      }
    };
    document.addEventListener("keydown", (event) => {
      if (!drawer.hidden) handleDialogKeys(event, drawer, closeDrawer);
      else if (!modal.hidden) handleDialogKeys(event, modal, closeModal);
    });
    $$('[data-close-drawer]', drawer).forEach((button) => button.addEventListener("click", closeDrawer));
    scrim.addEventListener("click", closeDrawer);
    $("#close-confirmation").addEventListener("click", closeModal);
    $("#cancel-confirmation").addEventListener("click", closeModal);
    $("#open-checklist").addEventListener("click", (event) => {
      event.preventDefault();
      if (reviewPending) return;
      if (activeConfirmation) openDrawer(activeConfirmation.item);
    });

    async function openDrawer(item) {
      hideNotice(errorNode);
      drawerReturnsToModal = !modal.hidden;
      drawerOpener = document.activeElement;
      if (drawerReturnsToModal) closeModal(false);
      drawer.hidden = false;
      scrim.hidden = false;
      $('[data-close-drawer]', drawer).focus();
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
        tab.textContent = `${taskLabel(task)} ${cqCount(detail)} 个`;
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
      count.textContent = `${cqCount(detail)} 个 CQ`;
      const bundle = document.createElement("a");
      bundle.className = "button small";
      bundle.href = `/api/catalog/${encodeURIComponent(task)}/${encodeURIComponent(domain)}/bundle`;
      bundle.textContent = "下载 CQ 包";
      meta.append(count, bundle);
      host.append(meta);
      const format = document.createElement("p");
      format.className = "input-format";
      format.textContent = task === "cq2term"
        ? "预测产物格式：UTF-8 JSON，包含 CQ ID 以及 class/property 词项列表"
        : "预测产物格式：OWL、RDF/XML、Turtle、N-Triples 或 N3";
      host.append(format);
      const list = document.createElement("ol");
      list.className = "cq-list";
      for (const cq of detail.cqs) {
        const li = document.createElement("li");
        const id = document.createElement("code");
        id.textContent = cq.id;
        const question = document.createElement("p");
        question.textContent = cq.question;
        li.append(id, question);
        list.append(li);
      }
      host.append(list);
    }

    async function beginConfirmations() {
      ontoQueue = [...runItems.entries()].filter(([key]) => key.startsWith("cq2onto:") && !reviewedItems.has(key));
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
      activeConfirmation = { item, runItem };
      $("#confirmation-title").textContent = `浏览 ${domain.replaceAll("_", " ")} 的 CQ 清单`;
      $("#confirmation-count").textContent = String(cqCount(detail));
      hideNotice($("#confirmation-error"));
      const host = $("#review-list");
      const list = document.createElement("ol");
      list.className = "cq-list";
      for (const cq of detail.cqs) {
        const row = document.createElement("li");
        const id = document.createElement("code"); id.textContent = cq.id;
        const question = document.createElement("p"); question.textContent = cq.question;
        row.append(id, question);
        list.append(row);
      }
      host.replaceChildren(list);
      host.scrollTop = 0;
      $("#accept-confirmation").disabled = false;
      showModal();
    }

    $("#accept-confirmation").addEventListener("click", async () => {
      if (!activeConfirmation || reviewPending) return;
      const { item, runItem } = activeConfirmation;
      const button = $("#accept-confirmation");
      reviewPending = true;
      button.disabled = true;
      hideNotice($("#confirmation-error"));
      try {
        await request(`/api/runs/${encodeURIComponent(activeRun.id)}/items/${encodeURIComponent(runItem.id)}/review`, { method: "PUT" });
        reviewedItems.add(itemKey(item));
        reviewPending = false;
        ontoIndex += 1;
        presentConfirmation();
      } catch (err) {
        reviewPending = false;
        button.disabled = false;
        const inlineError = $("#confirmation-error");
        showNotice(inlineError, err.message);
        inlineError.focus();
      }
    });

    async function uploadAndStart() {
      if (uploadPending) return;
      uploadPending = true;
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
          if (!file) throw new Error(`请选择文件：${key.replace(":", " · ")}。`);
          const body = new FormData();
          body.append("file", file);
          await request(`/api/runs/${encodeURIComponent(activeRun.id)}/items/${encodeURIComponent(runItem.id)}/upload`, { method: "POST", body });
          uploaded.add(key);
        }
        const queued = await request(`/api/runs/${encodeURIComponent(activeRun.id)}/start`, { method: "POST" });
        showNotice(noticeNode, "运行已进入队列。");
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
      } finally {
        uploadPending = false;
        button.disabled = false;
      }
    }

    $("#prepare-run").addEventListener("click", async () => {
      if (submissionPending || uploadPending || !modal.hidden || !drawer.hidden) return;
      hideNotice(errorNode);
      hideNotice(noticeNode);
      if (activeRun) {
        const incomplete = [...runItems.keys()].filter((key) => key.startsWith("cq2onto:") && !files.has(key));
        if (incomplete.length) {
          showNotice(errorNode, `请选择文件：${incomplete[0].replace(":", " · ")}。`);
          return;
        }
        await beginConfirmations();
        return;
      }
      const items = selection();
      if (!agentSelect.value || !modelSelect.value) { showNotice(errorNode, "请选择 Agent 和模型。"); return; }
      if (!items.length) { showNotice(errorNode, "请至少选择一个评测条目。"); return; }
      const missing = items.find((item) => !files.has(itemKey(item)));
      if (missing) { showNotice(errorNode, `请选择文件：${itemKey(missing)}。`); return; }
      submissionPending = true;
      const prepareButton = $("#prepare-run");
      prepareButton.disabled = true;
      try {
        if (items.some((item) => !details.has(itemKey(item)))) {
          await Promise.all(items.map((item) => details.has(itemKey(item)) ? Promise.resolve() : loadCount(item)));
        }
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
      finally {
        submissionPending = false;
        prepareButton.disabled = !modal.hidden || uploadPending;
      }
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

  function setupRunDetail() {
    const summary = $(".detail-summary[data-run-id]");
    if (!summary || !["queued", "running"].includes(summary.dataset.runStatus)) return;
    const path = window.location.pathname;
    const refresh = async () => {
      if (window.location.pathname !== path) return;
      try {
        const response = await fetch(path, { headers: { Accept: "text/html" } });
        if (!response.ok) throw new Error(`运行详情刷新失败（HTTP ${response.status}）`);
        const next = new DOMParser().parseFromString(await response.text(), "text/html");
        const nextSummary = next.querySelector(".detail-summary[data-run-id]");
        const currentSummary = $(".detail-summary[data-run-id]");
        const nextSections = [...next.querySelectorAll("main.page-content > .detail-section")];
        const currentSections = $$("main.page-content > .detail-section");
        if (!nextSummary || nextSummary.dataset.runId !== summary.dataset.runId ||
            nextSections.length !== currentSections.length) throw new Error("Run detail response is incomplete");
        currentSummary.replaceWith(nextSummary);
        currentSections.forEach((section, index) => section.replaceWith(nextSections[index]));
        if (["queued", "running"].includes(nextSummary.dataset.runStatus)) setTimeout(refresh, 1000);
      } catch (error) {
        if (window.location.pathname === path) setTimeout(refresh, 1000);
      }
    };
    setTimeout(refresh, 1000);
  }

  setupRunDetail();

  function setupRunLogs() {
    const drawer = $("#log-drawer");
    if (!drawer) return;
    const scrim = $("#log-scrim");
    const list = $("#log-events");
    const status = $("#log-status");
    const stageFilter = $("#log-stage-filter");
    const streamFilter = $("#log-stream-filter");
    const itemLabels = JSON.parse($("#log-item-labels").textContent);
    let events = [];
    let opener = null;
    let timer = null;
    let loading = false;
    let previousOverflow = "";

    const parsePayload = (event) => {
      try { return JSON.parse(event.payload_json || "{}"); }
      catch (_) { return { text: event.payload_json || "" }; }
    };
    const render = () => {
      const filtered = events.filter((event) => {
        const payload = parsePayload(event);
        return (!stageFilter.value || payload.stage === stageFilter.value) &&
          (!streamFilter.value || (payload.stream || "status") === streamFilter.value) &&
          (!payload.stream || String(payload.text || "").trim());
      });
      const nearBottom = list.childElementCount > 0 && list.scrollHeight - list.scrollTop - list.clientHeight < 40;
      const oldScrollTop = list.scrollTop;
      list.replaceChildren();
      for (const event of filtered) {
        const payload = parsePayload(event);
        const row = document.createElement("li");
        const meta = document.createElement("div"); meta.className = "log-event-meta";
        const heading = document.createElement("strong");
        heading.textContent = payload.stage ? label(payload.stage, STAGE_LABELS) : statusLabel(event.event_type);
        const stream = document.createElement("span");
        stream.textContent = payload.stream === "stdout" ? "标准输出" : payload.stream === "stderr" ? "错误输出" : "状态变化";
        const item = document.createElement("span"); item.textContent = itemLabels[payload.item_id] || "";
        const time = document.createElement("time"); time.textContent = new Date(event.created_at).toLocaleString("zh-CN");
        meta.append(heading, stream);
        if (item.textContent) meta.append(item);
        meta.append(time);
        const message = document.createElement("pre");
        message.textContent = String(payload.text || payload.error || payload.reason || statusLabel(payload.status || event.event_type)).trimEnd();
        row.append(meta, message);
        list.append(row);
      }
      status.textContent = `显示 ${filtered.length} / ${events.length} 条事件`;
      list.scrollTop = nearBottom ? list.scrollHeight : oldScrollTop;
    };
    const refresh = async () => {
      if (loading || drawer.hidden) return;
      loading = true;
      try {
        events = await request(`/api/runs/${encodeURIComponent(drawer.dataset.runId)}/events`);
        const selected = stageFilter.value;
        stageFilter.replaceChildren(new Option("全部阶段", ""));
        for (const stage of new Set(events.map((event) => parsePayload(event).stage).filter(Boolean))) {
          stageFilter.add(new Option(label(stage, STAGE_LABELS), stage));
        }
        if ([...stageFilter.options].some((option) => option.value === selected)) stageFilter.value = selected;
        render();
        if (!["queued", "running"].includes($(".detail-summary")?.dataset.runStatus) && timer) {
          clearInterval(timer); timer = null;
        }
      } catch (error) { status.textContent = `日志加载失败：${error.message}`; }
      finally { loading = false; }
    };
    const close = () => {
      drawer.hidden = true;
      scrim.hidden = true;
      document.body.style.overflow = previousOverflow;
      if (timer) { clearInterval(timer); timer = null; }
      const target = opener?.isConnected ? opener : $("[data-open-log-drawer]");
      target?.focus();
    };
    const open = (target) => {
      opener = target;
      previousOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      drawer.hidden = false;
      scrim.hidden = false;
      list.scrollTop = 0;
      $("[data-close-log-drawer]", drawer).focus();
      status.textContent = "正在加载日志…";
      refresh();
      if (["queued", "running"].includes($(".detail-summary")?.dataset.runStatus)) timer = setInterval(refresh, 3000);
    };
    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-open-log-drawer]");
      if (button) open(button);
    });
    $("[data-close-log-drawer]", drawer).addEventListener("click", close);
    scrim.addEventListener("click", close);
    document.addEventListener("keydown", (event) => { if (!drawer.hidden) handleDialogKeys(event, drawer, close); });
    stageFilter.addEventListener("change", render);
    streamFilter.addEventListener("change", render);
  }

  setupRunLogs();

  async function setupRecords() {
    const body = $("#records-body");
    if (!body) return;
    let page = 1;
    const selected = new Set();
    const query = () => {
      const params = new URLSearchParams({ page: String(page), page_size: "50", trend: $("#trend-toggle").checked ? "1" : "0" });
      for (const [id, key] of [["filter-agent", "agent_id"], ["filter-model", "model_id"], ["filter-task", "task"],
        ["filter-domain", "domain"], ["filter-status", "status"], ["filter-from", "from"], ["filter-to", "to"]]) {
        const value = $(`#${id}`).value;
        if (value) params.set(key, value);
      }
      return params;
    };
    const appendScoreRows = (cell, entries, { trend = false, multipleItems = false } = {}) => {
      if (!entries?.length) {
        const empty = document.createElement("span");
        empty.className = "muted";
        empty.textContent = trend ? "暂无可比指标" : "尚无分数";
        cell.append(empty);
        return;
      }
      const makeRow = (entry) => {
        const row = document.createElement("div");
        row.className = `score-row${trend ? ` ${entry.improved === true ? "trend-improved" : entry.improved === false ? "trend-declined" : "trend-neutral"}` : ""}`;
        const name = document.createElement("span");
        name.className = "score-name";
        name.textContent = `${multipleItems ? `${taskLabel(entry.task)}/${entry.domain} · ` : ""}${entry.label}`;
        name.title = entry.description || "";
        const value = document.createElement("strong");
        value.className = "score-value";
        value.textContent = trend
          ? `${entry.improved === true ? "↑ " : entry.improved === false ? "↓ " : "· "}${deltaText(entry.delta)}`
          : scoreText(entry.value);
        value.title = trend ? `上次 ${scoreText(entry.previous)}，本次 ${scoreText(entry.value)}` : name.title;
        row.append(name, value);
        return row;
      };
      const list = document.createElement("div");
      list.className = "score-list";
      entries.slice(0, 4).forEach((entry) => list.append(makeRow(entry)));
      cell.append(list);
      if (entries.length > 4) {
        const more = document.createElement("details");
        more.className = "score-more";
        const summary = document.createElement("summary");
        summary.textContent = `其余 ${entries.length - 4} 项`;
        const rest = document.createElement("div");
        rest.className = "score-list";
        entries.slice(4).forEach((entry) => rest.append(makeRow(entry)));
        more.append(summary, rest);
        cell.append(more);
      }
    };
    const refresh = async () => {
      try {
        const response = await request(`/api/runs?${query()}`);
        body.replaceChildren();
        for (const run of response.items) {
          const row = document.createElement("tr");
          row.dataset.runId = run.id;
          const checkCell = document.createElement("td");
          const check = document.createElement("input");
          check.type = "checkbox"; check.checked = selected.has(run.id); check.setAttribute("aria-label", `选择运行 ${run.id}`);
          check.addEventListener("change", () => { check.checked ? selected.add(run.id) : selected.delete(run.id); updateCompare(); });
          checkCell.append(check);
          const link = (text, href) => { const a = document.createElement("a"); a.href = href; a.textContent = text; return a; };
          const created = document.createElement("td");
          const agent = document.createElement("td");
          const agentName = document.createElement("strong"); agentName.textContent = run.agent_name;
          const modelName = document.createElement("small"); modelName.textContent = run.model_name;
          agent.append(agentName, modelName);
          const taskDomain = document.createElement("td"); taskDomain.textContent = run.items.map((item) => `${taskLabel(item.task)} / ${item.domain}`).join(" · ");
          const state = document.createElement("td");
          const stateText = document.createElement("span"); stateText.className = `state-pill state-${run.status}`;
          stateText.textContent = statusLabel(run.status); state.append(stateText);
          const metrics = document.createElement("td");
          appendScoreRows(metrics, run.summary_metrics, { multipleItems: run.items.length > 1 });
          const trend = document.createElement("td");
          if (run.trend.previous_run_id) {
            const previous = link(`对比上次 ${run.trend.previous_run_id.slice(0, 8)} →`, `/compare?run_ids=${encodeURIComponent(run.trend.previous_run_id)},${encodeURIComponent(run.id)}`);
            previous.className = "previous-link";
            trend.append(previous);
            appendScoreRows(trend, run.trend.headline_deltas, { trend: true, multipleItems: run.items.length > 1 });
          } else trend.textContent = $("#trend-toggle").checked ? "没有可对比的记录" : "已关闭";
          const runLink = link(run.id.slice(0, 8), `/runs/${encodeURIComponent(run.id)}`);
          runLink.className = "row-link";
          const time = document.createElement("small"); time.textContent = new Date(run.created_at).toLocaleString("zh-CN");
          created.append(runLink, time);
          row.append(checkCell, created, agent, taskDomain, state, metrics, trend); body.append(row);
        }
        if (!response.items.length) { const row = document.createElement("tr"); row.className = "record-empty"; const cell = document.createElement("td"); cell.colSpan = 7; cell.textContent = "没有符合筛选条件的运行记录。"; row.append(cell); body.append(row); }
        $("#record-count").textContent = `共 ${response.total} 条记录`;
        $("#records-page").textContent = `第 ${response.page} 页，共 ${Math.max(1, Math.ceil(response.total / response.page_size))} 页`;
        $("#records-prev").disabled = page <= 1;
        $("#records-next").disabled = page * response.page_size >= response.total;
        updateCompare();
      } catch (error) { body.textContent = error.message; }
    };
    const updateCompare = () => { $("#compare-selected").disabled = selected.size < 2 || selected.size > 4; };
    const reload = () => { page = 1; refresh(); };
    for (const filter of $$(".records-toolbar select, .records-toolbar input[type=date], #trend-toggle")) filter.addEventListener("change", reload);
    $("#clear-record-filters").addEventListener("click", () => { for (const filter of $$(".records-toolbar select, .records-toolbar input[type=date]")) filter.value = ""; $("#trend-toggle").checked = true; reload(); });
    $("#records-prev").addEventListener("click", () => { page -= 1; refresh(); });
    $("#records-next").addEventListener("click", () => { page += 1; refresh(); });
    $("#compare-selected").addEventListener("click", () => { window.location.assign(`/compare?run_ids=${[...selected].map(encodeURIComponent).join(",")}`); });
    $("#filter-agent").addEventListener("change", async () => {
      const select = $("#filter-model"); select.replaceChildren(new Option("全部模型", ""));
      if ($("#filter-agent").value) {
        const models = await request(`/api/agents/${encodeURIComponent($("#filter-agent").value)}/models`);
        for (const model of models) select.add(new Option(model.name, model.id));
      }
      reload();
    });
    refresh();
  }

  async function setupCompare() {
    const root = $("#compare-root");
    const body = $("#compare-body");
    if (!root || !body) return;
    try {
      const result = await request("/api/runs/compare", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ run_ids: root.dataset.runIds.split(",") }) });
      $("#compare-intersection").textContent = `共有 ${result.intersection_count} 个领域：${result.domains.join(", ") || "无"}`;
      for (const [index, run] of result.runs.entries()) {
        const heading = $(`[data-compare-run-id="${run.id}"]`);
        if (!heading) continue;
        const existing = $("small", heading);
        if (existing) existing.textContent = `${statusLabel(run.status)} · ${new Date(run.created_at).toLocaleString("zh-CN")}`;
        const context = document.createElement("small");
        context.textContent = `${run.agent_name} / ${run.model_name}${index === 0 ? " · 基准" : ""}`;
        heading.append(context);
      }
      const summaryMaps = result.runs.map((run) => new Map((run.summary_metrics || [])
        .filter((metric) => result.domains.includes(metric.domain))
        .map((metric) => [JSON.stringify(metric.key), metric])));
      const orderedSummary = [];
      const seen = new Set();
      for (const run of result.runs) for (const metric of run.summary_metrics || []) {
        const key = JSON.stringify(metric.key);
        if (!result.domains.includes(metric.domain) || seen.has(key)) continue;
        seen.add(key);
        orderedSummary.push(metric);
      }
      const summaryRows = orderedSummary.map((metric) => {
        const values = summaryMaps.map((map) => map.get(JSON.stringify(metric.key))?.value ?? null);
        const baseline = values[0];
        return {
          key: [metric.task, metric.domain, metric.dimension, metric.layer, metric.metric_name, "ratio", metric.scope],
          label: metric.label,
          description: metric.description,
          entries: values.map((value, index) => {
            const delta = index && value != null && baseline != null ? value - baseline : null;
            return { value, delta, improved: delta == null || delta === 0 ? null : delta > 0 };
          }),
        };
      });
      const allRows = [...result.metrics].sort((a, b) => {
        const priority = (metric) => metric.key[6]?.startsWith("cq:") ? 2 : metric.key[6] === "combined" ? 0 : 1;
        return priority(a) - priority(b) || JSON.stringify(a.key).localeCompare(JSON.stringify(b.key));
      });
      const render = (view) => {
        $$('[data-compare-view]', root).forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.compareView === view)));
        body.replaceChildren();
        const rows = view === "all" ? allRows : summaryRows;
        for (const metric of rows) {
          const row = document.createElement("tr");
          const task = document.createElement("th"); task.scope = "row";
          task.textContent = `${taskLabel(metric.key[0])} / ${metric.key[1]}`;
          const dimension = document.createElement("td"); dimension.textContent = dimensionLabel(metric.key[2]);
          const scope = document.createElement("td"); scope.textContent = `${layerLabel(metric.key[3])} · ${scopeLabel(metric.key[6])}`;
          const name = document.createElement("td"); name.textContent = metric.label || metricLabel(metric.key[4]);
          name.title = metric.description || `${dimension.textContent}，${scope.textContent}。完整定义见指标说明。`;
          row.append(task, dimension, scope, name);
          for (const entry of metric.entries) {
            const cell = document.createElement("td");
            cell.className = "compare-value";
            const value = document.createElement("strong"); value.textContent = scoreText(entry.value);
            cell.append(value);
            if (entry.delta != null) {
              const delta = document.createElement("small");
              delta.className = entry.improved === true ? "metric-improved" : entry.improved === false ? "metric-declined" : "";
              delta.textContent = `${entry.improved === true ? "↑ " : entry.improved === false ? "↓ " : "· "}${deltaText(entry.delta)}`;
              cell.append(delta);
            }
            row.append(cell);
          }
          body.append(row);
        }
        if (!rows.length) {
          const row = document.createElement("tr");
          const cell = document.createElement("td"); cell.colSpan = result.run_ids.length + 4;
          cell.textContent = "共同领域中没有可对比的指标。";
          row.append(cell); body.append(row);
        }
      };
      $$('[data-compare-view]', root).forEach((button) => button.addEventListener("click", () => render(button.dataset.compareView)));
      render("summary");
    } catch (error) { body.textContent = error.message; }
  }

  setupRecords();
  setupCompare();
})();
