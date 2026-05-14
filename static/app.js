const demoAlerts = [
  {
    id: "airflow_task_failed",
    label: "Airflow 任务失败",
    alert: "DAG dwd_order_detail_daily 今天凌晨运行失败，请帮我诊断原因。",
  },
  {
    id: "partition_missing",
    label: "表分区缺失",
    alert: "dws_sales_daily 今天没有生成 dt=2026-05-14 分区，请帮我排查。",
  },
  {
    id: "data_volume_drop",
    label: "数据量突降",
    alert: "dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。",
  },
  {
    id: "null_rate_spike",
    label: "字段空值率异常",
    alert: "ads_user_profile 表中 user_id 字段空值率突然升高，请分析影响范围。",
  },
];

const workflowSteps = [
  "AlertParser",
  "DiagnosisSkillMatcher",
  "KnowledgeRetriever",
  "Planner",
  "ToolExecutor",
  "CoverageChecker",
  "Reporter",
  "IncidentRecorder",
];

let selectedDemoId = "data_volume_drop";
let currentDiagnosis = null;

const byId = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
  byId("session-id").value = makeSessionId();
  byId("alert-input").value = demoAlerts.find((item) => item.id === selectedDemoId).alert;
  renderDemoButtons();
  renderPipeline({});
  bindTabs();
  bindActions();
  refreshHealth();
  loadIncidents();
});

function bindActions() {
  byId("diagnose-button").addEventListener("click", runDiagnosis);
  byId("new-session-button").addEventListener("click", () => {
    byId("session-id").value = makeSessionId();
    resetResult();
  });
  byId("chat-button").addEventListener("click", sendChat);
  byId("chat-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      sendChat();
    }
  });
}

function bindTabs() {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.addEventListener("click", () => setActiveTab(button.dataset.tab));
  });
}

function setActiveTab(tabName) {
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${tabName}`);
  });
}

function makeSessionId() {
  return `demo-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function renderDemoButtons() {
  const container = byId("demo-alerts");
  container.innerHTML = "";
  demoAlerts.forEach((item) => {
    const button = document.createElement("button");
    button.className = `demo-button ${item.id === selectedDemoId ? "active" : ""}`;
    button.type = "button";
    button.textContent = item.label;
    button.addEventListener("click", () => {
      selectedDemoId = item.id;
      byId("alert-input").value = item.alert;
      renderDemoButtons();
    });
    container.appendChild(button);
  });
}

async function refreshHealth() {
  const response = await fetchJson("/api/health");
  if (!response.ok) {
    setHealthChip("health-status", "API error", "warn");
    return;
  }
  const data = response.body.data;
  setHealthChip("health-status", `API ${data.status}`, data.status === "ok" ? "ok" : "warn");
  setHealthChip("skill-count", `Skills ${data.skills_loaded}`, data.skills_loaded ? "ok" : "warn");
  setHealthChip("rag-status", `RAG ${data.rag_index}`, data.rag_index === "ok" ? "ok" : "warn");
}

function setHealthChip(id, text, level) {
  const node = byId(id);
  node.textContent = text;
  node.className = `status-chip ${level}`;
}

async function runDiagnosis() {
  const sessionId = byId("session-id").value.trim() || makeSessionId();
  const alert = byId("alert-input").value.trim();
  if (!alert) {
    showError("告警内容不能为空。");
    return;
  }

  byId("session-id").value = sessionId;
  setBusy(true);
  setRunStatus("running");
  byId("incident-id").textContent = "--";
  byId("selected-skill").textContent = "--";
  renderPipeline({ AlertParser: "running" });
  clearResultPanels();

  const response = await fetchJson("/api/diagnose", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      alert,
      options: { debug: true },
    }),
  });

  setBusy(false);
  if (!response.ok && response.status !== 422) {
    showError(response.body?.error?.detail || "诊断请求失败。");
    setRunStatus("failed");
    return;
  }

  const data = response.body.data;
  currentDiagnosis = data;
  renderDiagnosis(data);
  await loadIncidents();
}

