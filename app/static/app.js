const STORAGE_KEY = "pyms.apiKey";
const state = {
  selectedTaskId: null,
  eventSource: null,
  wordcloudUrl: null,
  apiKey: localStorage.getItem(STORAGE_KEY) || "",
  queuePage: 1,
  queuePageSize: 8,
  queueState: "all",
  queueTotal: 0,
  resultsPage: 1,
  resultsPageSize: 6,
  resultsView: "clean",
  resultsQuery: "",
  resultsTotal: 0,
};

const elements = {
  authForm: document.getElementById("auth-form"),
  apiKeyInput: document.getElementById("api-key-input"),
  clearApiKey: document.getElementById("clear-api-key"),
  authStatus: document.getElementById("auth-status"),
  submitForm: document.getElementById("submit-form"),
  submitOutput: document.getElementById("submit-output"),
  refreshTasks: document.getElementById("refresh-tasks"),
  taskList: document.getElementById("task-list"),
  selectedTaskLabel: document.getElementById("selected-task-label"),
  commandForm: document.getElementById("command-form"),
  commandInput: document.getElementById("command-input"),
  commandOutput: document.getElementById("command-output"),
  quickButtons: Array.from(document.querySelectorAll(".quick")),
  detail: document.getElementById("task-detail"),
  streamStatus: document.getElementById("stream-status"),
  eventsLog: document.getElementById("events-log"),
  exportButtons: Array.from(document.querySelectorAll("[data-format]")),
  generateWordcloud: document.getElementById("generate-wordcloud"),
  wordcloudPanel: document.getElementById("wordcloud-panel"),
  wordcloudImage: document.getElementById("wordcloud-image"),
  wordcloudMeta: document.getElementById("wordcloud-meta"),
  statTotal: document.getElementById("stat-total"),
  statRunning: document.getElementById("stat-running"),
  statSuccess: document.getElementById("stat-success"),
  statAuth: document.getElementById("stat-auth"),
  queueState: document.getElementById("queue-state"),
  queuePrev: document.getElementById("queue-prev"),
  queueNext: document.getElementById("queue-next"),
  queuePageLabel: document.getElementById("queue-page-label"),
  queueSummary: document.getElementById("queue-summary"),
  queueTableWrap: document.getElementById("queue-table-wrap"),
  resultsView: document.getElementById("results-view"),
  resultsQuery: document.getElementById("results-query"),
  resultsSearch: document.getElementById("results-search"),
  resultsPrev: document.getElementById("results-prev"),
  resultsNext: document.getElementById("results-next"),
  resultsPageLabel: document.getElementById("results-page-label"),
  resultsTableWrap: document.getElementById("results-table-wrap"),
};

function init() {
  elements.apiKeyInput.value = state.apiKey;
  updateAuthStatus();
  elements.authForm.addEventListener("submit", onSaveApiKey);
  elements.clearApiKey.addEventListener("click", onClearApiKey);
  elements.submitForm.addEventListener("submit", onSubmitTask);
  elements.refreshTasks.addEventListener("click", () => void loadTasks());
  elements.commandForm.addEventListener("submit", onCommandRun);
  elements.quickButtons.forEach((button) => button.addEventListener("click", onQuickCommand));
  elements.exportButtons.forEach((button) => button.addEventListener("click", onExport));
  elements.generateWordcloud.addEventListener("click", onGenerateWordcloud);
  elements.queueState.addEventListener("change", async (event) => {
    state.queueState = event.currentTarget.value;
    state.queuePage = 1;
    await refreshQueue();
  });
  elements.queuePrev.addEventListener("click", async () => {
    if (state.queuePage > 1) {
      state.queuePage -= 1;
      await refreshQueue();
    }
  });
  elements.queueNext.addEventListener("click", async () => {
    if (state.queuePage < totalPages(state.queueTotal, state.queuePageSize)) {
      state.queuePage += 1;
      await refreshQueue();
    }
  });
  elements.resultsView.addEventListener("change", async (event) => {
    state.resultsView = event.currentTarget.value;
    state.resultsPage = 1;
    await refreshResults();
  });
  elements.resultsSearch.addEventListener("click", async () => {
    state.resultsQuery = elements.resultsQuery.value.trim();
    state.resultsPage = 1;
    await refreshResults();
  });
  elements.resultsQuery.addEventListener("keydown", async (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      state.resultsQuery = elements.resultsQuery.value.trim();
      state.resultsPage = 1;
      await refreshResults();
    }
  });
  elements.resultsPrev.addEventListener("click", async () => {
    if (state.resultsPage > 1) {
      state.resultsPage -= 1;
      await refreshResults();
    }
  });
  elements.resultsNext.addEventListener("click", async () => {
    if (state.resultsPage < totalPages(state.resultsTotal, state.resultsPageSize)) {
      state.resultsPage += 1;
      await refreshResults();
    }
  });
  void loadTasks();
}

