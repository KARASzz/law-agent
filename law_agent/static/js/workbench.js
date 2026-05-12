const config = window.WORKBENCH_CONFIG || {};
const apiPaths = config.apiPaths || {};

const state = {
  current: null,
  reviewTask: null,
  taskHierarchy: null,
  activeUser: normalizeActiveUser(config.activeUser)
};

const $ = (id) => document.getElementById(id);

function normalizeActiveUser(activeUser) {
  return {
    label: activeUser?.label || "开发用户",
    userId: activeUser?.user_id || activeUser?.userId || "web_user",
    sessionId: activeUser?.session_id || activeUser?.sessionId || "web_session"
  };
}

function renderActiveUser() {
  $("currentUserLabel").textContent = `${state.activeUser.label} · ${state.activeUser.userId}`;
}

const EXAMPLE_INPUTS = config.examples || [
  "公司拖欠工资三个月，员工是否可以立即解除劳动合同？",
  "帮我找建设工程实际施工人主张工程价款的类案",
  "生成一份民事起诉状：张三要求李四返还借款10万元",
  "审查一份房屋租赁合同，重点看违约责任和解除条款"
];

const COMMANDS = {
  help: {
    name: "/help",
    description: "查看帮助引导",
    run: async () => showCommandResult(
      "工作台指令帮助",
      COMMAND_ORDER.map((key) => {
        const command = COMMANDS[key];
        return `${command.name}：${command.description}`;
      }).join("\n")
    ),
  },
  clear: {
    name: "/clear",
    description: "清理当前页面缓存",
    run: async () => {
      clearWorkbenchCache();
      setStatus("已清理当前页面缓存", "done");
    },
  },
  new: {
    name: "/new",
    description: "新建一次空白处理",
    run: async () => {
      clearWorkbenchCache();
      $("userInput").value = "";
      setStatus("已新建空白处理", "done");
    },
  },
  review: {
    name: "/review",
    description: "加载待审阅任务",
    run: async () => {
      $("reviewFilter").value = "pending_review";
      await loadTasks();
      showCommandResult("待审阅任务", "已加载 pending_review 任务，请在左侧审阅任务列表中选择。");
    },
  },
  examples: {
    name: "/examples",
    description: "查看输入示例",
    run: async () => showCommandResult(
      "可试用输入示例",
      EXAMPLE_INPUTS.map((item, index) => `${index + 1}. ${item}`).join("\n")
    ),
  },
  status: {
    name: "/status",
    description: "查看服务与模型状态",
    run: async () => {
      const data = await api(apiPath("health", "/api/v1/health"));
      showCommandResult(
        "服务状态",
        [
          `status: ${data.status || "-"}`,
          `llm_enabled: ${data.llm_enabled ?? "-"}`,
          `llm_status: ${data.llm_status || "-"}`,
          `llm_model: ${data.llm_model || "-"}`,
          `fallback_models: ${(data.llm_fallback_models || []).join(", ") || "-"}`,
        ].join("\n")
      );
    },
  },
  search: {
    name: "/search",
    description: "普通联网检索",
    run: async (text) => runWebResearchCommand(text, "quick_search"),
  },
  research: {
    name: "/research",
    description: "深度联网研究",
    run: async (text) => runWebResearchCommand(text, "deep_research"),
  },
  extract: {
    name: "/extract",
    description: "读取指定网页正文",
    run: async (text) => runWebResearchCommand(text, "extract_url"),
  },
  site: {
    name: "/site",
    description: "发现或采集指定站点资料",
    run: async (text) => runWebResearchCommand(text, "site_discovery"),
  },
};

const COMMAND_ORDER = (config.commands || []).length ? config.commands.map((item) => item.key) : [
  "help",
  "clear",
  "new",
  "review",
  "examples",
  "status",
  "search",
  "research",
  "extract",
  "site"
];

(config.commands || []).forEach((item) => {
  if (COMMANDS[item.key]) {
    COMMANDS[item.key].name = item.name || COMMANDS[item.key].name;
    COMMANDS[item.key].description = item.description || COMMANDS[item.key].description;
  }
});