function renderDiagnosis(data) {
  setRunStatus(data.status);
  byId("incident-id").textContent = data.incident_id || "--";
  byId("selected-skill").textContent = data.selected_diagnosis_skill?.name || "--";
  byId("doc-count").textContent = String(data.retrieved_docs?.length || 0);
  byId("tool-count").textContent = String(data.tool_calls?.length || 0);
  byId("failed-tool-count").textContent = String(
    (data.tool_calls || []).filter((call) => call.status === "failed").length,
  );

  renderPipeline(statusMapForDiagnosis(data));
  renderContext(data.alert_context || {});
  renderSkill(data.selected_diagnosis_skill, data.candidate_diagnosis_skills || []);
  renderPlan(data.plan || []);
  renderDocs(data.retrieved_docs || []);
  renderTools(data.tool_calls || []);
  renderCoverage(data.coverage_result || {});
  renderReport(data.final_report || "");
  renderVolumeChart(data.tool_calls || []);

  if (data.status === "needs_clarification") {
    showError(data.clarification_question || "需要补充更多信息。");
    setActiveTab("overview");
  } else {
    setActiveTab("report");
  }
}

function statusMapForDiagnosis(data) {
  if (data.status === "needs_clarification") {
    return {
      AlertParser: data.alert_context ? "done" : "warn",
      DiagnosisSkillMatcher: "warn",
      Reporter: "done",
      IncidentRecorder: data.incident_id ? "done" : "warn",
    };
  }

  const coverageStatus = data.coverage_result?.status;
  return {
    AlertParser: "done",
    DiagnosisSkillMatcher: data.selected_diagnosis_skill ? "done" : "warn",
    KnowledgeRetriever: (data.retrieved_docs || []).length ? "done" : "warn",
    Planner: (data.plan || []).length ? "done" : "warn",
    ToolExecutor: (data.tool_calls || []).length ? "done" : "warn",
    CoverageChecker: coverageStatus === "complete" ? "done" : "warn",
    Reporter: data.final_report ? "done" : "warn",
    IncidentRecorder: data.incident_id ? "done" : "warn",
  };
}

function renderPipeline(statusMap) {
  const container = byId("pipeline-steps");
  container.innerHTML = "";
  workflowSteps.forEach((name) => {
    const status = statusMap[name] || "idle";
    const row = document.createElement("div");
    row.className = `pipeline-step ${status}`;
    row.innerHTML = `
      <span class="step-dot" aria-hidden="true"></span>
      <span class="step-name">${escapeHtml(name)}</span>
      <span class="step-note">${escapeHtml(status)}</span>
    `;
    container.appendChild(row);
  });
}

function renderContext(context) {
  const container = byId("alert-context");
  const entries = Object.entries(context);
  container.innerHTML = entries.length
    ? entries
        .map(
          ([key, value]) => `
            <dt>${escapeHtml(key)}</dt>
            <dd>${escapeHtml(formatValue(value))}</dd>
          `,
        )
        .join("")
    : `<dt>state</dt><dd>--</dd>`;
}

function renderSkill(skill, candidates) {
  const container = byId("skill-result");
  if (!skill) {
    container.className = "empty-state";
    container.textContent = candidates.length ? "needs clarification" : "--";
    return;
  }
  container.className = "skill-card";
  const tools = (skill.required_tools || []).map((tool) => `<span class="tag">${escapeHtml(tool)}</span>`).join("");
  const confidence = Math.round(Number(skill.confidence || 0) * 100);
  container.innerHTML = `
    <h3>${escapeHtml(skill.display_name || skill.name)}</h3>
    <div class="tag-row">
      <span class="tag good">${escapeHtml(skill.name)}</span>
      <span class="tag">${confidence}% confidence</span>
      <span class="tag">${escapeHtml(skill.risk_level || "risk --")}</span>
    </div>
    <p>${escapeHtml(skill.reason || "")}</p>
    <div class="tag-row">${tools}</div>
  `;
}

function renderPlan(plan) {
  const container = byId("plan-list");
  if (!plan.length) {
    container.innerHTML = `<li class="empty-state">--</li>`;
    return;
  }
  container.innerHTML = plan
    .map((step) => {
      const title = step.tool_name || step;
      const purpose = step.purpose || "";
      return `<li><strong>${escapeHtml(title)}</strong><br><span class="empty-state">${escapeHtml(purpose)}</span></li>`;
    })
    .join("");
}