function onSaveApiKey(event) {
  event.preventDefault();
  state.apiKey = elements.apiKeyInput.value.trim();
  localStorage.setItem(STORAGE_KEY, state.apiKey);
  updateAuthStatus();
  renderOutput(elements.commandOutput, { code: 0, message: "API Key 已保存到当前浏览器", data: null });
}

function onClearApiKey() {
  state.apiKey = "";
  elements.apiKeyInput.value = "";
  localStorage.removeItem(STORAGE_KEY);
  updateAuthStatus();
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
}

async function onSubmitTask(event) {
  event.preventDefault();
  const formData = new FormData(elements.submitForm);
  const payload = {
    url: String(formData.get("url") || "").trim(),
    limit: Number(formData.get("limit") || 50),
    depth: Number(formData.get("depth") || 1),
    renderer: String(formData.get("renderer") || "http").trim(),
  };
  const taskName = String(formData.get("task_name") || "").trim();
  if (taskName) {
    payload.task_name = taskName;
  }
  const response = await apiFetch("/v1/crawl/submit", { method: "POST", body: JSON.stringify(payload) });
  renderOutput(elements.submitOutput, response);
  if (response.code === 0 && response.data?.task_id) {
    state.queuePage = 1;
    state.resultsPage = 1;
    selectTask(response.data.task_id);
    await loadTasks();
    await refreshSelectedTask();
  }
}

async function onCommandRun(event) {
  event.preventDefault();
  const command = elements.commandInput.value.trim();
  if (!command) {
    return;
  }
  const response = await apiFetch("/v1/command", { method: "POST", body: JSON.stringify({ command }) });
  renderOutput(elements.commandOutput, response);
  if (response.code === 0 && response.data?.task_id) {
    selectTask(response.data.task_id);
    await loadTasks();
    await refreshSelectedTask();
  }
}

function onQuickCommand(event) {
  if (!state.selectedTaskId) {
    renderOutput(elements.commandOutput, { message: "请先选择任务", code: 1001, data: null });
    return;
  }
  elements.commandInput.value = `${event.currentTarget.dataset.command} task_id=${state.selectedTaskId}`;
}

async function onExport(event) {
  if (!state.selectedTaskId) {
    renderOutput(elements.commandOutput, { message: "请先选择任务再导出", code: 1001, data: null });
    return;
  }
  const format = event.currentTarget.dataset.format;
  const response = await fetch(`/v1/tasks/${encodeURIComponent(state.selectedTaskId)}/export`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({ format }),
  });
  if (!response.ok) {
    renderOutput(elements.commandOutput, await response.json());
    return;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const disposition = response.headers.get("content-disposition") || "";
  const filenameMatch = disposition.match(/filename="([^"]+)"/);
  anchor.href = url;
  anchor.download = filenameMatch ? filenameMatch[1] : `${state.selectedTaskId}.${format}`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function onGenerateWordcloud() {
  if (!state.selectedTaskId) {
    renderOutput(elements.commandOutput, { message: "请先选择任务再生成词云图", code: 1001, data: null });
    return;
  }
  const response = await fetch(`/v1/tasks/${encodeURIComponent(state.selectedTaskId)}/wordcloud`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({ view: "auto", width: 1200, height: 720, top_n: 80 }),
  });
  if (!response.ok) {
    renderOutput(elements.commandOutput, await response.json());
    return;
  }
  const blob = await response.blob();
  if (state.wordcloudUrl) {
    URL.revokeObjectURL(state.wordcloudUrl);
  }
  state.wordcloudUrl = URL.createObjectURL(blob);
  elements.wordcloudImage.src = state.wordcloudUrl;
  elements.wordcloudPanel.classList.remove("hidden");

  const view = response.headers.get("x-wordcloud-view") || "auto";
  let topTermText = "";
  try {
    topTermText = JSON.parse(response.headers.get("x-wordcloud-top-terms") || "[]")
      .slice(0, 5)
      .map((item) => `${item.word}:${item.count}`)
      .join(" | ");
  } catch {
    topTermText = "";
  }
  elements.wordcloudMeta.textContent = `来源=${view}${topTermText ? ` | 热词=${topTermText}` : ""}`;
}

