const api = require("../../utils/api");
const { config } = require("../../utils/config");
const { normalizeError } = require("../../utils/format");
const {
  getInterviewSetup,
  getIndustryLabel,
  getSetupSummary,
  buildInterviewGoal
} = require("../../utils/interviewSetup");

Page({
  data: {
    healthText: "检查中",
    industries: [],
    selectedIndustryLabel: "互联网行业",
    setup: getInterviewSetup(),
    setupSummary: "",
    sessionId: "",
    selectedResumeId: "",
    selectedResumeName: "",
    input: "",
    busy: false,
    messages: []
  },

  onLoad() {
    api.restoreToken();
    this.loadSetup();
    this.loadHealth();
  },

  onShow() {
    this.loadSetup();
    this.loadIndustries();
    this.loadSelectedResume();
    this.restoreSessionIfNeeded();
  },

  loadSetup() {
    const setup = getInterviewSetup();
    const selectedIndustryLabel = getIndustryLabel(this.data.industries, setup.industry);
    this.setData({
      setup,
      selectedIndustryLabel,
      setupSummary: getSetupSummary(setup, selectedIndustryLabel)
    });
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
      setup: {
        ...this.data.setup,
        mode: detail.mode || this.data.setup.mode
      },
      setupSummary: getSetupSummary(
        { ...this.data.setup, mode: detail.mode || this.data.setup.mode },
        this.data.selectedIndustryLabel
      )
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
      const industries = await api.listIndustries(this.data.setup.targetRole || "AI 应用工程师");
      const selectedIndustryLabel = getIndustryLabel(industries, this.data.setup.industry);
      this.setData({
        industries,
        selectedIndustryLabel,
        setupSummary: getSetupSummary(this.data.setup, selectedIndustryLabel)
      });
    } catch (_error) {
      const fallback = [{ value: "internet", label: "互联网行业" }];
      const selectedIndustryLabel = getIndustryLabel(fallback, this.data.setup.industry);
      this.setData({
        industries: fallback,
        selectedIndustryLabel,
        setupSummary: getSetupSummary(this.data.setup, selectedIndustryLabel)
      });
    }
  },

  onInput(event) {
    this.setData({ input: event.detail.value });
  },

  async startInterview() {
    if (this.data.busy) return;
    if (!ensureLogin("开始面试前需要先登录，登录后会保存会话、简历和用量记录。")) return;
    const setup = getInterviewSetup();
    this.setData({ busy: true, messages: [] });
    try {
      const response = await api.createSession({
        offline: true,
        mode: setup.mode,
        industry: setup.industry,
        target_role: setup.targetRole,
        seniority: setup.seniority,
        interview_goal: buildInterviewGoal(setup),
        focus_areas: setup.focusAreas,
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

  openSetupPage() {
    wx.switchTab({ url: "/pages/setup/setup" });
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