function renderCommands() {
  $("commandList").innerHTML = COMMAND_ORDER.map((key) => {
    const command = COMMANDS[key];
    return `<button class="command-btn" type="button" data-command="${escapeHtml(command.name)}">${escapeHtml(command.name)}</button>`;
  }).join("");

  document.querySelectorAll("#commandList .command-btn").forEach((node) => {
    node.addEventListener("click", () => {
      $("userInput").value = node.dataset.command;
      processInput().catch((error) => setStatus(error.message, "error"));
    });
  });
}

async function handleCommandIfNeeded(rawInput) {
  const text = rawInput.trim();
  if (!text.startsWith("/")) return false;

  const commandName = text.slice(1).split(/\s+/)[0].toLowerCase();
  const command = COMMANDS[commandName];
  if (!command) {
    showCommandResult("未知指令", `未识别指令：/${commandName}\n输入 /help 查看可用指令。`);
    return true;
  }

  await command.run(text);
  return true;
}

function showCommandResult(title, content) {
  state.current = {
    success: true,
    task_id: "local-command",
    trace_id: "local-command",
    output: `## ${title}\n\n${content}`,
    intent: "command",
    risk_level: "low",
    requires_human_review: false,
    can_export: true,
    tools_used: ["workbench.command"],
    profile_record_ids: [],
    profile_strategy: {},
    review_status: "not_required",
    llm_enabled: false,
    llm_status: "not_called",
    llm_tools_used: [],
    llm_model: "",
    llm_fallback_models: [],
  };
  state.reviewTask = null;
  state.taskHierarchy = null;
  renderCurrent();
  setStatus("已执行指令", "done");
}

async function runWebResearchCommand(rawText, purpose) {
  const parsed = parseResearchCommand(rawText, purpose);
  if (!parsed.query && !parsed.urls.length && !parsed.site_url) {
    showCommandResult(
      "联网研究指令",
      "请输入要检索的问题或 URL。\n示例：/search 最高人民法院 建设工程 实际施工人\n示例：/extract https://example.com/article\n示例：/site court.gov.cn 建设工程"
    );
    return;
  }

  setStatus("联网研究中", "processing");
  const data = await api(apiPath("research_web", "/api/v1/research/web"), {
    method: "POST",
    body: JSON.stringify(parsed)
  });
  state.current = {
    success: true,
    task_id: "web-research",
    trace_id: `web-research-${Date.now()}`,
    output: formatResearchOutput(data),
    intent: "web_research",
    risk_level: "medium",
    confidence: 1,
    requires_human_review: false,
    can_export: false,
    tools_used: (data.tool_calls || []).map((call) => `external.${call.provider}.${call.tool}`),
    profile_record_ids: [],
    profile_strategy: {},
    review_status: "not_required",
    review_task: null,
    llm_enabled: false,
    llm_status: "not_called",
    llm_tools_used: [],
    llm_model: "",
    llm_fallback_models: [],
  };
  state.reviewTask = null;
  state.taskHierarchy = null;
  renderCurrent();
  setStatus("联网研究完成", "done");
}

function parseResearchCommand(rawText, purpose) {
  const parts = rawText.trim().split(/\s+/);
  parts.shift();
  const urlPattern = /^https?:\/\/\S+/i;
  const urls = parts.filter((part) => urlPattern.test(part));
  let siteUrl = "";
  let queryParts = parts.filter((part) => !urlPattern.test(part));

  if (purpose === "extract_url") {
    return {
      query: queryParts.join(" "),
      purpose,
      urls,
      site_url: "",
    };
  }

  if (purpose === "site_discovery") {
    siteUrl = parts[0] || "";
    queryParts = parts.slice(1);
  }

  return {
    query: queryParts.join(" "),
    purpose,
    urls,
    site_url: siteUrl,
  };
}