async function loadTasks() {
  const response = await apiFetch("/v1/tasks");
  if (response.code !== 0 || !Array.isArray(response.data)) {
    renderTaskList([]);
    return;
  }
  updateHeroStats(response.data);
  renderTaskList(response.data);
  if (!state.selectedTaskId && response.data.length > 0) {
    selectTask(response.data[0].task_id);
    await refreshSelectedTask();
  }
}

function updateHeroStats(tasks) {
  elements.statTotal.textContent = String(tasks.length);
  elements.statRunning.textContent = String(tasks.filter((task) => task.status === "running").length);
  elements.statSuccess.textContent = String(tasks.filter((task) => task.status === "success").length);
  updateAuthStatus();
}

function updateAuthStatus() {
  const enabled = Boolean(state.apiKey);
  elements.authStatus.textContent = enabled ? "已设置" : "未设置";
  elements.statAuth.textContent = enabled ? "Secured" : "Open";
}

function renderTaskList(tasks) {
  if (!tasks.length) {
    elements.taskList.innerHTML = '<div class="empty-state">当前没有任务</div>';
    return;
  }
  elements.taskList.innerHTML = tasks.map((task) => `
    <button class="task-chip ${task.task_id === state.selectedTaskId ? "active" : ""}" data-task-id="${task.task_id}">
      <strong>${escapeHtml(task.task_name || task.task_id)}</strong>
      <span>${escapeHtml(task.task_id)}</span>
      <span class="status-pill status-${escapeHtml(task.status)}">${escapeHtml(task.status)}</span>
      <span>progress=${escapeHtml(String(task.progress))}% done=${escapeHtml(String(task.done_count))}/${escapeHtml(String(task.total_count))}</span>
    </button>
  `).join("");

  Array.from(elements.taskList.querySelectorAll("[data-task-id]")).forEach((button) => {
    button.addEventListener("click", async () => {
      state.queuePage = 1;
      state.resultsPage = 1;
      selectTask(button.dataset.taskId);
      renderTaskList(tasks);
      await refreshSelectedTask();
    });
  });
}

function selectTask(taskId) {
  state.selectedTaskId = taskId;
  elements.selectedTaskLabel.textContent = taskId ? `当前任务: ${taskId}` : "未选择任务";
  resetWordcloudPreview();
  startEventStream(taskId);
}

async function refreshSelectedTask() {
  if (!state.selectedTaskId) {
    elements.detail.innerHTML = '<div class="empty-state">选择任务后显示详情</div>';
    return;
  }
  const response = await apiFetch(`/v1/tasks/${encodeURIComponent(state.selectedTaskId)}`);
  if (response.code !== 0 || !response.data) {
    renderOutput(elements.commandOutput, response);
    return;
  }
  const task = response.data;
  elements.detail.innerHTML = [
    detailCard("task_id", task.task_id),
    detailCard("status", task.status),
    detailCard("fetch_mode", task.fetch_mode || "http"),
    detailCard("root_url", task.root_url),
    detailCard("progress", `${task.progress}%`),
    detailCard("done_count", String(task.done_count)),
    detailCard("failed_count", String(task.failed_count)),
    detailCard("total_count", String(task.total_count)),
    detailCard("clean_done_count", String(task.clean_done_count)),
  ].join("");
  await Promise.all([refreshQueue(), refreshResults()]);
}

async function refreshQueue() {
  if (!state.selectedTaskId) {
    return;
  }
  const response = await apiFetch(
    `/v1/tasks/${encodeURIComponent(state.selectedTaskId)}/queue?state=${encodeURIComponent(state.queueState)}&page=${state.queuePage}&page_size=${state.queuePageSize}`,
  );
  if (response.code !== 0 || !response.data) {
    renderOutput(elements.commandOutput, response);
    return;
  }
  state.queueTotal = response.data.total;
  renderQueueTable(response.data);
}

async function refreshResults() {
  if (!state.selectedTaskId) {
    return;
  }
  const response = await apiFetch(
    `/v1/tasks/${encodeURIComponent(state.selectedTaskId)}/results?view=${encodeURIComponent(state.resultsView)}&page=${state.resultsPage}&page_size=${state.resultsPageSize}&q=${encodeURIComponent(state.resultsQuery)}`,
  );
  if (response.code !== 0 || !response.data) {
    renderOutput(elements.commandOutput, response);
    return;
  }
  state.resultsTotal = response.data.total;
  renderResultsTable(response.data);
}

