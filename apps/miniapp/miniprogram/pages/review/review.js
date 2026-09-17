const api = require("../../utils/api");
const { requireLogin } = require("../../utils/auth");
const { config } = require("../../utils/config");
const { normalizeError } = require("../../utils/format");
const { consumeTaskTarget } = require("../../utils/learning");

Page({
  data: {
    authenticated: false,
    loading: false,
    plans: [],
    hasMore: true,
    selectedPlanId: "",
    activeTask: null,
    role: "AI 应用工程师",
    focus: "项目深挖、系统设计、Agent 工程化",
    days: 14,
    dayOptions: [7, 14, 21, 30],
    note: "",
    message: "",
    error: ""
  },

  onShow() {
    api.restoreToken();
    const authenticated = Boolean(config.apiToken);
    const target = authenticated ? consumeTaskTarget(null) : null;
    this.setData({
      authenticated,
      plans: authenticated ? this.data.plans : [],
      selectedPlanId: authenticated ? ((target && target.plan_id) || this.data.selectedPlanId) : "",
      activeTask: authenticated ? target : null,
      note: authenticated ? this.data.note : ""
    });
    if (authenticated) this.loadPlans();
  },

  async loadPlans(append = false) {
    if (!config.apiToken) return;
    if (this.data.loading || (append && !this.data.hasMore)) return;
    this.setData({ loading: true, error: "" });
    try {
      const plans = await api.listReviewPlans({ limit: 20, offset: append ? this.data.plans.length : 0 });
      this.setData({
        plans: append ? mergeById(this.data.plans, plans) : plans,
        hasMore: plans.length === 20,
        selectedPlanId: this.data.selectedPlanId || (plans[0] && plans[0].id) || ""
      });
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  },

  onReachBottom() { this.loadPlans(true); },

  onInput(event) {
    this.setData({ [event.currentTarget.dataset.key]: event.detail.value });
  },

  onDaysChange(event) {
    this.setData({ days: this.data.dayOptions[Number(event.detail.value)] || 14 });
  },

  selectPlan(event) {
    this.setData({ selectedPlanId: event.currentTarget.dataset.id });
  },

  async generatePlan() {
    if (!requireLogin("生成复习计划前需要先登录。") || this.data.loading) return;
    this.setData({ loading: true, error: "", message: "正在生成你的复习计划…" });
    try {
      const result = await api.generateReviewPlan({
        title: `${this.data.role} 面试计划`,
        target_role: this.data.role,
        seniority: "高级",
        total_days: this.data.days,
        hours_per_day: 1.5,
        focus_areas: this.data.focus.split(/[、,，]/).map((item) => item.trim()).filter(Boolean),
        resume_id: wx.getStorageSync(config.storageKeys.selectedResumeId) || undefined,
        use_history: true
      });
      this.setData({ selectedPlanId: result.plan_id, message: "计划已生成" });
      await this.loadPlans();
    } catch (error) {
      this.setData({ error: normalizeError(error), message: "" });
    } finally {
      this.setData({ loading: false });
    }
  },

  async checkin() {
    if (!requireLogin("完成计划打卡前需要先登录。") || !this.data.selectedPlanId || this.data.loading) return;
    this.setData({ loading: true, error: "", message: "" });
    try {
      const result = await api.checkinReviewPlan(this.data.selectedPlanId, {
        elapsed_minutes: 30,
        note: this.data.note
      });
      this.setData({
        message: `打卡成功，连续 ${(result.streak && result.streak.current_streak) || 0} 天`,
        note: ""
      });
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