function formatResearchOutput(data) {
  const lines = ["## 联网研究结果"];
  if (data.answer) {
    lines.push("", data.answer);
  }

  const sources = data.sources || [];
  if (sources.length) {
    lines.push("", "### 来源");
    sources.slice(0, 10).forEach((source, index) => {
      lines.push(`${index + 1}. ${source.title || source.url || "未命名来源"}`);
      if (source.url) lines.push(`   ${source.url}`);
      lines.push(`   工具：${source.provider || "-"} / ${source.tool || "-"}`);
      const snippet = source.snippet || source.content || "";
      if (snippet) lines.push(`   摘要：${snippet.slice(0, 220)}`);
    });
  }

  const calls = data.tool_calls || [];
  if (calls.length) {
    lines.push("", "### 工具调用");
    calls.forEach((call) => {
      lines.push(`- ${call.provider}.${call.tool}: ${call.status}${call.count != null ? ` (${call.count})` : ""}`);
    });
  }

  const warnings = data.warnings || [];
  if (warnings.length) {
    lines.push("", "### 注意");
    warnings.forEach((item) => lines.push(`- ${item}`));
  }

  return lines.join("\n");
}

function clearWorkbenchCache() {
  state.current = null;
  state.reviewTask = null;
  state.taskHierarchy = null;
  $("reviewedOutput").value = "";
  $("profileStrategy").innerHTML = "<div class=\"empty\">暂无命中画像</div>";
  $("runtimeInfo").innerHTML = "<div class=\"empty\">暂无运行信息</div>";
  $("toolChips").innerHTML = "";
  $("orchestrationInfo").innerHTML = "<div class=\"empty\">暂无层级任务</div>";
  $("externalActionList").innerHTML = "<div class=\"empty\">暂无记录</div>";
  renderCurrent();
}

function setStatus(message, type = "info") {
  const el = $("globalStatus");
  el.className = "status-line";
  if (!message) {
    el.innerHTML = "";
    return;
  }

  el.classList.add("visible");
  if (type === "processing") {
    el.innerHTML = `<span>${escapeHtml(message)}</span><span class="spinner" aria-hidden="true"></span>`;
    return;
  }

  if (type === "done") {
    el.innerHTML = `<span>${escapeHtml(message)}</span><span class="status-done" aria-hidden="true">✅</span>`;
    return;
  }

  if (type === "error") {
    el.classList.add("error");
  }
  el.textContent = message;
}

function badge(el, value, classValue = value) {
  el.textContent = value || "-";
  el.className = "badge";
  if (classValue) {
    el.classList.add(String(classValue).replace(/[^a-zA-Z0-9_-]/g, "_"));
  }
}

function renderRisk(value) {
  const metric = $("riskMetric");
  const risk = value || "";
  $("riskLevel").textContent = risk || "-";
  metric.className = "metric risk-metric";
  if (risk === "low") {
    metric.classList.add("risk-low");
  } else if (risk === "medium") {
    metric.classList.add("risk-medium");
  } else if (risk === "high") {
    metric.classList.add("risk-high");
  } else {
    metric.classList.add("risk-unknown");
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json"},
    ...options
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || response.statusText);
  }
  return data;
}

function apiPath(name, fallback) {
  return apiPaths[name] || fallback;
}

async function loadTaskHierarchy(taskId) {
  state.taskHierarchy = null;
  renderOrchestration(state.taskHierarchy);
  if (!taskId || taskId === "local-command" || taskId === "web-research") return;

  try {
    state.taskHierarchy = await api(`${apiPath("tasks", "/api/v1/tasks")}/${encodeURIComponent(taskId)}`);
  } catch (error) {
    state.taskHierarchy = {load_error: error.message, steps: [], tool_calls: []};
  }
  renderOrchestration(state.taskHierarchy);
}

function externalAllowed() {
  if (!state.current) return false;
  if (state.current.risk_level === "low") return true;
  return currentReviewStatus() === "confirmed";
}

function currentReviewStatus() {
  if (state.reviewTask) return state.reviewTask.review_status;
  return state.current ? state.current.review_status : "";
}