function renderQueueTable(queue) {
  const counts = queue.counts_by_state || {};
  elements.queueSummary.innerHTML = ["pending", "running", "done", "failed", "canceled"].map((name) => `
    <div class="summary-pill">
      <span>${escapeHtml(name)}</span>
      <strong>${escapeHtml(String(counts[name] || 0))}</strong>
    </div>
  `).join("");
  elements.queuePageLabel.textContent = `${queue.page} / ${totalPages(queue.total, queue.page_size)}`;
  if (!queue.items.length) {
    elements.queueTableWrap.innerHTML = '<div class="empty-state">当前页没有队列项</div>';
    return;
  }
  elements.queueTableWrap.innerHTML = `
    <table>
      <thead><tr><th>ID</th><th>State</th><th>Hop</th><th>Retry</th><th>URL</th></tr></thead>
      <tbody>
        ${queue.items.map((item) => `
          <tr>
            <td>${escapeHtml(String(item.id))}</td>
            <td>${escapeHtml(item.state)}</td>
            <td>${escapeHtml(String(item.hop_count))}</td>
            <td>${escapeHtml(String(item.retry_count))}</td>
            <td>${escapeHtml(item.url)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderResultsTable(results) {
  elements.resultsPageLabel.textContent = `${results.page} / ${totalPages(results.total, results.page_size)}`;
  if (!results.items.length) {
    elements.resultsTableWrap.innerHTML = '<div class="empty-state">当前页没有结果</div>';
    return;
  }
  const rows = results.items.map((item) => {
    const title = results.view === "raw" ? item.news_title : item.clean_news_title;
    const date = results.view === "raw" ? item.news_date : item.clean_news_date;
    const content = results.view === "raw" ? item.news_content : item.clean_news_content;
    const source = results.view === "raw" ? (item.source_url || "-") : (item.dedup_key || "-");
    return `
      <tr>
        <td>${escapeHtml(String(item.id))}</td>
        <td>${escapeHtml(date || "-")}</td>
        <td>${escapeHtml(title || "-")}</td>
        <td>${escapeHtml(content || "-")}</td>
        <td>${escapeHtml(source)}</td>
      </tr>
    `;
  }).join("");
  elements.resultsTableWrap.innerHTML = `
    <table>
      <thead><tr><th>ID</th><th>Date</th><th>Title</th><th>Content</th><th>${results.view === "raw" ? "Source URL" : "Dedup Key"}</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function detailCard(label, value) {
  return `<dl class="detail-card"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></dl>`;
}

function startEventStream(taskId) {
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
  elements.eventsLog.innerHTML = "";
  if (!taskId) {
    elements.streamStatus.textContent = "未连接";
    return;
  }
  const apiKeyQuery = state.apiKey ? `&api_key=${encodeURIComponent(state.apiKey)}` : "";
  state.eventSource = new EventSource(`/v1/events/stream?task_id=${encodeURIComponent(taskId)}${apiKeyQuery}`);
  elements.streamStatus.textContent = "连接中";
  state.eventSource.onopen = () => { elements.streamStatus.textContent = "已连接"; };
  state.eventSource.onerror = () => { elements.streamStatus.textContent = "连接结束"; };
  state.eventSource.onmessage = async (event) => {
    appendLogLine(JSON.parse(event.data));
    await loadTasks();
    await refreshSelectedTask();
  };
}

function appendLogLine(payload) {
  const line = document.createElement("div");
  line.className = "log-line";
  line.textContent = `[${payload.timestamp}] ${payload.event_type} ${JSON.stringify(payload.payload)}`;
  elements.eventsLog.prepend(line);
}

function resetWordcloudPreview() {
  if (state.wordcloudUrl) {
    URL.revokeObjectURL(state.wordcloudUrl);
    state.wordcloudUrl = null;
  }
  elements.wordcloudPanel.classList.add("hidden");
  elements.wordcloudImage.removeAttribute("src");
  elements.wordcloudMeta.textContent = "尚未生成";
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, { headers: buildHeaders(options.headers || {}), ...options });
  return response.json();
}

function buildHeaders(extraHeaders = {}) {
  const headers = { "Content-Type": "application/json", ...extraHeaders };
  if (state.apiKey) {
    headers.Authorization = `Bearer ${state.apiKey}`;
    headers["X-API-Key"] = state.apiKey;
  }
  return headers;
}

function renderOutput(target, response) {
  target.textContent = JSON.stringify(response, null, 2);
}

function totalPages(total, pageSize) {
  return Math.max(1, Math.ceil(Number(total || 0) / Number(pageSize || 1)));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

init();