function renderDocs(docs) {
  const container = byId("doc-list");
  if (!docs.length) {
    container.innerHTML = `<div class="empty-state">--</div>`;
    return;
  }
  container.innerHTML = docs
    .map(
      (doc) => `
        <article class="doc-card">
          <h3>${escapeHtml(doc.section_title || doc.source_file)}</h3>
          <div class="tag-row">
            <span class="tag good">${escapeHtml(doc.doc_type || "--")}</span>
            <span class="tag">${escapeHtml(String(doc.score ?? "--"))}</span>
            <span class="tag">${escapeHtml(doc.chunk_id || "--")}</span>
          </div>
          <p>${escapeHtml(doc.content_summary || "")}</p>
          <p class="empty-state">${escapeHtml(doc.source_file || "")}</p>
        </article>
      `,
    )
    .join("");
}

function renderTools(toolCalls) {
  const container = byId("tool-timeline");
  if (!toolCalls.length) {
    container.innerHTML = `<div class="empty-state">--</div>`;
    return;
  }
  container.innerHTML = toolCalls
    .map((call) => {
      const statusClass = call.status === "failed" ? "failed" : "";
      const statusTag = call.status === "failed" ? "fail" : "good";
      return `
        <article class="tool-card ${statusClass}">
          <h3>${escapeHtml(call.tool_name || "--")}</h3>
          <div class="tag-row">
            <span class="tag ${statusTag}">${escapeHtml(call.status || "--")}</span>
            <span class="tag">${escapeHtml(String(call.latency_ms ?? "--"))} ms</span>
            <span class="tag">${escapeHtml(call.tool_call_id || "--")}</span>
          </div>
          <div class="tool-meta">
            <span>${escapeHtml(call.result_summary || call.error_message || "")}</span>
            <pre class="tool-args">${escapeHtml(JSON.stringify(call.arguments || {}, null, 2))}</pre>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderCoverage(coverage) {
  const badge = byId("coverage-badge");
  const ratio = Number(coverage.coverage_ratio ?? 0);
  const status = coverage.status || "--";
  badge.textContent = `coverage ${Math.round(ratio * 100)}%`;
  badge.className = `coverage-badge ${status === "complete" ? "complete" : "partial"}`;
  byId("coverage-json").textContent = JSON.stringify(coverage, null, 2);
}

function renderReport(markdown) {
  byId("report-view").innerHTML = markdown ? markdownToHtml(markdown) : `<p class="empty-state">--</p>`;
}

function renderVolumeChart(toolCalls) {
  const container = byId("volume-chart");
  const volumeCall = toolCalls.find((call) => call.tool_name === "query_data_volume");
  const rows = volumeCall?.result?.volume_stats || [];
  if (!rows.length) {
    container.innerHTML = `<div class="empty-state">No volume trend</div>`;
    return;
  }
  const maxValue = Math.max(...rows.map((row) => Number(row.row_count || 0)), 1);
  container.innerHTML = rows
    .map((row) => {
      const rowCount = Number(row.row_count || 0);
      const height = Math.max(8, Math.round((rowCount / maxValue) * 118));
      const anomaly = row.anomaly_flag ? "anomaly" : "";
      return `
        <div class="chart-bar ${anomaly}" title="${escapeHtml(String(rowCount))}">
          <div class="chart-bar-fill" style="height:${height}px"></div>
          <span class="chart-label">${escapeHtml(String(row.stat_date || "").slice(5))}<br>${escapeHtml(String(rowCount))}</span>
        </div>
      `;
    })
    .join("");
}

async function sendChat() {
  const message = byId("chat-input").value.trim();
  const sessionId = byId("session-id").value.trim();
  if (!message || !sessionId) {
    return;
  }
  appendChat("user", message);
  byId("chat-button").disabled = true;
  const response = await fetchJson("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  byId("chat-button").disabled = false;

  if (!response.ok) {
    appendChat("assistant", response.body?.error?.detail || "当前 session 暂无可用上下文。");
    return;
  }
  const data = response.body.data;
  const references = (data.references || [])
    .map((ref) => `${ref.type}:${ref.tool_name || ref.source_file || ref.status || ref.incident_id || ""}`)
    .join(" | ");
  appendChat("assistant", references ? `${data.answer}\n\nrefs: ${references}` : data.answer);
}

function appendChat(role, content) {
  const node = document.createElement("div");
  node.className = `chat-message ${role}`;
  node.innerHTML = `<strong>${role}</strong><p>${escapeHtml(content).replace(/\n/g, "<br>")}</p>`;
  byId("chat-log").appendChild(node);
  byId("chat-log").scrollTop = byId("chat-log").scrollHeight;
}

async function loadIncidents() {
  const response = await fetchJson("/api/incidents?page=1&page_size=5");
  const container = byId("incident-history");
  if (!response.ok || !response.body.data.items.length) {
    container.innerHTML = `<div class="empty-state">--</div>`;
    return;
  }
  container.innerHTML = "";
  response.body.data.items.forEach((incident) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "history-item";
    button.innerHTML = `
      <strong>${escapeHtml(incident.title)}</strong>
      <span>${escapeHtml(incident.selected_diagnosis_skill || "--")} · ${escapeHtml(incident.status)}</span>
    `;
    button.addEventListener("click", () => loadIncident(incident.incident_id));
    container.appendChild(button);
  });
}

async function loadIncident(incidentId) {
  const [incidentResponse, toolResponse] = await Promise.all([
    fetchJson(`/api/incidents/${encodeURIComponent(incidentId)}`),
    fetchJson(`/api/incidents/${encodeURIComponent(incidentId)}/tool-calls`),
  ]);
  if (!incidentResponse.ok) {
    return;
  }
  const incident = incidentResponse.body.data;
  const toolCalls = toolResponse.ok ? toolResponse.body.data.tool_calls : [];
  const data = {
    session_id: incident.session_id,
    incident_id: incident.incident_id,
    status: incident.status,
    alert_context: incident.alert_context || {},
    selected_diagnosis_skill: {
      name: incident.selected_diagnosis_skill,
      display_name: incident.selected_diagnosis_skill,
    },
    candidate_diagnosis_skills: [],
    retrieved_docs: [],
    plan: [],
    tool_calls: toolCalls,
    coverage_result: incident.coverage_result || {},
    final_report: incident.final_report || "",
  };
  currentDiagnosis = data;
  byId("session-id").value = incident.session_id;
  renderDiagnosis(data);
}

function clearResultPanels() {
  byId("alert-context").innerHTML = "";
  byId("skill-result").className = "empty-state";
  byId("skill-result").textContent = "--";
  byId("plan-list").innerHTML = "";
  byId("doc-list").innerHTML = "";
  byId("tool-timeline").innerHTML = "";
  byId("coverage-json").textContent = "{}";
  byId("report-view").innerHTML = "";
  byId("volume-chart").innerHTML = "";
}

function resetResult() {
  currentDiagnosis = null;
  setRunStatus("idle");
  byId("incident-id").textContent = "--";
  byId("selected-skill").textContent = "--";
  byId("doc-count").textContent = "0";
  byId("tool-count").textContent = "0";
  byId("failed-tool-count").textContent = "0";
  byId("coverage-badge").textContent = "coverage --";
  byId("coverage-badge").className = "coverage-badge";
  byId("chat-log").innerHTML = "";
  clearResultPanels();
  renderPipeline({});
}

function showError(message) {
  byId("report-view").innerHTML = `<div class="error-banner">${escapeHtml(message)}</div>`;
  setActiveTab("report");
}

function setRunStatus(status) {
  byId("run-status").textContent = status || "idle";
}

function setBusy(isBusy) {
  byId("diagnose-button").disabled = isBusy;
  byId("diagnose-button").textContent = isBusy ? "Diagnosing" : "Start Diagnosis";
}

async function fetchJson(url, options) {
  try {
    const response = await fetch(url, options);
    const body = await response.json();
    return { ok: response.ok, status: response.status, body };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      body: { error: { detail: error.message || String(error) } },
    };
  }
}

function markdownToHtml(markdown) {
  const lines = markdown.split(/\r?\n/);
  const html = [];
  let inList = false;

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (!line.trim()) {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
      continue;
    }
    if (line.startsWith("## ")) {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
      html.push(`<h2>${formatInline(line.slice(3))}</h2>`);
    } else if (line.startsWith("# ")) {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
      html.push(`<h1>${formatInline(line.slice(2))}</h1>`);
    } else if (line.startsWith("- ")) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${formatInline(line.slice(2))}</li>`);
    } else {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
      html.push(`<p>${formatInline(line)}</p>`);
    }
  }

  if (inList) {
    html.push("</ul>");
  }
  return html.join("");
}

function formatInline(value) {
  return escapeHtml(value).replace(/`([^`]+)`/g, "<code>$1</code>");
}

function formatValue(value) {
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return value ?? "--";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