function renderCurrent() {
  const current = state.current;
  const runtime = getRuntime(current);
  const reviewStatus = currentReviewStatus();
  $("traceId").textContent = current ? current.trace_id : "-";
  $("intentValue").textContent = current ? current.intent : "-";
  $("llmStatus").textContent = runtime.statusLabel || "-";
  renderRisk(current ? current.risk_level : "");
  $("reviewStatus").textContent = reviewStatus || "-";
  $("canExport").textContent = externalAllowed() ? "true" : "false";
  $("output").textContent = current ? current.output : "";
  $("reviewedOutput").value = state.reviewTask
    ? (state.reviewTask.reviewed_output || state.reviewTask.original_output || "")
    : (current ? current.output : "");

  renderProfile(current ? current.profile_strategy : null);
  renderRuntime(current, runtime);
  renderOrchestration(state.taskHierarchy);

  const hasTrace = Boolean(current && current.trace_id);
  const needsReview = current && current.requires_human_review;
  $("confirmBtn").disabled = !hasTrace || !needsReview || reviewStatus === "confirmed";
  $("confirmEditedBtn").disabled = !hasTrace || !needsReview || reviewStatus === "confirmed";
  $("rejectBtn").disabled = !hasTrace || !needsReview || reviewStatus === "rejected";
  $("exportBtn").disabled = !hasTrace || !externalAllowed();
  $("sendBtn").disabled = !hasTrace || !externalAllowed();
}

function renderProfile(strategy) {
  const entries = [];
  if (strategy && Object.keys(strategy).length) {
    entries.push(["record_ids", (strategy.record_ids || []).join(", ")]);
    entries.push(["strategy_choice", strategy.strategy_choice]);
    entries.push(["risk_communication", strategy.risk_communication]);
    entries.push(["handling_temperature", strategy.handling_temperature]);
    entries.push(["reusable_rule", strategy.reusable_rule]);
    entries.push(["external_document_suitability", strategy.external_document_suitability]);
  }

  $("profileStrategy").innerHTML = entries
    .filter(([, value]) => value)
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`)
    .join("") || "<div class=\"empty\">暂无命中画像</div>";
}

function getRuntime(current) {
  if (!current) {
    return {
      status: "",
      statusLabel: "",
      enabled: "-",
      model: "-",
      fallbackModels: "-",
      llmTools: [],
      note: "",
    };
  }

  const tools = (current.tools_used || []).map((tool) => String(tool));
  const inferredLlmTools = tools.filter((tool) => tool.startsWith("llm."));
  const explicitLlmTools = Array.isArray(current.llm_tools_used)
    ? current.llm_tools_used.filter(Boolean).map((tool) => String(tool))
    : [];
  const llmTools = explicitLlmTools.length ? explicitLlmTools : inferredLlmTools;
  const outputText = String(current.output || "");
  const inferredFromOutput = !llmTools.length && (
    outputText.includes("律师工作台内部辅助助手") ||
    outputText.includes("所有输出仅供团队内部参考") ||
    outputText.includes("不替代律师")
  );
  const hasRuntimeFields = [
    "llm_enabled",
    "llm_status",
    "llm_model",
    "llm_fallback_models",
  ].some((key) => Object.prototype.hasOwnProperty.call(current, key));

  let status = current.llm_status || "";
  if (!status && llmTools.length) {
    status = llmTools.some((tool) => tool.includes("failed"))
      ? "called_with_error"
      : "called";
  }
  if (!status && inferredFromOutput) {
    status = "probable";
  }
  if (!status) {
    status = current.llm_enabled === false ? "disabled" : "unknown";
  }

  const statusLabels = {
    called: "called",
    called_with_fallback: "fallback",
    called_with_error: "error",
    failed: "failed",
    not_called: "not_called",
    disabled: "disabled",
    probable: "probable",
    unknown: "unknown",
  };

  let enabled = current.llm_enabled;
  if (enabled === undefined || enabled === null) {
    if (llmTools.length) {
      enabled = "true (由 tools_used 推断)";
    } else if (inferredFromOutput) {
      enabled = "疑似 true (由输出特征推断)";
    } else {
      enabled = "后端未返回";
    }
  }

  const fallbackModels = Array.isArray(current.llm_fallback_models)
    ? current.llm_fallback_models.filter(Boolean).join(", ")
    : "";
  let note = "";
  if (llmTools.length && !hasRuntimeFields) {
    note = "API 未返回 llm_* 字段，已从 tools_used 推断；重启服务后会显示模型配置。";
  } else if (inferredFromOutput) {
    note = "当前响应没有 tools_used/llm_* 字段，但输出符合 LLM 助手特征；请重启工作台服务获取精确链路。";
  } else if (!hasRuntimeFields && !tools.length) {
    note = "当前后端未返回运行链路字段；请重启工作台服务。";
  }

  return {
    status,
    statusLabel: statusLabels[status] || status,
    enabled,
    model: current.llm_model || (llmTools.length || inferredFromOutput ? "后端未返回（需重启服务）" : "后端未返回"),
    fallbackModels: fallbackModels || "后端未返回",
    llmTools,
    inferredFromOutput,
    note,
  };
}

function renderRuntime(current, runtime = getRuntime(current)) {
  if (!current) {
    $("runtimeInfo").innerHTML = "<div class=\"empty\">暂无运行信息</div>";
    $("toolChips").innerHTML = "";
    return;
  }

  const entries = [
    ["llm_enabled", runtime.enabled],
    ["llm_model", runtime.model],
    ["fallback_models", runtime.fallbackModels],
    [
      "llm_tools_used",
      runtime.llmTools.length
        ? runtime.llmTools.join(", ")
        : (runtime.inferredFromOutput ? "未返回，但输出疑似 LLM 生成" : "未调用或后端未返回")
    ],
    ["runtime_note", runtime.note],
  ];

  $("runtimeInfo").innerHTML = entries
    .filter(([, value]) => value)
    .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`)
    .join("");

  const tools = current.tools_used || [];
  $("toolChips").innerHTML = tools.length
    ? tools.map((tool) => `<span class="chip">${escapeHtml(tool)}</span>`).join("")
    : "<div class=\"empty\">后端未返回工具调用</div>";
}

