import { parseQuestionBankFile } from "./utils/questionBankParser";

const DEFAULT_API_BASE_URL = "/api";
const TOKEN_STORAGE_KEY = "interview-agent-api-token";
const REFRESH_TOKEN_STORAGE_KEY = "interview-agent-refresh-token";
const TENANT_STORAGE_KEY = "interview-agent-tenant-id";
const REQUEST_TIMEOUT_MS = 15000;
const LONG_REQUEST_TIMEOUT_MS = 180000;
const UPLOAD_TIMEOUT_MS = 60000;
const MAX_CONCURRENT_REQUESTS = 2;
const JSON_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let activeRequests = 0;
const requestQueue = [];
let refreshInFlight = null;

function apiBaseUrl() {
  return (import.meta.env.VITE_INTERVIEW_AGENT_API_URL || DEFAULT_API_BASE_URL).replace(/\/$/, "");
}

function electronBridge() {
  return typeof window !== "undefined" ? window.interviewAgent : null;
}

function getStoredToken() {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY) || "";
  } catch (_error) {
    return "";
  }
}

function setStoredToken(token) {
  try {
    if (token) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch (_error) {
    // Ignore storage failures so private browsing modes still work.
  }
}

function getStoredRefreshToken() {
  try {
    return window.localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY) || "";
  } catch (_error) {
    return "";
  }
}

function getStoredTenantId() {
  try {
    return window.localStorage.getItem(TENANT_STORAGE_KEY) || "";
  } catch (_error) {
    return "";
  }
}

function setStoredAuth(response = {}) {
  setStoredToken(response.access_token || "");
  try {
    if (response.refresh_token) {
      window.localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, response.refresh_token);
    } else if (!response.access_token) {
      window.localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
    }
    if (response.tenant_id) {
      window.localStorage.setItem(TENANT_STORAGE_KEY, response.tenant_id);
    } else if (!response.access_token) {
      window.localStorage.removeItem(TENANT_STORAGE_KEY);
    }
  } catch (_error) {
    // Ignore storage failures so private browsing modes still work.
  }
}

