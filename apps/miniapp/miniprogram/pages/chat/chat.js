const api = require("../../utils/api");
const { config } = require("../../utils/config");
const { normalizeError } = require("../../utils/format");

Page({
  data: {
    healthText: "检查中",
    industries: [],
    selectedIndustry: "internet",
    selectedIndustryLabel: "互联网行业",
    sessionId: "",
    selectedResumeId: "",
    selectedResumeName: "",
    input: "",
    busy: false,
    messages: [],
    modeOptions: [
      { value: "interviewer", label: "Agent 面试我" },
      { value: "candidate", label: "Agent 回答我" }
    ],
    selectedMode: "interviewer",
    selectedModeLabel: "Agent 面试我"
  },

  onLoad() {
    api.restoreToken();
    this.loadHealth();
    this.loadIndustries();
    this.loadSelectedResume();
  },

  onShow() {
    this.loadSelectedResume();
    this.restoreSessionIfNeeded();
  },

  loadSelectedResume() {
    const selectedResumeId = wx.getStorageSync(config.storageKeys.selectedResumeId) || "";
    const selectedResumeName = wx.getStorageSync(`${config.storageKeys.selectedResumeId}:name`) || "";
    this.setData({ selectedResumeId, selectedResumeName });
  },

  restoreSessionIfNeeded() {
    const detail = wx.getStorageSync("interview_agent_restore_session");
    if (!detail || !detail.id) return;
    wx.removeStorageSync("interview_agent_restore_session");
    this.setData({
      sessionId: detail.id,
      messages: turnsToMessages(detail.turns || []),
      selectedMode: detail.mode || this.data.selectedMode,
      selectedModeLabel: detail.mode === "candidate" ? "Agent 回答我" : "Agent 面试我"
    });
    wx.showToast({ title: "已恢复会话", icon: "success" });
  },

  async loadHealth() {
    try {
      const health = await api.health();
      this.setData({ healthText: health.status === "ok" ? "已连接" : "服务异常" });
    } catch (error) {
      this.setData({ healthText: error.message });
    }
  },

  async loadIndustries() {
    try {
      const industries = await api.listIndustries();
      this.setData({
        industries,
        selectedIndustry: industries[0]?.value || "internet",
        selectedIndustryLabel: industries[0]?.label || "互联网行业"
      });
    } catch (_error) {
      this.setData({
        industries: [{ value: "internet", label: "互联网行业" }],
        selectedIndustry: "internet",
        selectedIndustryLabel: "互联网行业"
      });
    }
  },

  onIndustryChange(event) {
    const index = Number(event.detail.value);
    const selected = this.data.industries[index];
    if (selected) {
      this.setData({
        selectedIndustry: selected.value,
        selectedIndustryLabel: selected.label
      });
    }
  },

  onModeChange(event) {
    const index = Number(event.detail.value);
    const selected = this.data.modeOptions[index];
    if (selected) {
      this.setData({
        selectedMode: selected.value,
        selectedModeLabel: selected.label
      });
    }
  },

  onInput(event) {
    this.setData({ input: event.detail.value });
  },

  async startInterview() {
    if (this.data.busy) return;
    if (!ensureLogin("开始面试前需要先登录，登录后会保存会话、简历和用量记录。")) return;
    this.setData({ busy: true, messages: [] });
    try {
      const response = await api.createSession({
        offline: true,
        mode: this.data.selectedMode,
        industry: this.data.selectedIndustry,
        target_role: "AI 应用工程师",
        seniority: "高级",
        interview_goal: "请基于我的简历和 AI 项目经历进行真实面试。",
        focus_areas: ["简历项目深挖", "RAG / Agent 生产化", "评测、上线、安全与观测"],
        resume_id: this.data.selectedResumeId || undefined
      });
      this.setData({
        sessionId: response.session_id,
        messages: [{ role: "agent", text: response.message }]
      });
    } catch (error) {
      this.appendSystemMessage(`创建会话失败：${normalizeError(error)}`);
    } finally {
      this.setData({ busy: false });
    }
  },

  async send() {
    const message = this.data.input.trim();
    if (!message || !this.data.sessionId || this.data.busy) return;
    if (!ensureLogin("发送回答前需要先登录。")) return;
    this.setData({
      input: "",
      busy: true,
      messages: [...this.data.messages, { role: "user", text: message }]
    });
    try {
      const response = await api.sendMessage(this.data.sessionId, message);
      this.setData({
        messages: [...this.data.messages, { role: "agent", text: response.message }]
      });
    } catch (error) {
      this.appendSystemMessage(`发送失败：${normalizeError(error)}`);
    } finally {
      this.setData({ busy: false });
    }
  },

  appendSystemMessage(text) {
    this.setData({
      messages: [...this.data.messages, { role: "system", text }]
    });
  },

  openResumePage() {
    wx.switchTab({ url: "/pages/resumes/resumes" });
  },

  openHistoryPage() {
    wx.switchTab({ url: "/pages/history/history" });
  }
});

function turnsToMessages(turns) {
  const messages = [];
  turns.forEach((turn) => {
    if (turn.interviewer) {
      messages.push({ role: "agent", text: turn.interviewer });
    }
    if (turn.candidate) {
      messages.push({ role: "user", text: turn.candidate });
    }
  });
  return messages;
}

function ensureLogin(content) {
  api.restoreToken();
  if (config.apiToken) return true;
  wx.showModal({
    title: "需要登录",
    content,
    confirmText: "去登录",
    success(result) {
      if (result.confirm) {
        wx.switchTab({ url: "/pages/profile/profile" });
      }
    }
  });
  return false;
}
