const { config } = require("./config");

function request(path, options = {}, attempt = 0) {
  const clientRequestId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const headers = {
    "Content-Type": "application/json",
    "X-Request-ID": clientRequestId,
    "X-Client-Request-Id": clientRequestId,
    "X-Client-Platform": "miniapp",
    "X-Client-Version": config.clientVersion,
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
        reject(apiError(response));
      },
      fail(error) {
        reject(new Error(error.errMsg || "请求 Interview Agent API 失败"));
      }
    });
  });
}

function apiError(response) {
  const payload = response.data || {};
  const detail = payload.details || (typeof payload.detail === "object" ? payload.detail : null);
  const error = new Error(
    payload.message || (typeof payload.detail === "string" ? payload.detail : "") || `HTTP ${response.statusCode}`
  );
  error.status = response.statusCode;
  error.code = payload.error || (detail && detail.code) || "";
  error.details = detail;
  return error;
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
  const userId = wx.getStorageSync(config.storageKeys.userId);
  setApiToken(token || "");
  config.refreshToken = refreshToken || "";
  config.tenantId = tenantId || "default";
  config.userId = userId || "anonymous";
  return config.apiToken;
}

function health() {
  return request("/health");
}

function login(email, password) {
  return request("/auth/login", {
    method: "POST",
    data: {
      email: String(email || "").trim(),
      password: String(password || "").trim(),
      platform: "miniapp"
    }
  });
}

function register(email, password, displayName) {
  return request("/auth/register", {
    method: "POST",
    data: {
      email: String(email || "").trim(),
      password: String(password || "").trim(),
      display_name: String(displayName || "").trim(),
      platform: "miniapp"
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
  config.userId = auth.user_id || "anonymous";
  if (config.refreshToken) {
    wx.setStorageSync(config.storageKeys.refreshToken, config.refreshToken);
  } else {
    wx.removeStorageSync(config.storageKeys.refreshToken);
  }
  if (config.tenantId) {
    wx.setStorageSync(config.storageKeys.tenantId, config.tenantId);
  }
  if (auth.user_id) {
    wx.setStorageSync(config.storageKeys.userId, auth.user_id);
  } else {
    wx.removeStorageSync(config.storageKeys.userId);
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

function learningToday() {
  return request("/learning/today");
}

function getLearningTask(taskId) {
  return request(`/learning/tasks/${encodeURIComponent(taskId)}`);
}

function executeLearningTask(taskId, command, idempotencyKey) {
  return request(`/learning/tasks/${encodeURIComponent(taskId)}/commands`, {
    method: "POST",
    data: command,
    header: { "Idempotency-Key": idempotencyKey }
  });
}

function pullLearningChanges(cursor, limit = 100) {
  const query = [`limit=${encodeURIComponent(limit)}`];
  if (cursor) query.push(`cursor=${encodeURIComponent(cursor)}`);
  return request(`/learning/sync?${query.join("&")}`);
}

function listReviewPlans({ limit = 20, offset = 0 } = {}) {
  return request(`/review-site/plans?limit=${limit}&offset=${offset}`);
}

function generateReviewPlan(payload) {
  return request("/review-site/planner/generate", { method: "POST", data: payload });
}

function checkinReviewPlan(planId, payload) {
  return request(`/review-site/plans/${encodeURIComponent(planId)}/checkin`, {
    method: "POST",
    data: payload
  });
}

function listInterviewKits({ limit = 20, offset = 0 } = {}) {
  return request(`/interviewer-workspace/kits?limit=${limit}&offset=${offset}`);
}

function createInterviewKit(payload) {
  return request("/interviewer-workspace/kits", { method: "POST", data: payload });
}

function listIndustries(targetRole = "AI 应用工程师") {
  return request(`/metadata/industries?target_role=${encodeURIComponent(targetRole)}`);
}

function listPracticeCategories() {
  return request("/practice/categories");
}

function listPracticeQuestions(filters = {}) {
  const params = [];
  if (filters.category) params.push(`category=${encodeURIComponent(filters.category)}`);
  if (filters.year) params.push(`year=${encodeURIComponent(filters.year)}`);
  if (filters.subject) params.push(`subject=${encodeURIComponent(filters.subject)}`);
  if (filters.questionType) params.push(`question_type=${encodeURIComponent(filters.questionType)}`);
  params.push(`limit=${encodeURIComponent(filters.limit || 30)}`);
  params.push(`offset=${encodeURIComponent(filters.offset || 0)}`);
  return request(`/practice/questions?${params.join("&")}`);
}

function seedPracticeQuestions() {
  return request("/practice/questions/seed", { method: "POST" });
}

function submitPracticeAttempt({ questionId, answer, elapsedSeconds }) {
  return request("/practice/attempt", {
    method: "POST",
    data: {
      question_id: questionId,
      answer,
      elapsed_seconds: elapsedSeconds
    }
  });
}

function createSession(payload) {
  return request("/sessions", {
    method: "POST",
    data: payload
  });
}

function listResumes({ limit = 20, offset = 0 } = {}) {
  return request(`/resumes?limit=${limit}&offset=${offset}`);
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

function listSessions(limit = 20, offset = 0) {
  return request(`/sessions?limit=${limit}&offset=${offset}`);
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
  login,
  register,
  wechatLogin,
  setApiToken,
  setAuthTokens,
  me,
  account,
  recharge,
  learningToday,
  getLearningTask,
  executeLearningTask,
  pullLearningChanges,
  listReviewPlans,
  generateReviewPlan,
  checkinReviewPlan,
  listInterviewKits,
  createInterviewKit,
  listIndustries,
  listPracticeCategories,
  listPracticeQuestions,
  seedPracticeQuestions,
  submitPracticeAttempt,
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
