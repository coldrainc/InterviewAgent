const api = require("../../utils/api");
const { formatDateTime, normalizeError } = require("../../utils/format");
const { isAuthenticated } = require("../../utils/auth");

Page({
  data: {
    loading: false,
    sessions: [],
    authenticated: false,
    hasMore: true,
    error: ""
  },

  onLoad() {
    this.guardAndLoad();
  },

  onShow() {
    this.guardAndLoad();
  },

  guardAndLoad() {
    const authenticated = isAuthenticated();
    this.setData({ authenticated, sessions: authenticated ? this.data.sessions : [] });
    if (authenticated) this.loadSessions();
  },

  async loadSessions(append = false) {
    if (!this.data.authenticated) return;
    if (this.data.loading || (append && !this.data.hasMore)) return;
    this.setData({ loading: true, error: "" });
    try {
      const sessions = await api.listSessions(20, append ? this.data.sessions.length : 0);
      const incoming = sessions.map((item) => ({
        ...item,
        updatedLabel: formatDateTime(item.updated_at),
        modeLabel: item.mode === "candidate" ? "Agent 回答我" : "Agent 面试我"
      }));
      this.setData({
        sessions: append ? mergeById(this.data.sessions, incoming) : incoming,
        hasMore: sessions.length === 20
      });
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  },

  onReachBottom() { this.loadSessions(true); },

  async openSession(event) {
    const sessionId = event.currentTarget.dataset.id;
    try {
      const detail = await api.getSession(sessionId);
      wx.setStorageSync("interview_agent_restore_session", detail);
      wx.switchTab({ url: "/pages/chat/chat" });
    } catch (error) {
      wx.showToast({ title: normalizeError(error), icon: "none" });
    }
  },

  deleteSession(event) {
    const sessionId = event.currentTarget.dataset.id;
    wx.showModal({
      title: "删除历史会话",
      content: "确认删除这段面试记录？",
      confirmColor: "#dc2626",
      success: async (result) => {
        if (!result.confirm) return;
        await this.confirmDelete(sessionId);
      }
    });
  },

  async confirmDelete(sessionId) {
    this.setData({ loading: true, error: "" });
    try {
      await api.deleteSession(sessionId);
      await this.loadSessions();
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  },

  openLogin() {
    wx.switchTab({ url: "/pages/profile/profile" });
  }
});

function mergeById(current, incoming) {
  const ids = new Set(current.map((item) => item.id));
  return current.concat(incoming.filter((item) => !ids.has(item.id)));
}