function renderOrchestration(payload) {
  const target = $("orchestrationInfo");
  const taskId = state.current ? state.current.task_id : "";
  if (!taskId || taskId === "local-command" || taskId === "web-research") {
    target.innerHTML = "<div class=\"empty\">暂无层级任务</div>";
    return;
  }

  if (!payload) {
    target.innerHTML = "<div class=\"empty\">层级任务尚未加载</div>";
    return;
  }

  if (payload.load_error) {
    target.innerHTML = `<div class="task-note">加载失败：${escapeHtml(payload.load_error)}</div>`;
    return;
  }

  const steps = payload.steps || [];
  const calls = payload.tool_calls || [];
  const taskError = payload.error ? `<div class="step-error">${escapeHtml(payload.error)}</div>` : "";
  const summary = `
    <div class="task-note">
      task_id: ${escapeHtml(payload.task_id || state.current.task_id)}
      · status: ${escapeHtml(payload.status || "-")}
      · intent: ${escapeHtml(payload.intent || "-")}
      ${taskError}
    </div>
  `;

  const stepHtml = steps.length ? steps.map((step) => {
    const stepCalls = calls.filter((call) => call.step_id === step.step_id);
    const callHtml = stepCalls.length ? `
      <div class="tool-call-list">
        ${stepCalls.map((call) => `
          <div class="tool-call">
            <span>${escapeHtml(call.provider || "-")}.${escapeHtml(call.tool_name || "-")}</span>
            <span class="badge ${escapeHtml(call.status || "")}">${escapeHtml(call.status || "-")}</span>
          </div>
          ${call.error ? `<div class="tool-error">${escapeHtml(call.error)}</div>` : ""}
        `).join("")}
      </div>
    ` : "";
    return `
      <div class="step-item">
        <div class="step-main">
          <div class="step-name">${escapeHtml(step.sequence)}. ${escapeHtml(step.name || "-")}</div>
          <span class="badge ${escapeHtml(step.status || "")}">${escapeHtml(step.status || "-")}</span>
        </div>
        <div class="step-meta">${escapeHtml(step.role || "-")} · ${escapeHtml(step.completed_at || step.started_at || "")}</div>
        ${step.error ? `<div class="step-error">${escapeHtml(step.error)}</div>` : ""}
        ${callHtml}
      </div>
    `;
  }).join("") : "<div class=\"empty\">暂无步骤记录</div>";

  const orphanCalls = calls.filter((call) => !steps.some((step) => step.step_id === call.step_id));
  const orphanHtml = orphanCalls.length ? `
    <div class="tool-call-list">
      ${orphanCalls.map((call) => `
        <div class="tool-call">
          <span>${escapeHtml(call.provider || "-")}.${escapeHtml(call.tool_name || "-")}</span>
          <span class="badge ${escapeHtml(call.status || "")}">${escapeHtml(call.status || "-")}</span>
        </div>
      `).join("")}
    </div>
  ` : "";

  target.innerHTML = `${summary}<div class="step-list">${stepHtml}</div>${orphanHtml}`;
}

