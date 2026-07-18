const { config } = require("./config");

function request(path, options = {}) {
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
  setApiToken(token || "");
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
