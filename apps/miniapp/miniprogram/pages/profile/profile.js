const api = require("../../utils/api");
const { clearPrivateData, isAuthenticated } = require("../../utils/auth");
const { normalizeError } = require("../../utils/format");

Page({
  data: {
    loading: false,
    authenticated: false,
    registerMode: false,
    email: "",
    password: "",
    displayName: "",
    account: null,
    error: ""
  },

  onShow() {
    const authenticated = isAuthenticated();
    this.setData({ authenticated });
    if (authenticated) this.loadAccount();
  },

  async loadAccount() {
    this.setData({ loading: true, error: "" });
    try {
      const account = await api.account();
      this.setData({ account, authenticated: true });
    } catch (error) {
      this.setData({ error: normalizeError(error) });
      if (error.status === 401) clearPrivateData();
    } finally {
      this.setData({ loading: false });
    }
  },

  onInput(event) {
    this.setData({ [event.currentTarget.dataset.key]: event.detail.value });
  },

  toggleMode() {
    this.setData({ registerMode: !this.data.registerMode, error: "" });
  },

  async submitAuth() {
    if (this.data.loading) return;
    const email = this.data.email.trim();
    const password = this.data.password.trim();
    if (!email || password.length < 8) {
      this.setData({ error: "请输入有效邮箱，密码至少 8 位。" });
      return;
    }
    this.setData({ loading: true, error: "" });
    try {
      const auth = this.data.registerMode
        ? await api.register(email, password, this.data.displayName.trim())
        : await api.login(email, password);
      api.setAuthTokens(auth);
      this.setData({ authenticated: true, password: "" });
      await this.loadAccount();
      wx.showToast({ title: this.data.registerMode ? "注册成功" : "登录成功", icon: "success" });
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  },

  async wechatLogin() {
    if (this.data.loading) return;
    this.setData({ loading: true, error: "" });
    try {
      const code = await wxLogin();
      const auth = await api.wechatLogin(code);
      api.setAuthTokens(auth);
      this.setData({ authenticated: true });
      await this.loadAccount();
      wx.showToast({ title: "微信登录成功", icon: "success" });
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  },

  logout() {
    clearPrivateData();
    this.setData({ authenticated: false, account: null, password: "", error: "" });
    wx.showToast({ title: "已退出登录", icon: "success" });
  },

  openResumes() { wx.navigateTo({ url: "/pages/resumes/resumes" }); },
  openHistory() { wx.navigateTo({ url: "/pages/history/history" }); },
  openPrivacy() { wx.navigateTo({ url: "/pages/privacy/privacy" }); }
});

function wxLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(result) { result.code ? resolve(result.code) : reject(new Error("微信登录未返回 code")); },
      fail(error) { reject(new Error(error.errMsg || "微信登录失败")); }
    });
  });
}
