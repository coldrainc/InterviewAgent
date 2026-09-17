const api = require("./api");
const { config } = require("./config");

function isAuthenticated() {
  api.restoreToken();
  return Boolean(config.apiToken);
}

function requireLogin(content = "登录后才能使用这项功能。") {
  if (isAuthenticated()) return true;
  wx.showModal({
    title: "需要登录",
    content,
    confirmText: "去登录",
    success(result) {
      if (result.confirm) wx.switchTab({ url: "/pages/profile/profile" });
    }
  });
  return false;
}

function clearPrivateData() {
  const ownerSuffix = `${config.tenantId || "default"}:${config.userId || "anonymous"}`;
  [
    `${config.storageKeys.learningTodayCache}:${ownerSuffix}`,
    `${config.storageKeys.learningSyncCursor}:${ownerSuffix}`,
    config.storageKeys.selectedResumeId,
    `${config.storageKeys.selectedResumeId}:name`,
    "interview_agent_restore_session"
  ].forEach((key) => wx.removeStorageSync(key));
  api.setAuthTokens({});
}

module.exports = { clearPrivateData, isAuthenticated, requireLogin };
