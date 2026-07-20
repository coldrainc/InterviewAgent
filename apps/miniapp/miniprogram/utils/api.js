const { config } = require("./config");

function request(path, options = {}, attempt = 0) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.header || {})
  };
  if (config.apiToken) {
    headers.Authorization = `Bearer ${config.apiToken}`;
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url: `${config.apiBaseUrl}${path}`,
      method: options.method || "GET",
      data: options.data,
      header: headers,
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(unwrapResponse(response.data));
          return;
        }
        if (response.statusCode === 401 && attempt === 0 && config.refreshToken && path !== "/auth/refresh") {
          refreshAccessToken()
            .then(() => request(path, options, attempt + 1).then(resolve).catch(reject))
            .catch(reject);
          return;
        }
        reject(new Error(response.data?.message || response.data?.detail || `HTTP ${response.statusCode}`));
      },
      fail(error) {
        reject(new Error(error.errMsg || "请求 Interview Agent API 失败"));
      }
    });
  });
}

function unwrapResponse(payload) {
  if (payload && typeof payload === "object" && "code" in payload && "data" in payload) {
    if (payload.code === 0) {
      return payload.data;
    }
    throw new Error(payload.message || `API_ERROR_${payload.code}`);
  }
  return payload;
}

function restoreToken() {
  const token = wx.getStorageSync(config.storageKeys.token);
  const refreshToken = wx.getStorageSync(config.storageKeys.refreshToken);
  const tenantId = wx.getStorageSync(config.storageKeys.tenantId);
  setApiToken(token || "");
  config.refreshToken = refreshToken || "";
  config.tenantId = tenantId || "default";
  return config.apiToken;
}

function health() {
  return request("/health");
}

function devLogin(payload = {}) {
  return request("/auth/dev-login", {
    method: "POST",
    data: {
      user_id: "miniapp-dev-user",
      display_name: "小程序开发用户",
      platform: "miniapp",
      ...payload
    }
  });
}

function wechatLogin(code, payload = {}) {
  return request("/auth/wechat/login", {
    method: "POST",
    data: {
      code,
      platform: "miniapp",
      ...payload
    }
  });
}

function setApiToken(token) {
  config.apiToken = token || "";
  if (token) {
    wx.setStorageSync(config.storageKeys.token, token);
  } else {
    wx.removeStorageSync(config.storageKeys.token);
  }
}

function setAuthTokens(auth = {}) {
  setApiToken(auth.access_token || "");
  config.refreshToken = auth.refresh_token || "";
  config.tenantId = auth.tenant_id || "default";
  if (config.refreshToken) {
    wx.setStorageSync(config.storageKeys.refreshToken, config.refreshToken);
  } else {
    wx.removeStorageSync(config.storageKeys.refreshToken);
  }
  if (config.tenantId) {
    wx.setStorageSync(config.storageKeys.tenantId, config.tenantId);
  }
}

function refreshAccessToken() {
  return request("/auth/refresh", {
    method: "POST",
    data: {
      refresh_token: config.refreshToken,
      tenant_id: config.tenantId
    },
    header: {}
  }, 1).then((auth) => {
    setAuthTokens(auth);
    return auth.access_token;
  }).catch((error) => {
    setAuthTokens({});
    throw error;
  });
}

function me() {
  return request("/me");
}

function account() {
  return request("/account");
}

function recharge(payload = {}) {
  return request("/account/recharge", {
    method: "POST",
    data: payload
  });
}

function listIndustries(targetRole = "AI 应用工程师") {
  return request(`/metadata/industries?target_role=${encodeURIComponent(targetRole)}`);
}

function createSession(payload) {
  return request("/sessions", {
    method: "POST",
    data: payload
  });
}

function listResumes() {
  return request("/resumes");
}

function getResume(resumeId) {
  return request(`/resumes/${resumeId}`);
}

function importResume({ filename, contentBase64, sourcePath }) {
  return request("/resumes", {
    method: "POST",
    data: {
      filename,
      content_base64: contentBase64,
      source_path: sourcePath
    }
  });
}

function deleteResume(resumeId) {
  return request(`/resumes/${resumeId}`, {
    method: "DELETE"
  });
}

function listSessions(limit = 50) {
  return request(`/sessions?limit=${limit}`);
}

function getSession(sessionId) {
  return request(`/sessions/${sessionId}`);
}

function deleteSession(sessionId) {
  return request(`/sessions/${sessionId}`, {
    method: "DELETE"
  });
}

function sendMessage(sessionId, message) {
  return request(`/sessions/${sessionId}/messages`, {
    method: "POST",
    data: { message }
  });
}

function streamMessage(sessionId, message) {
  return request(`/sessions/${sessionId}/stream`, {
    method: "POST",
    data: { message }
  }).catch((error) => {
    throw error;
  });
}

module.exports = {
  restoreToken,
  health,
  devLogin,
  wechatLogin,
  setApiToken,
  setAuthTokens,
  me,
  account,
  recharge,
  listIndustries,
  createSession,
  listResumes,
  getResume,
  importResume,
  deleteResume,
  listSessions,
  getSession,
  deleteSession,
  sendMessage,
  streamMessage
};