function renderTasks(items) {
  $("taskList").innerHTML = items.length ? items.map((task) => `
    <div class="item" data-trace="${escapeHtml(task.trace_id)}">
      <div class="item-title">
        <span>${escapeHtml(task.task_title || task.user_input || task.intent)}</span>
        <span class="badge ${escapeHtml(task.review_status)}">${escapeHtml(task.review_status)}</span>
      </div>
      <div class="item-text">${escapeHtml(task.intent)} · ${escapeHtml(task.trace_id)}</div>
      <div class="item-text">${escapeHtml(task.risk_level)} · ${escapeHtml(task.updated_at || "")}</div>
    </div>
  `).join("") : "<div class=\"empty\">暂无审阅任务</div>";

  document.querySelectorAll("#taskList .item").forEach((node) => {
    node.addEventListener("click", () => selectTask(items.find((item) => item.trace_id === node.dataset.trace)));
  });
}

function selectTask(task) {
  state.reviewTask = task;
  $("userInput").value = task.user_input || "";
  state.current = {
    success: true,
    task_id: task.task_id,
    trace_id: task.trace_id,
    output: task.reviewed_output || task.original_output,
    intent: task.intent,
    risk_level: task.risk_level,
    requires_human_review: task.review_status !== "not_required",
    can_export: task.review_status === "confirmed",
    tools_used: task.tools_used || [],
    llm_enabled: task.llm_enabled,
    llm_status: task.llm_status,
    llm_tools_used: task.llm_tools_used || [],
    llm_model: task.llm_model,
    llm_fallback_models: task.llm_fallback_models || [],
    profile_record_ids: task.profile_record_ids || [],
    profile_strategy: {},
    review_status: task.review_status
  };
  state.taskHierarchy = null;
  renderCurrent();
  loadTaskHierarchy(task.task_id).catch((error) => setStatus(error.message, "error"));
  loadAudit();
  loadExternalActions();
}

