const api = require("../../utils/api");
const { formatDateTime, normalizeError } = require("../../utils/format");

Page({
  data: {
    loading: false,
    sessions: [],
    error: ""
  },

  onLoad() {
    api.restoreToken();
    this.loadSessions();
  },

  onShow() {
    this.loadSessions();
  },

  async loadSessions() {
    this.setData({ loading: true, error: "" });
    try {
      const sessions = await api.listSessions(50);
      this.setData({
        sessions: sessions.map((item) => ({
          ...item,
          updatedLabel: formatDateTime(item.updated_at),
          modeLabel: item.mode === "candidate" ? "Agent 回答我" : "Agent 面试我"
        }))
      });
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  },

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
  }
});