function requestId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function buildHeaders({ hasJsonBody = false, auth = true } = {}) {
  const token = getStoredToken();
  const headers = {
    Accept: "application/json",
    "X-Request-ID": requestId()
  };
  if (hasJsonBody) {
    headers["Content-Type"] = "application/json";
  }
  if (auth && token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function normalizeRoute(route) {
  if (typeof route !== "string" || !route.startsWith("/") || route.startsWith("//")) {
    throw new Error("API 路径无效。");
  }
  return route;
}

function normalizeJson(text) {
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch (_error) {
    throw new Error("API 返回了无效 JSON。");
  }
}

function unwrapApiResponse(payload, response) {
  if (
    payload
    && typeof payload === "object"
    && Object.prototype.hasOwnProperty.call(payload, "code")
    && Object.prototype.hasOwnProperty.call(payload, "data")
  ) {
    if (payload.code === 0) {
      return payload.data;
    }
    const message = payload.message || payload.error || `HTTP ${response.status}`;
    throw new Error(message);
  }
  if (!response.ok) {
    throw new Error(payload?.detail || `HTTP ${response.status}`);
  }
  return payload;
}

function enqueueRequest(task) {
  return new Promise((resolve, reject) => {
    requestQueue.push({ task, resolve, reject });
    drainRequestQueue();
  });
}

function drainRequestQueue() {
  while (activeRequests < MAX_CONCURRENT_REQUESTS && requestQueue.length) {
    const item = requestQueue.shift();
    activeRequests += 1;
    item.task()
      .then(item.resolve)
      .catch(item.reject)
      .finally(() => {
        activeRequests -= 1;
        drainRequestQueue();
      });
  }
}

async function requestJson(route, options = {}, attempt = 0) {
  return enqueueRequest(() => executeJsonRequest(route, options, attempt));
}

// 统一 JSON 传输：Electron 下走主进程 IPC（复用鉴权/刷新/重试），浏览器下直连 fetch
async function apiJson(route, options = {}) {
  const bridge = electronBridge();
  if (bridge?.apiRequest) {
    return bridge.apiRequest(route, { method: options.method, body: options.body });
  }
  return requestJson(route, options);
}

async function requestEventStream(route, options = {}, onEvent) {
  return enqueueRequest(() => executeEventStreamRequest(route, options, onEvent));
}

async function executeJsonRequest(route, options = {}, attempt = 0) {
  const method = (options.method || "GET").toUpperCase();
  const hasJsonBody = JSON_METHODS.has(method) && options.body !== undefined;
  const url = `${apiBaseUrl()}${normalizeRoute(route)}`;
  const timeoutMs = options.timeoutMs || REQUEST_TIMEOUT_MS;

  const controller = new AbortController();
  let externallyAborted = Boolean(options.signal?.aborted);
  const abortFromExternalSignal = () => {
    externallyAborted = true;
    controller.abort();
  };
  if (options.signal) {
    if (options.signal.aborted) {
      controller.abort();
    } else {
      options.signal.addEventListener("abort", abortFromExternalSignal, { once: true });
    }
  }
  let timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  const resetTimeout = () => {
    window.clearTimeout(timeout);
    timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  };
  try {
    const response = await fetch(url, {
      method,
      body: options.body,
      headers: buildHeaders({ hasJsonBody, auth: options.auth !== false }),
      mode: "cors",
      credentials: "omit",
      cache: "no-store",
      redirect: "follow",
      referrerPolicy: "strict-origin-when-cross-origin",
      signal: controller.signal
    });
    const text = await response.text();
    const data = normalizeJson(text);
    if (
      response.status === 401
      && attempt === 0
      && options.auth !== false
      && route !== "/auth/refresh"
      && getStoredRefreshToken()
    ) {
      await refreshAccessToken();
      return executeJsonRequest(route, options, attempt + 1);
    }
    return unwrapApiResponse(data, response);
  } catch (error) {
    if (attempt === 0 && method === "GET") {
      return executeJsonRequest(route, options, attempt + 1);
    }
    if (error.name === "AbortError") {
      if (externallyAborted) {
        const stoppedError = new Error("请求已停止。");
        stoppedError.name = "AbortError";
        throw stoppedError;
      }
      throw new Error("请求处理时间较长，模型可能仍在生成。请稍后重试，或检查后端服务日志。");
    }
    if (error instanceof TypeError) {
      throw new Error(`无法连接 API 服务：${apiBaseUrl()}。请检查网络、HTTPS、CSP 或 Nginx 限流配置。`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
    options.signal?.removeEventListener?.("abort", abortFromExternalSignal);
  }
}

async function refreshAccessToken() {
  if (refreshInFlight) {
    return refreshInFlight;
  }
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) {
    throw new Error("登录状态已失效，请重新登录。");
  }
  refreshInFlight = (async () => {
    const response = await fetch(`${apiBaseUrl()}/auth/refresh`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Request-ID": requestId()
      },
      mode: "cors",
      credentials: "omit",
      cache: "no-store",
      redirect: "follow",
      referrerPolicy: "strict-origin-when-cross-origin",
      body: JSON.stringify({
        refresh_token: refreshToken,
        tenant_id: getStoredTenantId() || undefined
      })
    });
    const text = await response.text();
    const payload = unwrapApiResponse(normalizeJson(text), response);
    if (!payload?.access_token || !payload?.refresh_token) {
      throw new Error("登录状态刷新失败，请重新登录。");
    }
    setStoredAuth(payload);
    return payload.access_token;
  })();
  try {
    return await refreshInFlight;
  } catch (error) {
    setStoredAuth({});
    throw error;
  } finally {
    refreshInFlight = null;
  }
}

async function executeEventStreamRequest(route, options = {}, onEvent, attempt = 0) {
  const method = (options.method || "POST").toUpperCase();
  const hasJsonBody = JSON_METHODS.has(method) && options.body !== undefined;
  const url = `${apiBaseUrl()}${normalizeRoute(route)}`;
  const timeoutMs = options.timeoutMs || LONG_REQUEST_TIMEOUT_MS;
  const controller = new AbortController();
  let externallyAborted = Boolean(options.signal?.aborted);
  const abortFromExternalSignal = () => {
    externallyAborted = true;
    controller.abort();
  };
  if (options.signal) {
    if (options.signal.aborted) {
      controller.abort();
    } else {
      options.signal.addEventListener("abort", abortFromExternalSignal, { once: true });
    }
  }
  let timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  const resetTimeout = () => {
    window.clearTimeout(timeout);
    timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  };
  try {
    const response = await fetch(url, {
      method,
      body: options.body,
      headers: buildHeaders({ hasJsonBody, auth: options.auth !== false }),
      mode: "cors",
      credentials: "omit",
      cache: "no-store",
      redirect: "follow",
      referrerPolicy: "strict-origin-when-cross-origin",
      signal: controller.signal
    });
    if (
      response.status === 401
      && attempt === 0
      && options.auth !== false
      && getStoredRefreshToken()
    ) {
      await refreshAccessToken();
      return executeEventStreamRequest(route, options, onEvent, attempt + 1);
    }
    if (!response.ok) {
      const text = await response.text();
      const data = normalizeJson(text);
      return unwrapApiResponse(data, response);
    }
    if (!response.body) {
      throw new Error("浏览器不支持流式响应。");
    }
    const decoder = new TextDecoder();
    const reader = response.body.getReader();
    let buffer = "";
    let finalPayload = null;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      resetTimeout();
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";
      for (const chunk of chunks) {
        const event = parseSseChunk(chunk);
        if (!event) continue;
        onEvent?.(event);
        if (event.event === "message.error") {
          throw new Error(event.data?.message || "流式生成失败。");
        }
        if (event.event === "message.done") {
          finalPayload = event.data;
        }
      }
    }
    if (buffer.trim()) {
      const event = parseSseChunk(buffer);
      if (event) {
        onEvent?.(event);
        if (event.event === "message.error") {
          throw new Error(event.data?.message || "流式生成失败。");
        }
        if (event.event === "message.done") {
          finalPayload = event.data;
        }
      }
    }
    return finalPayload || {};
  } catch (error) {
    if (error.name === "AbortError") {
      if (externallyAborted) {
        const stoppedError = new Error("请求已停止。");
        stoppedError.name = "AbortError";
        throw stoppedError;
      }
      throw new Error("请求处理时间较长，模型可能仍在生成。请稍后重试，或检查后端服务日志。");
    }
    if (error instanceof TypeError) {
      throw new Error(`无法连接 API 服务：${apiBaseUrl()}。请检查网络、HTTPS、CSP 或 Nginx 限流配置。`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
    options.signal?.removeEventListener?.("abort", abortFromExternalSignal);
  }
}

function parseSseChunk(chunk) {
  let event = "message";
  const dataLines = [];
  for (const line of chunk.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }
  if (!dataLines.length) return null;
  const rawData = dataLines.join("\n");
  try {
    return { event, data: JSON.parse(rawData) };
  } catch (_error) {
    return { event, data: { message: rawData } };
  }
}

function chooseFile(accept) {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = accept;
    input.onchange = () => resolve(input.files?.[0] || null);
    input.click();
  });
}

