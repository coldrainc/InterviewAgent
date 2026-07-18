const DEFAULT_API_BASE_URL = "/api";
const TOKEN_STORAGE_KEY = "interview-agent-api-token";
const REQUEST_TIMEOUT_MS = 15000;
const LONG_REQUEST_TIMEOUT_MS = 180000;
const UPLOAD_TIMEOUT_MS = 60000;
const MAX_CONCURRENT_REQUESTS = 2;
const JSON_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let activeRequests = 0;
const requestQueue = [];

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

async function requestEventStream(route, options = {}, onEvent) {
  return enqueueRequest(() => executeEventStreamRequest(route, options, onEvent));
}

async function executeJsonRequest(route, options = {}, attempt = 0) {
  const method = (options.method || "GET").toUpperCase();
  const hasJsonBody = JSON_METHODS.has(method) && options.body !== undefined;
  const url = `${apiBaseUrl()}${normalizeRoute(route)}`;
  const timeoutMs = options.timeoutMs || REQUEST_TIMEOUT_MS;

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
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
    return unwrapApiResponse(data, response);
  } catch (error) {
    if (attempt === 0 && method === "GET") {
      return executeJsonRequest(route, options, attempt + 1);
    }
    if (error.name === "AbortError") {
      throw new Error("请求处理时间较长，模型可能仍在生成。请稍后重试，或检查后端服务日志。");
    }
    if (error instanceof TypeError) {
      throw new Error(`无法连接 API 服务：${apiBaseUrl()}。请检查网络、HTTPS、CSP 或 Nginx 限流配置。`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

async function executeEventStreamRequest(route, options = {}, onEvent) {
  const method = (options.method || "POST").toUpperCase();
  const hasJsonBody = JSON_METHODS.has(method) && options.body !== undefined;
  const url = `${apiBaseUrl()}${normalizeRoute(route)}`;
  const timeoutMs = options.timeoutMs || LONG_REQUEST_TIMEOUT_MS;
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
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
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";
      for (const chunk of chunks) {
        const event = parseSseChunk(chunk);
        if (!event) continue;
        onEvent?.(event);
        if (event.event === "message.done") {
          finalPayload = event.data;
        }
      }
    }
    if (buffer.trim()) {
      const event = parseSseChunk(buffer);
      if (event) {
        onEvent?.(event);
        if (event.event === "message.done") {
          finalPayload = event.data;
        }
      }
    }
    return finalPayload || {};
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("请求处理时间较长，模型可能仍在生成。请稍后重试，或检查后端服务日志。");
    }
    if (error instanceof TypeError) {
      throw new Error(`无法连接 API 服务：${apiBaseUrl()}。请检查网络、HTTPS、CSP 或 Nginx 限流配置。`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
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

function chooseResumeFile() {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".pdf,.md,.markdown,application/pdf,text/markdown,text/plain";
    input.onchange = () => resolve(input.files?.[0] || null);
    input.click();
  });
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

const browserClient = {
  hasToken: () => Boolean(getStoredToken()),
  health: () => requestJson("/health"),
  listIndustries: (targetRole) => {
    const query = targetRole ? `?target_role=${encodeURIComponent(targetRole)}` : "";
    return requestJson(`/metadata/industries${query}`);
  },
  listModels: () => requestJson("/metadata/models"),
  async register(payload) {
    const response = await requestJson("/auth/register", {
      method: "POST",
      body: JSON.stringify({ ...payload, platform: "web" })
    });
    setStoredToken(response.access_token || "");
    return response;
  },
  async login(payload) {
    const response = await requestJson("/auth/login", {
      method: "POST",
      body: JSON.stringify({ ...payload, platform: "web" })
    });
    setStoredToken(response.access_token || "");
    return response;
  },
  async devLogin(payload) {
    const response = await requestJson("/auth/dev-login", {
      method: "POST",
      body: JSON.stringify({ ...payload, platform: "web" })
    });
    setStoredToken(response.access_token || "");
    return response;
  },
  logout: async () => {
    setStoredToken("");
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
  importResume: importResumeFromBrowser,
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
      body: JSON.stringify({ message: payload.message })
    }),
  streamMessage: (payload, onEvent) =>
    requestEventStream(
      `/sessions/${payload.sessionId}/stream`,
      {
        method: "POST",
        timeoutMs: LONG_REQUEST_TIMEOUT_MS,
        body: JSON.stringify({ message: payload.message })
      },
      onEvent
    )
};

export function getInterviewAgentClient() {
  const bridge = electronBridge();
  if (!bridge) return browserClient;
  return {
    hasToken: () => true,
    ...bridge
  };
}
