const DEFAULT_API_BASE_URL = "https://api.aivago.cn";
const TOKEN_STORAGE_KEY = "interview-agent-api-token";
const REQUEST_TIMEOUT_MS = 15000;

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

async function requestJson(route, options = {}, attempt = 0) {
  const token = getStoredToken();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${apiBaseUrl()}${route}`, {
      ...options,
      headers,
      signal: controller.signal
    });
    const text = await response.text();
    const data = text ? JSON.parse(text) : {};
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }
    return data;
  } catch (error) {
    const method = (options.method || "GET").toUpperCase();
    if (attempt === 0 && method === "GET") {
      return requestJson(route, options, attempt + 1);
    }
    if (error.name === "AbortError") {
      throw new Error("请求超时，请检查网络或稍后重试。");
    }
    if (error instanceof TypeError) {
      throw new Error(`无法连接 API 服务：${apiBaseUrl()}。请检查网络、HTTPS 或浏览器安全策略。`);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
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
  recharge: (payload) =>
    requestJson("/account/recharge", {
      method: "POST",
      body: JSON.stringify(payload || {})
    }),
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
      body: JSON.stringify(payload || {})
    }),
  sendMessage: (payload) =>
    requestJson(`/sessions/${payload.sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ message: payload.message })
    })
};

export function getInterviewAgentClient() {
  const bridge = electronBridge();
  if (!bridge) return browserClient;
  return {
    hasToken: () => true,
    ...bridge
  };
}
