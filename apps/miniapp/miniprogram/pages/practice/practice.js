const api = require("../../utils/api");
const { config } = require("../../utils/config");
const { normalizeError } = require("../../utils/format");

Page({
  data: {
    loading: false,
    categories: [],
    selectedCategory: "ai_application",
    questions: [],
    currentQuestion: null,
    currentIndex: 0,
    selectedCategoryLabel: "AI 应用 / 大模型",
    answer: "",
    result: null,
    error: "",
    total: 0,
    startedAt: 0
  },

  onLoad() {
    api.restoreToken();
    this.loadPractice();
  },

  onShow() {
    if (!this.data.questions.length) {
      this.loadPractice();
    }
  },

  async loadPractice() {
    if (!ensureLogin("刷题前需要先登录账号。")) return;
    this.setData({ loading: true, error: "", result: null });
    try {
      const [categories, questions] = await Promise.all([
        api.listPracticeCategories(),
        api.listPracticeQuestions({ category: this.data.selectedCategory, limit: 50 })
      ]);
      this.setData({
        categories,
        questions: questions.items || [],
        selectedCategoryLabel: categoryLabel(categories, this.data.selectedCategory),
        total: questions.total || 0,
        currentIndex: 0,
        answer: "",
        startedAt: Date.now()
      });
      this.syncCurrentQuestion();
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  },

  async seedQuestions() {
    if (!ensureLogin("初始化练习样题前需要先登录账号。")) return;
    this.setData({ loading: true, error: "" });
    try {
      await api.seedPracticeQuestions();
      await this.loadPractice();
      wx.showToast({ title: "样题已初始化", icon: "success" });
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  },

  onCategoryChange(event) {
    const category = this.data.categories[Number(event.detail.value)];
    if (!category) return;
    this.setData({
      selectedCategory: category.value,
      selectedCategoryLabel: category.label
    }, () => this.loadPractice());
  },

  onAnswerInput(event) {
    this.setData({ answer: event.detail.value });
  },

  chooseOption(event) {
    this.setData({ answer: event.currentTarget.dataset.value || "" });
  },

  nextQuestion() {
    if (!this.data.questions.length) return;
    this.setData({
      currentIndex: (this.data.currentIndex + 1) % this.data.questions.length,
      answer: "",
      result: null,
      startedAt: Date.now()
    });
    this.syncCurrentQuestion();
  },

  async submit() {
    const question = this.data.questions[this.data.currentIndex];
    if (!question || this.data.loading) return;
    const elapsedSeconds = Math.max(0, Math.round((Date.now() - this.data.startedAt) / 1000));
    this.setData({ loading: true, error: "" });
    try {
      const result = await api.submitPracticeAttempt({
        questionId: question.id,
        answer: this.data.answer,
        elapsedSeconds
      });
      this.setData({ result });
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  },

  syncCurrentQuestion() {
    const question = this.data.questions[this.data.currentIndex];
    if (!question) {
      this.setData({ currentQuestion: null });
      return;
    }
    const choices = (question.choices || []).map((text, index) => ({
      key: String.fromCharCode(65 + index),
      text
    }));
    this.setData({
      currentQuestion: {
        ...question,
        choices
      }
    });
  }
});

function categoryLabel(categories, value) {
  const category = (categories || []).find((item) => item.value === value);
  return (category && category.label) || value || "全部";
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