function chooseResumeFile() {
  return chooseFile(".pdf,.md,.markdown,application/pdf,text/markdown,text/plain");
}

function chooseQuestionBankFile() {
  return chooseFile(".json,.csv,application/json,text/csv,text/plain");
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("读取文件失败。"));
    reader.onload = () => {
      const value = String(reader.result || "");
      resolve(value.includes(",") ? value.split(",")[1] : value);
    };
    reader.readAsDataURL(file);
  });
}

function fileToText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("读取题库文件失败。"));
    reader.onload = () => resolve(String(reader.result || ""));
    reader.readAsText(file, "utf-8");
  });
}

async function importResumeFromBrowser() {
  const file = await chooseResumeFile();
  if (!file) {
    return { canceled: true };
  }
  const contentBase64 = await fileToBase64(file);
  const stored = await requestJson("/resumes", {
    method: "POST",
    timeoutMs: UPLOAD_TIMEOUT_MS,
    body: JSON.stringify({
      filename: file.name,
      content_base64: contentBase64
    })
  });
  return { canceled: false, path: file.name, ...stored };
}

async function parseDocumentFromBrowser({ accept } = {}) {
  const file = await chooseFile(accept || ".pdf,.md,.markdown,.txt,application/pdf,text/markdown,text/plain");
  if (!file) {
    return { canceled: true };
  }
  const contentBase64 = await fileToBase64(file);
  const parsed = await requestJson("/resume/parse", {
    method: "POST",
    timeoutMs: UPLOAD_TIMEOUT_MS,
    body: JSON.stringify({
      filename: file.name,
      content_base64: contentBase64
    })
  });
  return { canceled: false, path: file.name, ...parsed };
}

