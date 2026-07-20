const api = require("../../utils/api");
const { config } = require("../../utils/config");
const { normalizeError } = require("../../utils/format");

Page({
  data: {
    loading: false,
    me: null,
    account: null,
    health: null,
    error: "",
    rechargeOptions: ["10", "50", "100"],
    rechargeStatus: ""
  },

  onLoad() {
    api.restoreToken();
    this.load();
  },

  onShow() {
    this.load();
  },

  async load() {
    this.setData({ loading: true, error: "", rechargeStatus: "" });
    try {
      const [me, account, health] = await Promise.all([
        api.me().catch(() => null),
        api.account().catch(() => null),
        api.health()
      ]);
      this.setData({ me, account, health });
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  },

  async devLogin() {
    this.setData({ loading: true, error: "" });
    try {
      const auth = await api.devLogin();
      api.setAuthTokens(auth);
      await this.load();
      wx.showToast({ title: "已登录", icon: "success" });
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  },

  async wechatLogin() {
    this.setData({ loading: true, error: "" });
    try {
      const code = await wxLogin();
      const auth = await api.wechatLogin(code);
      api.setAuthTokens(auth);
      await this.load();
      wx.showToast({ title: "微信登录成功", icon: "success" });
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  },

  logout() {
    api.setAuthTokens({});
    wx.removeStorageSync(config.storageKeys.selectedResumeId);
    wx.removeStorageSync(`${config.storageKeys.selectedResumeId}:name`);
    this.setData({ me: null, account: null });
    wx.showToast({ title: "已清除本地登录", icon: "success" });
  },

  async recharge(event) {
    const amount = event.currentTarget.dataset.amount;
    if (!config.apiToken) {
      wx.showModal({
        title: "需要登录",
        content: "充值积分前需要先登录账号。",
        confirmText: "去登录"
      });
      return;
    }
    this.setData({ loading: true, error: "", rechargeStatus: "" });
    try {
      const account = await api.recharge({
        amount_credits: amount,
        payment_provider: "miniapp-mock",
        external_order_id: `miniapp-${Date.now()}`
      });
      this.setData({ account, rechargeStatus: `已充值 ${amount} 积分` });
      wx.showToast({ title: "充值成功", icon: "success" });
    } catch (error) {
      this.setData({ error: normalizeError(error) });
    } finally {
      this.setData({ loading: false });
    }
  },

  openPrivacy() {
    wx.navigateTo({ url: "/pages/privacy/privacy" });
  }
});

function wxLogin() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(result) {
        if (result.code) {
          resolve(result.code);
          return;
        }
        reject(new Error("微信登录未返回 code"));
      },
      fail(error) {
        reject(new Error(error.errMsg || "微信登录失败"));
      }
    });
  });
}