function renderList(id, items, formatter) {
  $(id).innerHTML = items.length
    ? items.map((item) => `<div class="item">${formatter(item)}</div>`).join("")
    : "<div class=\"empty\">暂无记录</div>";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function processInput() {
  if (await handleCommandIfNeeded($("userInput").value)) return;

  setStatus("处理中", "processing");
  const data = await api(apiPath("process", "/api/v1/process"), {
    method: "POST",
    body: JSON.stringify({
      user_input: $("userInput").value,
      session_id: state.activeUser.sessionId,
      user_id: state.activeUser.userId
    })
  });
  state.current = data;
  state.reviewTask = data.review_task;
  state.taskHierarchy = null;
  renderCurrent();
  await loadTaskHierarchy(data.task_id);
  await refreshAll();
  setStatus("已完成", "done");
}

async function loadTasks() {
  const params = new URLSearchParams();
  if ($("reviewFilter").value) params.set("review_status", $("reviewFilter").value);
  if ($("riskFilter").value) params.set("risk_level", $("riskFilter").value);
  params.set("limit", "50");
  const data = await api(`${apiPath("review_tasks", "/api/v1/review/tasks")}?${params.toString()}`);
  renderTasks(data.items || []);
}

async function loadAudit() {
  const params = new URLSearchParams({limit: "20"});
  if (state.current && state.current.risk_level) params.set("risk_level", state.current.risk_level);
  const data = await api(`${apiPath("audit", "/api/v1/audit")}?${params.toString()}`);
  renderList("auditList", data.items || [], (item) => `
    <div class="item-title">
      <span>${escapeHtml(item.intent || "-")}</span>
      <span class="badge ${escapeHtml(item.risk_level || "")}">${escapeHtml(item.risk_level || "-")}</span>
    </div>
    <div class="item-text">${escapeHtml(item.trace_id)}</div>
    <div class="item-text">${escapeHtml(item.input_summary || "")}</div>
  `);
}

async function loadExternalActions() {
  const params = new URLSearchParams({limit: "20"});
  if (state.current && state.current.trace_id) params.set("trace_id", state.current.trace_id);
  const data = await api(`${apiPath("external_actions", "/api/v1/audit/external-actions")}?${params.toString()}`);
  renderList("externalActionList", data.items || [], (item) => `
    <div class="item-title">
      <span>${escapeHtml(item.action_type || "-")}</span>
      <span class="badge ${item.confirmed ? "confirmed" : "blocked"}">${item.confirmed ? "confirmed" : "unconfirmed"}</span>
    </div>
    <div class="item-text">${escapeHtml(item.trace_id)}</div>
    <div class="item-text">${escapeHtml(item.actor_id || "")} · ${escapeHtml(item.destination || "")}</div>
  `);
}

async function confirmReview(useEdited) {
  if (!state.current) return;
  const body = {
    trace_id: state.current.trace_id,
    reviewer_id: $("reviewerId").value
  };
  if (useEdited) body.reviewed_output = $("reviewedOutput").value;
  state.reviewTask = await api(apiPath("review_confirm", "/api/v1/review/confirm"), {
    method: "POST",
    body: JSON.stringify(body)
  });
  state.current.review_status = state.reviewTask.review_status;
  state.current.can_export = true;
  state.current.output = state.reviewTask.reviewed_output || state.current.output;
  renderCurrent();
  await refreshAll();
  setStatus("已确认");
}

async function rejectReview() {
  if (!state.current) return;
  state.reviewTask = await api(apiPath("review_reject", "/api/v1/review/reject"), {
    method: "POST",
    body: JSON.stringify({
      trace_id: state.current.trace_id,
      reviewer_id: $("reviewerId").value,
      rejection_reason: $("rejectionReason").value
    })
  });
  state.current.review_status = state.reviewTask.review_status;
  state.current.can_export = false;
  renderCurrent();
  await refreshAll();
  setStatus("已驳回");
}

async function externalAction(type) {
  if (!state.current) return;
  const path = type === "send" ? apiPath("send", "/api/v1/send") : apiPath("export", "/api/v1/export");
  const body = {
    trace_id: state.current.trace_id,
    actor_id: $("actorId").value,
    destination: $("destination").value
  };
  if (type === "export") body.export_format = "markdown";
  await api(path, {
    method: "POST",
    body: JSON.stringify(body)
  });
  await loadExternalActions();
  await loadAudit();
  setStatus(type === "send" ? "已发送并留痕" : "已导出并留痕");
}

async function refreshAll() {
  await Promise.all([loadTasks(), loadAudit(), loadExternalActions()]);
}

$("processBtn").addEventListener("click", () => processInput().catch((error) => setStatus(error.message)));
$("userSwitchBtn").addEventListener("click", () => {
  setStatus("当前为单用户开发模式，多用户切换模块已预留");
});
$("refreshBtn").addEventListener("click", () => refreshAll().catch((error) => setStatus(error.message)));
$("loadTasksBtn").addEventListener("click", () => loadTasks().catch((error) => setStatus(error.message)));
$("confirmBtn").addEventListener("click", () => confirmReview(false).catch((error) => setStatus(error.message)));
$("confirmEditedBtn").addEventListener("click", () => confirmReview(true).catch((error) => setStatus(error.message)));
$("rejectBtn").addEventListener("click", () => rejectReview().catch((error) => setStatus(error.message)));
$("exportBtn").addEventListener("click", () => externalAction("export").catch((error) => setStatus(error.message)));
$("sendBtn").addEventListener("click", () => externalAction("send").catch((error) => setStatus(error.message)));
$("reviewFilter").addEventListener("change", () => loadTasks().catch((error) => setStatus(error.message)));
$("riskFilter").addEventListener("change", () => loadTasks().catch((error) => setStatus(error.message)));

renderCommands();
renderActiveUser();
renderCurrent();
refreshAll().catch((error) => setStatus(error.message));
