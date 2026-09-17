const api = require("../../utils/api");
const { config } = require("../../utils/config");
const { normalizeError } = require("../../utils/format");
const {
  commandForTask,
  idempotencyKey,
  normalizeToday,
  replaceTask,
  saveTaskTarget,
  syncCursorKey,
  todayCacheKey
} = require("../../utils/learning");

Page({
  data: {
    loading: false,
    commandTaskId: "",
    authenticated: false,
    offline: false,
    staleAt: "",
    dashboard: normalizeToday(null),
    error: ""
  },

  onLoad() {
    api.restoreToken();
    this.restoreCache();
  },

  onShow() {
    api.restoreToken();
    const authenticated = Boolean(config.apiToken);
    this.setData({ authenticated });
    if (authenticated) this.refresh();
  },

  restoreCache() {
    const cached = wx.getStorageSync(todayCacheKey());
    if (!cached || !cached.dashboard) return;
    this.setData({
      dashboard: normalizeToday(cached.dashboard),
      offline: true,
      staleAt: cached.savedAt || ""
    });
  },

  async refresh() {
    if (!config.apiToken) {
      this.setData({ authenticated: false, loading: false });
      return;
    }
    this.setData({ loading: true, authenticated: true, error: "" });
    try {
      const dashboard = normalizeToday(await api.learningToday());
      const savedAt = new Date().toISOString();
      wx.setStorageSync(todayCacheKey(), { dashboard, savedAt });
      this.setData({ dashboard, offline: false, staleAt: savedAt });
      await this.pullChanges();
    } catch (error) {
      const cached = wx.getStorageSync(todayCacheKey());
      this.setData({
        error: cached ? "网络不可用，当前为只读缓存。" : normalizeError(error),
        offline: Boolean(cached)
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  async pullChanges() {
    const cursorKey = syncCursorKey();
    const cursor = wx.getStorageSync(cursorKey) || "";
    try {
      const result = await api.pullLearningChanges(cursor);
      if (result && result.next_cursor) wx.setStorageSync(cursorKey, result.next_cursor);
    } catch (error) {
      if (error.status === 400 && cursor) {
        wx.removeStorageSync(cursorKey);
        const result = await api.pullLearningChanges("");
        if (result && result.next_cursor) wx.setStorageSync(cursorKey, result.next_cursor);
        return;
      }
      throw error;
    }
  },

  async runTask(event) {
    const taskId = event.currentTarget.dataset.id;
    const tasks = (this.data.dashboard.today && this.data.dashboard.today.tasks) || [];
    const task = tasks.find((item) => item.id === taskId);
    if (!task || this.data.commandTaskId || this.data.offline) return;
    const action = commandForTask(task);
    this.setData({ commandTaskId: taskId, error: "" });
    try {
      const result = await api.executeLearningTask(
        task.id,
        { action, expected_version: task.version },
        idempotencyKey(task.id, action)
      );
      const dashboard = replaceTask(this.data.dashboard, result.task);
      this.setData({ dashboard });
      wx.setStorageSync(todayCacheKey(), { dashboard, savedAt: new Date().toISOString() });
      await this.refresh();
    } catch (error) {
      const currentTask = error.details && error.details.current_task;
      if (error.status === 409 && currentTask) {
        this.setData({
          dashboard: replaceTask(this.data.dashboard, currentTask),
          error: "任务已在其他设备更新，已同步服务端最新状态。"
        });
      } else {
        this.setData({ error: normalizeError(error) });
      }
    } finally {
      this.setData({ commandTaskId: "" });
    }
  },

  openTask(task) {
    if (!task) return;
    saveTaskTarget(task);
    if (task.task_type === "practice") {
      wx.switchTab({ url: "/pages/practice/practice" });
      return;
    }
    if (task.task_type === "interview") {
      wx.switchTab({ url: "/pages/chat/chat" });
      return;
    }
    wx.switchTab({ url: "/pages/review/review" });
  },

  openTaskCard(event) {
    const taskId = event.currentTarget.dataset.id;
    const tasks = (this.data.dashboard.today && this.data.dashboard.today.tasks) || [];
    this.openTask(tasks.find((item) => item.id === taskId));
  },

  openLogin() {
    wx.switchTab({ url: "/pages/profile/profile" });
  },

  startInterview() {
    wx.switchTab({ url: "/pages/chat/chat" });
  }
});
