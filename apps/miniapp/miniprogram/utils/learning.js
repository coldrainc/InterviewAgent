const { config } = require("./config");

function ownerStorageKey(baseKey) {
  return `${baseKey}:${config.tenantId || "default"}:${config.userId || "anonymous"}`;
}

function todayCacheKey() {
  return ownerStorageKey(config.storageKeys.learningTodayCache);
}

function syncCursorKey() {
  return ownerStorageKey(config.storageKeys.learningSyncCursor);
}

function taskTargetKey() {
  return ownerStorageKey(config.storageKeys.learningTaskTarget);
}

function saveTaskTarget(task) {
  const payload = task && task.link_payload && typeof task.link_payload === "object"
    ? task.link_payload
    : {};
  wx.setStorageSync(taskTargetKey(), {
    ...payload,
    task_id: payload.task_id || (task && task.id) || "",
    task_type: (task && task.task_type) || "review",
    title: (task && task.title) || "当前任务"
  });
}

function consumeTaskTarget(expectedType) {
  const key = taskTargetKey();
  const target = wx.getStorageSync(key);
  if (!target || (expectedType && target.task_type !== expectedType)) return null;
  wx.removeStorageSync(key);
  return target;
}

function normalizeToday(payload) {
  const source = payload && typeof payload === "object" ? payload : {};
  const today = source.today && typeof source.today === "object" ? source.today : null;
  const tasks = Array.isArray(today && today.tasks) ? today.tasks.map(normalizeTask) : [];
  return {
    ...source,
    today: today ? {
      ...today,
      tasks,
      total_tasks: tasks.length,
      tasks_done: tasks.filter((task) => task.done).length
    } : null,
    risks: Array.isArray(source.risks) ? source.risks : [],
    next_best_action: source.next_best_action && typeof source.next_best_action === "object"
      ? source.next_best_action
      : {}
  };
}

function normalizeTask(task) {
  const source = task && typeof task === "object" ? task : {};
  const verification = source.verification && typeof source.verification === "object"
    ? source.verification
    : { status: "not_run", mode: "none" };
  const primaryAction = source.primary_action && typeof source.primary_action === "object"
    ? source.primary_action
    : null;
  return {
    ...source,
    title: source.title || "未命名任务",
    status: source.status || "todo",
    version: Number(source.version || 0),
    done: Boolean(source.done),
    verification,
    verificationLabel: verificationLabel(verification),
    primary_action: primaryAction,
    actionLabel: primaryAction && primaryAction.label ? primaryAction.label : "查看"
  };
}

function replaceTask(todayPayload, task) {
  const normalized = normalizeToday(todayPayload);
  if (!normalized.today) return normalized;
  const nextTask = normalizeTask(task);
  const tasks = normalized.today.tasks.map((item) => item.id === nextTask.id ? nextTask : item);
  return normalizeToday({ ...normalized, today: { ...normalized.today, tasks } });
}

function verificationLabel(verification) {
  const status = verification && verification.status;
  if (status === "verified") return "已验证";
  if (status === "rejected") return "证据未通过";
  if (status === "needs_review") return "等待复核";
  return "尚未验证";
}

function idempotencyKey(taskId, action, now = Date.now(), random = Math.random()) {
  return `miniapp:${taskId}:${action}:${now}:${Math.floor(random * 1000000)}`;
}

function commandForTask(task) {
  const command = task && task.primary_action && task.primary_action.command;
  if (["start", "complete", "reopen", "verify"].includes(command)) return command;
  return task && task.done ? "reopen" : "complete";
}

module.exports = {
  commandForTask,
  idempotencyKey,
  normalizeTask,
  normalizeToday,
  replaceTask,
  saveTaskTarget,
  consumeTaskTarget,
  syncCursorKey,
  taskTargetKey,
  todayCacheKey,
  verificationLabel
};
