const state = {
  selectedTaskId: null,
  eventSource: null,
  wordcloudUrl: null,
};

const elements = {
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
};

function init() {
  elements.submitForm.addEventListener("submit", onSubmitTask);
  elements.refreshTasks.addEventListener("click", () => void loadTasks());
  elements.commandForm.addEventListener("submit", onCommandRun);
  elements.quickButtons.forEach((button) => button.addEventListener("click", onQuickCommand));
  elements.exportButtons.forEach((button) => button.addEventListener("click", onExport));
  elements.generateWordcloud.addEventListener("click", onGenerateWordcloud);
  void loadTasks();
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
  const response = await apiFetch("/v1/crawl/submit", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  renderOutput(elements.submitOutput, response);
  if (response.code === 0 && response.data && response.data.task_id) {
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
  const response = await apiFetch("/v1/command", {
    method: "POST",
    body: JSON.stringify({ command }),
  });
  renderOutput(elements.commandOutput, response);
  if (response.code === 0 && response.data && response.data.task_id) {
    selectTask(response.data.task_id);
    await loadTasks();
    await refreshSelectedTask();
  }
}

function onQuickCommand(event) {
  const taskId = state.selectedTaskId;
  if (!taskId) {
    renderOutput(elements.commandOutput, { message: "请先选择任务", code: 1001, data: null });
    return;
  }
  const base = event.currentTarget.dataset.command;
  elements.commandInput.value = `${base} task_id=${taskId}`;
}

async function onExport(event) {
  const taskId = state.selectedTaskId;
  if (!taskId) {
    renderOutput(elements.commandOutput, { message: "请先选择任务再导出", code: 1001, data: null });
    return;
  }
  const format = event.currentTarget.dataset.format;
  const response = await fetch(`/v1/tasks/${encodeURIComponent(taskId)}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format }),
  });

  if (!response.ok) {
    const errorBody = await response.json();
    renderOutput(elements.commandOutput, errorBody);
    return;
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const disposition = response.headers.get("content-disposition") || "";
  const filenameMatch = disposition.match(/filename="([^"]+)"/);
  anchor.href = url;
  anchor.download = filenameMatch ? filenameMatch[1] : `${taskId}.${format}`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  renderOutput(elements.commandOutput, {
    code: 0,
    message: `已导出 ${format.toUpperCase()}`,
    data: { task_id: taskId },
  });
}

async function loadTasks() {
  const response = await apiFetch("/v1/tasks");
  if (response.code !== 0 || !Array.isArray(response.data)) {
    renderTaskList([]);
    return;
  }
  const tasks = response.data;
  updateHeroStats(tasks);
  renderTaskList(tasks);
  if (!state.selectedTaskId && tasks.length > 0) {
    selectTask(tasks[0].task_id);
    await refreshSelectedTask();
  }
}

function updateHeroStats(tasks) {
  elements.statTotal.textContent = String(tasks.length);
  elements.statRunning.textContent = String(tasks.filter((task) => task.status === "running").length);
  elements.statSuccess.textContent = String(tasks.filter((task) => task.status === "success").length);
}

function renderTaskList(tasks) {
  if (tasks.length === 0) {
    elements.taskList.innerHTML = '<div class="muted">当前没有任务</div>';
    return;
  }

  elements.taskList.innerHTML = tasks
    .map(
      (task) => `
        <button class="task-chip ${task.task_id === state.selectedTaskId ? "active" : ""}" data-task-id="${task.task_id}">
          <strong>${escapeHtml(task.task_name || task.task_id)}</strong>
          <span>${escapeHtml(task.task_id)}</span>
          <span>status=${escapeHtml(task.status)} progress=${escapeHtml(String(task.progress))}% done=${escapeHtml(String(task.done_count))}/${escapeHtml(String(task.total_count))}</span>
        </button>
      `,
    )
    .join("");

  Array.from(elements.taskList.querySelectorAll("[data-task-id]")).forEach((button) => {
    button.addEventListener("click", async () => {
      selectTask(button.dataset.taskId);
      await refreshSelectedTask();
      renderTaskList(tasks);
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
    elements.detail.innerHTML = '<div class="muted">选择任务后显示详情</div>';
    return;
  }
  const [taskResponse, queueResponse, resultsResponse] = await Promise.all([
    apiFetch(`/v1/tasks/${encodeURIComponent(state.selectedTaskId)}`),
    apiFetch(`/v1/tasks/${encodeURIComponent(state.selectedTaskId)}/queue?state=all`),
    apiFetch(`/v1/tasks/${encodeURIComponent(state.selectedTaskId)}/results?view=clean&page=1&page_size=3`),
  ]);

  if (taskResponse.code !== 0 || !taskResponse.data) {
    renderOutput(elements.commandOutput, taskResponse);
    return;
  }

  const task = taskResponse.data;
  const queue = queueResponse.code === 0 && queueResponse.data ? queueResponse.data : { total: 0, items: [] };
  const results = resultsResponse.code === 0 && resultsResponse.data ? resultsResponse.data : { total: 0, items: [] };

  const latestTitles = results.items
    .map((item) => item.clean_news_title || "(empty)")
    .join(" | ");

  elements.detail.innerHTML = [
    detailCard("task_id", task.task_id),
    detailCard("status", task.status),
    detailCard("fetch_mode", task.fetch_mode || "http"),
    detailCard("root_url", task.root_url),
    detailCard("progress", `${task.progress}%`),
    detailCard("queue_total", String(queue.total)),
    detailCard("done_failed", `${task.done_count}/${task.failed_count}`),
    detailCard("clean_done", String(task.clean_done_count)),
    detailCard("latest_clean", latestTitles || "暂无"),
  ].join("");
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

  elements.streamStatus.textContent = "连接中";
  const source = new EventSource(`/v1/events/stream?task_id=${encodeURIComponent(taskId)}`);
  state.eventSource = source;

  source.onopen = () => {
    elements.streamStatus.textContent = "已连接";
  };

  source.onerror = () => {
    elements.streamStatus.textContent = "连接结束";
  };

  source.onmessage = async (event) => {
    const payload = JSON.parse(event.data);
    appendLogLine(payload);
    await refreshSelectedTask();
    await loadTasks();
  };
}

async function onGenerateWordcloud() {
  const taskId = state.selectedTaskId;
  if (!taskId) {
    renderOutput(elements.commandOutput, { message: "请先选择任务再生成词云图", code: 1001, data: null });
    return;
  }

  const response = await fetch(`/v1/tasks/${encodeURIComponent(taskId)}/wordcloud`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ view: "auto", width: 1200, height: 720, top_n: 80 }),
  });

  if (!response.ok) {
    const errorBody = await response.json();
    renderOutput(elements.commandOutput, errorBody);
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
  const topTerms = response.headers.get("x-wordcloud-top-terms") || "[]";
  let topTermText = "";
  try {
    const terms = JSON.parse(topTerms);
    topTermText = terms.slice(0, 5).map((item) => `${item.word}:${item.count}`).join(" | ");
  } catch {
    topTermText = "";
  }
  elements.wordcloudMeta.textContent = `来源=${view}${topTermText ? ` | 热词=${topTermText}` : ""}`;
  renderOutput(elements.commandOutput, { code: 0, message: "词云图已生成", data: { task_id: taskId, view } });
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

function appendLogLine(payload) {
  const line = document.createElement("div");
  line.className = "log-line";
  line.textContent = `[${payload.timestamp}] ${payload.event_type} ${JSON.stringify(payload.payload)}`;
  elements.eventsLog.prepend(line);
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json();
  return body;
}

function renderOutput(target, response) {
  target.textContent = JSON.stringify(response, null, 2);
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
