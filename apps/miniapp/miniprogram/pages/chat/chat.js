const api = require("../../utils/api");
const { config } = require("../../utils/config");
const { normalizeError } = require("../../utils/format");
const { requireLogin } = require("../../utils/auth");
const {
  getInterviewSetup,
  getIndustryLabel,
  getSetupSummary,
  buildInterviewGoal
} = require("../../utils/interviewSetup");
const { consumeTaskTarget } = require("../../utils/learning");

Page({
  data: {
    healthText: "检查中",
    authenticated: false,
    workspaceMode: "candidate",
    kits: [],
    kitsHasMore: true,
    kitsLoading: false,
    kitRole: "AI 应用工程师",
    industries: [],
    selectedIndustryLabel: "互联网行业",
    setup: getInterviewSetup(),
    setupSummary: "",
    sessionId: "",
    selectedResumeId: "",
    selectedResumeName: "",
    input: "",
    busy: false,
    taskTarget: null,
    messages: []
  },

  onLoad() {
    api.restoreToken();
    this.loadSetup();
    this.loadHealth();
  },

  onShow() {
    api.restoreToken();
    const authenticated = Boolean(config.apiToken);
    this.setData({
      authenticated,
      sessionId: authenticated ? this.data.sessionId : "",
      messages: authenticated ? this.data.messages : [],
      kits: authenticated ? this.data.kits : [],
      selectedResumeId: authenticated ? this.data.selectedResumeId : "",
      selectedResumeName: authenticated ? this.data.selectedResumeName : ""
    });
    if (!authenticated) return;
    this.loadSetup();
    this.loadIndustries();
    this.loadSelectedResume();
    const taskTarget = consumeTaskTarget("interview");
    if (taskTarget) this.setData({ taskTarget });
    this.restoreSessionIfNeeded();
    this.loadKits();
  },

  setWorkspaceMode(event) {
    this.setData({ workspaceMode: event.currentTarget.dataset.mode });
  },

  onKitRoleInput(event) {
    this.setData({ kitRole: event.detail.value });
  },

  async loadKits(append = false) {
    if (!config.apiToken) return;
    if (this.data.kitsLoading || (append && !this.data.kitsHasMore)) return;
    this.setData({ kitsLoading: true });
    try {
      const raw = await api.listInterviewKits({ limit: 20, offset: append ? this.data.kits.length : 0 });
      const kits = raw.map((kit) => ({
        ...kit,
        questionCount: Array.isArray(kit.questions) ? kit.questions.length : 0
      }));
      this.setData({ kits: append ? mergeById(this.data.kits, kits) : kits, kitsHasMore: raw.length === 20 });
    } catch (error) {
      this.appendSystemMessage(`加载面试题单失败：${normalizeError(error)}`);
    } finally {
      this.setData({ kitsLoading: false });
    }
  },

  onKitsScrollLower() {
    this.loadKits(true);
  },

  onReachBottom() {
    if (this.data.workspaceMode === "interviewer") this.loadKits(true);
  },

  async createKit() {
    if (!requireLogin("创建面试题单前需要先登录。") || this.data.busy) return;
    this.setData({ busy: true });
    try {
      await api.createInterviewKit({
        title: `${this.data.kitRole} 面试题单`,
        target_role: this.data.kitRole,
        seniority: "高级",
        duration_minutes: 45,
        dimensions: ["技术深度", "系统设计", "表达与协作"]
      });
      await this.loadKits();
      wx.showToast({ title: "题单已生成", icon: "success" });
    } catch (error) {
      this.appendSystemMessage(`创建题单失败：${normalizeError(error)}`);
    } finally {
      this.setData({ busy: false });
    }
  },

  loadSetup() {
    const setup = getInterviewSetup();
    const taskTarget = this.data.taskTarget || {};
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
        mode: taskTarget.mode || setup.mode,
        industry: setup.industry,
        target_role: setup.targetRole,
        seniority: setup.seniority,
        interview_goal: taskTarget.focus || buildInterviewGoal(setup),
        focus_areas: setup.focusAreas,
        resume_id: this.data.selectedResumeId || undefined,
        plan_task_id: taskTarget.task_id || undefined
      });
      this.setData({
        sessionId: response.session_id,
        messages: [{ role: "agent", text: response.message }]
      });
      this.setData({ taskTarget: null });
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
    wx.navigateTo({ url: "/pages/resumes/resumes" });
  },

  openSetupPage() {
    wx.navigateTo({ url: "/pages/setup/setup" });
  },

  openHistoryPage() {
    wx.navigateTo({ url: "/pages/history/history" });
  },

  openLogin() {
    wx.switchTab({ url: "/pages/profile/profile" });
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

function mergeById(current, incoming) {
  const ids = new Set(current.map((item) => item.id));
  return current.concat(incoming.filter((item) => !ids.has(item.id)));
}

const ensureLogin = requireLogin;