async function importQuestionBankFromBrowser() {
  const file = await chooseQuestionBankFile();
  if (!file) {
    return { canceled: true };
  }
  const text = await fileToText(file);
  const questions = parseQuestionBankFile(file.name, text);
  const stored = await requestJson("/practice/questions/import", {
    method: "POST",
    timeoutMs: UPLOAD_TIMEOUT_MS,
    body: JSON.stringify({ questions })
  });
  return { canceled: false, path: file.name, ...stored };
}

const browserClient = {
  hasToken: () => Boolean(getStoredToken() || getStoredRefreshToken()),
  health: () => requestJson("/health"),
  listIndustries: (targetRole) => {
    const query = targetRole ? `?target_role=${encodeURIComponent(targetRole)}` : "";
    return requestJson(`/metadata/industries${query}`);
  },
  listModels: () => requestJson("/metadata/models"),
  getPracticeLearningPlan: () => requestJson("/practice/learning-plan"),
  listPracticeCategories: () => requestJson("/practice/categories"),
  listJobs: () => requestJson("/jobs"),
  getJob: (jobId) => requestJson(`/jobs/${encodeURIComponent(jobId)}`),
  createJob: (payload) =>
    requestJson("/jobs", {
      method: "POST",
      body: JSON.stringify(payload || {})
    }),
  cancelJob: (jobId) => requestJson(`/jobs/${encodeURIComponent(jobId)}/cancel`, { method: "POST" }),
  runWorkflow: (payload) =>
    requestJson("/workflows/run", {
      method: "POST",
      body: JSON.stringify(payload || {})
    }),
  createEvalRun: (payload) =>
    requestJson("/eval-runs", {
      method: "POST",
      body: JSON.stringify(payload || {})
    }),
  listEvalRuns: () => requestJson("/eval-runs"),
  listAgentTraces: () => requestJson("/ops/traces"),
  getAgentTrace: (traceId) => requestJson(`/ops/traces/${encodeURIComponent(traceId)}`),
  getOpsMetrics: () => requestJson("/ops/metrics"),
  listPracticeQuestions: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.category) params.set("category", filters.category);
    if (filters.year) params.set("year", filters.year);
    if (filters.subject) params.set("subject", filters.subject);
    if (filters.questionType) params.set("question_type", filters.questionType);
    params.set("limit", filters.limit || 30);
    params.set("offset", filters.offset || 0);
    return requestJson(`/practice/questions?${params.toString()}`);
  },
  seedPracticeQuestions: () => requestJson("/practice/questions/seed", { method: "POST" }),
  importPracticeQuestionBank: importQuestionBankFromBrowser,
  getCivilServiceLearningPlan: () => requestJson("/civil-service/learning-plan"),
  listCivilServiceQuestions: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.year) params.set("year", filters.year);
    if (filters.subject) params.set("subject", filters.subject);
    if (filters.questionType) params.set("question_type", filters.questionType);
    params.set("limit", filters.limit || 30);
    params.set("offset", filters.offset || 0);
    return requestJson(`/civil-service/questions?${params.toString()}`);
  },
  seedCivilServiceQuestions: () => requestJson("/civil-service/questions/seed", { method: "POST" }),
  importCivilServiceQuestionBank: importQuestionBankFromBrowser,
  async register(payload) {
    const response = await requestJson("/auth/register", {
      method: "POST",
      body: JSON.stringify({ ...payload, platform: "web" })
    });
    setStoredAuth(response);
    return response;
  },
  async login(payload) {
    const response = await requestJson("/auth/login", {
      method: "POST",
      body: JSON.stringify({ ...payload, platform: "web" })
    });
    setStoredAuth(response);
    return response;
  },
  async devLogin(payload) {
    const response = await requestJson("/auth/dev-login", {
      method: "POST",
      body: JSON.stringify({ ...payload, platform: "web" })
    });
    setStoredAuth(response);
    return response;
  },
  logout: async () => {
    const refreshToken = getStoredRefreshToken();
    try {
      if (refreshToken) {
        await requestJson("/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: refreshToken })
        });
      }
    } finally {
      setStoredAuth({});
    }
    return { ok: true };
  },
  getAccount: () => requestJson("/account"),
  getSettings: () => requestJson("/settings"),
  updateSettings: (payload) =>
    requestJson("/settings", {
      method: "PUT",
      body: JSON.stringify(payload || {})
    }),
  recharge: (payload) =>
    requestJson("/account/recharge", {
      method: "POST",
      body: JSON.stringify(payload || {})
    }),
  listSecurityEvents: () => requestJson("/admin/security/events?limit=50"),
  listRoles: () => requestJson("/admin/roles"),
  grantRole: (payload) =>
    requestJson("/admin/roles/grant", {
      method: "POST",
      body: JSON.stringify(payload || {})
    }),
  revokeRole: (payload) =>
    requestJson("/admin/roles/revoke", {
      method: "POST",
      body: JSON.stringify(payload || {})
    }),
  createPaymentOrder: (payload) =>
    requestJson("/payments/orders", {
      method: "POST",
      body: JSON.stringify(payload || {})
    }),
  getPaymentOrder: (orderId) => requestJson(`/payments/orders/${encodeURIComponent(orderId)}`),
  listResumes: () => requestJson("/resumes"),
  getResume: (resumeId) => requestJson(`/resumes/${resumeId}`),
  deleteResume: (resumeId) => requestJson(`/resumes/${resumeId}`, { method: "DELETE" }),
  listSessions: () => requestJson("/sessions"),
  getSession: (sessionId) => requestJson(`/sessions/${sessionId}`),
  deleteSession: (sessionId) => requestJson(`/sessions/${sessionId}`, { method: "DELETE" }),
  rewindSession: (sessionId, payload) =>
    requestJson(`/sessions/${sessionId}/rewind`, {
      method: "POST",
      body: JSON.stringify(payload || {})
    }),
  importResume: importResumeFromBrowser,
  parseDocument: parseDocumentFromBrowser,
  createSession: (payload) =>
    requestJson("/sessions", {
      method: "POST",
      timeoutMs: LONG_REQUEST_TIMEOUT_MS,
      body: JSON.stringify(payload || {})
    }),
  sendMessage: (payload) =>
    requestJson(`/sessions/${payload.sessionId}/messages`, {
      method: "POST",
      timeoutMs: LONG_REQUEST_TIMEOUT_MS,
      signal: payload.signal,
      body: JSON.stringify({ message: payload.message })
    }),
  streamMessage: (payload, onEvent) =>
    requestEventStream(
      `/sessions/${payload.sessionId}/stream`,
      {
        method: "POST",
        timeoutMs: LONG_REQUEST_TIMEOUT_MS,
        signal: payload.signal,
        body: JSON.stringify({ message: payload.message })
      },
      onEvent
    )
};

