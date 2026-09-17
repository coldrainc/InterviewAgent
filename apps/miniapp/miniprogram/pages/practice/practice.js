const api = require("../../utils/api");
const { config } = require("../../utils/config");
const { normalizeError } = require("../../utils/format");
const { isAuthenticated, requireLogin } = require("../../utils/auth");
const { consumeTaskTarget } = require("../../utils/learning");

Page({
  data: {
    loading: false,
    authenticated: false,
    categories: [],
    selectedCategory: "ai_application",
    questions: [],
    currentQuestion: null,
    currentIndex: 0,
    targetQuestionId: "",
    selectedCategoryLabel: "AI 应用 / 大模型",
    answer: "",
    result: null,
    error: "",
    total: 0,
    hasMore: true,
    startedAt: 0
  },

  onLoad() {
    const authenticated = isAuthenticated();
    this.setData({ authenticated });
    if (authenticated) this.loadPractice();
  },

  onShow() {
    const authenticated = isAuthenticated();
    const target = authenticated ? consumeTaskTarget("practice") : null;
    if (target) this.setData({
      selectedCategory: target.category || this.data.selectedCategory,
      targetQuestionId: target.question_id || ""
    });
    this.setData({ authenticated, questions: authenticated ? this.data.questions : [], currentQuestion: authenticated ? this.data.currentQuestion : null });
    if (authenticated && (target || !this.data.questions.length)) {
      this.loadPractice();
    }
  },

  async loadPractice(append = false) {
    if (!ensureLogin("刷题前需要先登录账号。")) return;
    if (this.data.loading || (append && !this.data.hasMore)) return;
    this.setData({ loading: true, error: "", result: null });
    try {
      const [categories, questions] = await Promise.all([
        api.listPracticeCategories(),
        api.listPracticeQuestions({ category: this.data.selectedCategory, limit: 20, offset: append ? this.data.questions.length : 0 })
      ]);
      this.setData({
        categories,
        questions: append ? mergeById(this.data.questions, questions.items || []) : (questions.items || []),
        selectedCategoryLabel: categoryLabel(categories, this.data.selectedCategory),
        total: questions.total || 0,
        currentIndex: append ? this.data.currentIndex : Math.max(0, (questions.items || []).findIndex((item) => item.id === this.data.targetQuestionId)),
        hasMore: Boolean(questions.has_more),
        answer: "",
        startedAt: Date.now()
      });
      this.syncCurrentQuestion();
      this.setData({ targetQuestionId: "" });
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
    if (this.data.currentIndex >= this.data.questions.length - 6) this.loadPractice(true);
  },

  onReachBottom() { this.loadPractice(true); },

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
  return requireLogin(content);
}

function mergeById(current, incoming) {
  const ids = new Set(current.map((item) => item.id));
  return current.concat(incoming.filter((item) => !ids.has(item.id)));
}
