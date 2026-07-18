const api = require("../../utils/api");
const { config } = require("../../utils/config");
const {
  modeOptions,
  getInterviewSetup,
  saveInterviewSetup,
  getModeLabel,
  getIndustryLabel,
  getSetupSummary
} = require("../../utils/interviewSetup");

Page({
  data: {
    healthText: "检查中",
    setup: getInterviewSetup(),
    modeOptions,
    industries: [],
    selectedModeLabel: "Agent 面试我",
    selectedIndustryLabel: "互联网行业",
    selectedResumeId: "",
    selectedResumeName: "",
    setupSummary: ""
  },

  onLoad() {
    api.restoreToken();
    this.loadSetup();
    this.loadHealth();
    this.loadIndustries();
  },

  onShow() {
    this.loadSetup();
    this.loadSelectedResume();
  },

  loadSetup() {
    const setup = getInterviewSetup();
    const selectedIndustryLabel = getIndustryLabel(this.data.industries, setup.industry);
    this.setData({
      setup,
      selectedModeLabel: getModeLabel(setup.mode),
      selectedIndustryLabel,
      setupSummary: getSetupSummary(setup, selectedIndustryLabel)
    });
  },

  loadSelectedResume() {
    const selectedResumeId = wx.getStorageSync(config.storageKeys.selectedResumeId) || "";
    const selectedResumeName = wx.getStorageSync(`${config.storageKeys.selectedResumeId}:name`) || "";
    this.setData({ selectedResumeId, selectedResumeName });
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
      this.setData({
        industries: fallback,
        selectedIndustryLabel: getIndustryLabel(fallback, this.data.setup.industry)
      });
    }
  },

  onModeChange(event) {
    const selected = this.data.modeOptions[Number(event.detail.value)];
    if (!selected) return;
    const setup = saveInterviewSetup({ mode: selected.value });
    this.setData({
      setup,
      selectedModeLabel: selected.label,
      setupSummary: getSetupSummary(setup, this.data.selectedIndustryLabel)
    });
  },

  onIndustryChange(event) {
    const selected = this.data.industries[Number(event.detail.value)];
    if (!selected) return;
    const setup = saveInterviewSetup({ industry: selected.value });
    this.setData({
      setup,
      selectedIndustryLabel: selected.label,
      setupSummary: getSetupSummary(setup, selected.label)
    });
  },

  onSetupInput(event) {
    const key = event.currentTarget.dataset.key;
    if (!key) return;
    const value = event.detail.value;
    const setup = saveInterviewSetup({ [key]: value });
    this.setData({
      [`setup.${key}`]: value,
      setupSummary: getSetupSummary(setup, this.data.selectedIndustryLabel)
    });
  },

  onTargetRoleBlur() {
    this.loadIndustries();
  },

  openResumePage() {
    wx.switchTab({ url: "/pages/resumes/resumes" });
  },

  startInterview() {
    wx.switchTab({ url: "/pages/chat/chat" });
  }
});