browserClient.reviewSite = {
  listPlans: async () => {
    try {
      const data = await requestJson("/review-site/plans");
      return Array.isArray(data) ? data : [];
    } catch (_error) {
      return [];
    }
  },
  createPlan: async (payload) => {
    try {
      const data = await requestJson("/review-site/plans", {
        method: "POST",
        body: JSON.stringify(payload || {})
      });
      return data || {};
    } catch (_error) {
      return {};
    }
  },
  getPlan: async (planId) => {
    try {
      const data = await requestJson(`/review-site/plans/${encodeURIComponent(planId)}`);
      return data || { plan: {}, phases: [], days: [], progresses: [], intro_scripts: [], star_cards: [], a4_memory: [] };
    } catch (_error) {
      return { plan: {}, phases: [], days: [], progresses: [], intro_scripts: [], star_cards: [], a4_memory: [] };
    }
  },
  patchPlan: async (planId, payload) => {
    try {
      const data = await requestJson(`/review-site/plans/${encodeURIComponent(planId)}`, {
        method: "PATCH",
        body: JSON.stringify(payload || {})
      });
      return data || {};
    } catch (_error) {
      return {};
    }
  },
  archivePlan: async (planId) => {
    try {
      const data = await requestJson(`/review-site/plans/${encodeURIComponent(planId)}/archive`, {
        method: "POST"
      });
      return data || {};
    } catch (_error) {
      return {};
    }
  },
  patchProgress: async (taskId, payload) => {
    try {
      const data = await requestJson(`/review-site/progress/task/${encodeURIComponent(taskId)}`, {
        method: "PATCH",
        body: JSON.stringify(payload || {})
      });
      return data || {};
    } catch (_error) {
      return null;
    }
  },
  listIntroScripts: async (planId) => {
    try {
      const data = await requestJson(`/review-site/plans/${encodeURIComponent(planId)}/intro-scripts`);
      return Array.isArray(data) ? data : [];
    } catch (_error) {
      return [];
    }
  },
  listStarCards: async (planId) => {
    try {
      const data = await requestJson(`/review-site/plans/${encodeURIComponent(planId)}/star-cards`);
      return Array.isArray(data) ? data : [];
    } catch (_error) {
      return [];
    }
  },
  listA4Memory: async (planId) => {
    try {
      const data = await requestJson(`/review-site/plans/${encodeURIComponent(planId)}/a4-memory`);
      return Array.isArray(data) ? data : [];
    } catch (_error) {
      return [];
    }
  },
  listPracticeQuestions: async (filters = {}) => {
    try {
      const params = new URLSearchParams();
      if (filters.category) params.set("category", filters.category);
      if (filters.subject) params.set("subject", filters.subject);
      if (filters.question_type) params.set("question_type", filters.question_type);
      if (filters.difficulty) params.set("difficulty", filters.difficulty);
      if (filters.keyword) params.set("keyword", filters.keyword);
      params.set("limit", filters.limit || 30);
      params.set("offset", filters.offset || 0);
      const data = await requestJson(`/review-site/practice-questions?${params.toString()}`);
      return data || { items: [], total: 0, limit: 30, offset: 0 };
    } catch (_error) {
      return { items: [], total: 0, limit: 30, offset: 0 };
    }
  },
  markQuestion: async (questionId, payload) => {
    try {
      const data = await requestJson(`/review-site/practice-questions/${encodeURIComponent(questionId)}/mark`, {
        method: "POST",
        body: JSON.stringify(payload || {})
      });
      return data || {};
    } catch (_error) {
      return null;
    }
  },
  listWrongBook: async () => {
    try {
      const data = await requestJson("/review-site/wrong-book");
      return Array.isArray(data) ? data : [];
    } catch (_error) {
      return [];
    }
  },
  runImport: async (payload) => {
    try {
      const data = await requestJson("/review-site/import", {
        method: "POST",
        timeoutMs: LONG_REQUEST_TIMEOUT_MS,
        body: JSON.stringify(payload || {})
      });
      return data || {};
    } catch (_error) {
      return {};
    }
  },
  generatePlan: async (payload) => {
    try {
      const data = await apiJson("/review-site/planner/generate", {
        method: "POST",
        timeoutMs: LONG_REQUEST_TIMEOUT_MS,
        body: JSON.stringify(payload || {})
      });
      return data || {};
    } catch (_error) {
      return {};
    }
  },
  // ---- Task 6 新增：天/任务/素材 CRUD ----
  createDay: (planId, payload) =>
    apiJson(`/review-site/plans/${encodeURIComponent(planId)}/days`, {
      method: "POST",
      body: JSON.stringify(payload || {})
    }),
  updateDay: (dayId, payload) =>
    apiJson(`/review-site/days/${encodeURIComponent(dayId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload || {})
    }),
  deleteDay: (dayId) =>
    apiJson(`/review-site/days/${encodeURIComponent(dayId)}`, { method: "DELETE" }),
  createTask: (dayId, payload) =>
    apiJson(`/review-site/days/${encodeURIComponent(dayId)}/tasks`, {
      method: "POST",
      body: JSON.stringify(payload || {})
    }),
  updateTask: (taskId, payload) =>
    apiJson(`/review-site/tasks/${encodeURIComponent(taskId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload || {})
    }),
  deleteTask: (taskId) =>
    apiJson(`/review-site/tasks/${encodeURIComponent(taskId)}`, { method: "DELETE" }),
  upsertMaterial: (planId, kind, payload) =>
    apiJson(`/review-site/plans/${encodeURIComponent(planId)}/materials/${encodeURIComponent(kind)}`, {
      method: "POST",
      body: JSON.stringify(payload || {})
    }),
  updateMaterial: (kind, itemId, payload) =>
    apiJson(`/review-site/materials/${encodeURIComponent(kind)}/${encodeURIComponent(itemId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload || {})
    }),
  deleteMaterial: (kind, itemId) =>
    apiJson(`/review-site/materials/${encodeURIComponent(kind)}/${encodeURIComponent(itemId)}`, {
      method: "DELETE"
    }),
  // ---- 打卡 ----
  getToday: (planId) => apiJson(`/review-site/plans/${encodeURIComponent(planId)}/today`),
  checkin: (planId, payload) =>
    apiJson(`/review-site/plans/${encodeURIComponent(planId)}/checkin`, {
      method: "POST",
      body: JSON.stringify(payload || {})
    }),
  listCheckins: (params = {}) => {
    const search = new URLSearchParams();
    if (params.planId) search.set("plan_id", params.planId);
    if (params.dateFrom) search.set("date_from", params.dateFrom);
    if (params.dateTo) search.set("date_to", params.dateTo);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return apiJson(`/review-site/checkins${suffix}`);
  },
  // ---- 刷题作答 v2 ----
  submitAttempt: (questionId, payload) =>
    apiJson(`/review-site/practice-questions/${encodeURIComponent(questionId)}/attempt`, {
      method: "POST",
      timeoutMs: LONG_REQUEST_TIMEOUT_MS,
      body: JSON.stringify(payload || {})
    }),
  listAttempts: (questionId, limit = 20) =>
    apiJson(`/review-site/practice-questions/${encodeURIComponent(questionId)}/attempts?limit=${limit}`)
};

// 学习闭环 v2：驾驶舱 / 成就 / 报告
browserClient.study = {
  dashboard: () => apiJson("/study/dashboard"),
  achievements: () => apiJson("/study/achievements"),
  listReports: (limit = 20) => apiJson(`/interview-reports?limit=${limit}`),
  getReport: (sessionId) => apiJson(`/interview-reports/${encodeURIComponent(sessionId)}`),
  addReportTasks: (planId, sessionId) =>
    apiJson(`/review-site/plans/${encodeURIComponent(planId)}/report-tasks`, {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId })
    })
};

export function getInterviewAgentClient() {
  const bridge = electronBridge();
  if (!bridge) return browserClient;
  return {
    ...bridge,
    ...browserClient,
    // SSE 流式必须走主进程 IPC（file:// 下 fetch 流不可用）
    streamMessage: bridge.streamMessage || browserClient.streamMessage,
    hasToken: () => true
  };
}
