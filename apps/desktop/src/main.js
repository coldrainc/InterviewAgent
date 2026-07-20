const { app, BrowserWindow, dialog, ipcMain, nativeImage } = require("electron");
const fs = require("fs/promises");
const path = require("path");

const API_BASE_URL = process.env.INTERVIEW_AGENT_API_URL || "http://127.0.0.1:8020";
let apiToken = process.env.INTERVIEW_AGENT_API_TOKEN || process.env.INTERVIEW_API_TOKEN || "";
const RENDERER_DEV_URL = process.env.INTERVIEW_RENDERER_DEV_URL;
const API_RETRY_COUNT = 8;
const API_RETRY_DELAY_MS = 350;
const APP_ICON_PATH = path.join(__dirname, "assets", "app-icon.png");
const streamControllers = new Map();

function createWindow() {
  const win = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 920,
    minHeight: 640,
    title: "Interview Agent",
    backgroundColor: "#eef4f1",
    icon: APP_ICON_PATH,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  if (RENDERER_DEV_URL) {
    win.loadURL(RENDERER_DEV_URL);
  } else {
    win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
}

app.whenReady().then(() => {
  const appIcon = nativeImage.createFromPath(APP_ICON_PATH);
  if (process.platform === "darwin" && !appIcon.isEmpty()) {
    app.dock.setIcon(appIcon);
  }
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

ipcMain.handle("api:health", async () => {
  return requestJson("/health");
});

ipcMain.handle("metadata:industries", async (_event, targetRole) => {
  const query = targetRole ? `?target_role=${encodeURIComponent(targetRole)}` : "";
  return requestJson(`/metadata/industries${query}`);
});

ipcMain.handle("metadata:models", async () => {
  return requestJson("/metadata/models");
});

ipcMain.handle("civil-service:learning-plan", async () => {
  return requestJson("/civil-service/learning-plan");
});

ipcMain.handle("practice:learning-plan", async () => {
  return requestJson("/practice/learning-plan");
});

ipcMain.handle("practice:questions", async (_event, filters = {}) => {
  const params = new URLSearchParams();
  if (filters.category) params.set("category", filters.category);
  if (filters.year) params.set("year", filters.year);
  if (filters.subject) params.set("subject", filters.subject);
  if (filters.questionType) params.set("question_type", filters.questionType);
  params.set("limit", filters.limit || 30);
  params.set("offset", filters.offset || 0);
  return requestJson(`/practice/questions?${params.toString()}`);
});

ipcMain.handle("practice:seed", async () => {
  return requestJson("/practice/questions/seed", { method: "POST" });
});

ipcMain.handle("civil-service:questions", async (_event, filters = {}) => {
  const params = new URLSearchParams();
  if (filters.year) params.set("year", filters.year);
  if (filters.subject) params.set("subject", filters.subject);
  if (filters.questionType) params.set("question_type", filters.questionType);
  params.set("limit", filters.limit || 30);
  params.set("offset", filters.offset || 0);
  return requestJson(`/civil-service/questions?${params.toString()}`);
});

ipcMain.handle("civil-service:seed", async () => {
  return requestJson("/civil-service/questions/seed", { method: "POST" });
});

ipcMain.handle("civil-service:import-file", async () => {
  const result = await dialog.showOpenDialog({
    title: "选择题库文件",
    properties: ["openFile"],
    filters: [
      { name: "题库文件", extensions: ["json", "csv"] },
      { name: "JSON", extensions: ["json"] },
      { name: "CSV", extensions: ["csv"] }
    ]
  });
  if (result.canceled || !result.filePaths.length) {
    return { canceled: true };
  }

  const filePath = result.filePaths[0];
  const text = await fs.readFile(filePath, "utf-8");
  const questions = parseQuestionBankFile(path.basename(filePath), text);
  const stored = await requestJson("/practice/questions/import", {
    method: "POST",
    body: JSON.stringify({ questions })
  });
  return { canceled: false, path: filePath, ...stored };
});

ipcMain.handle("practice:import-file", async () => {
  const result = await dialog.showOpenDialog({
    title: "选择题库文件",
    properties: ["openFile"],
    filters: [
      { name: "题库文件", extensions: ["json", "csv"] },
      { name: "JSON", extensions: ["json"] },
      { name: "CSV", extensions: ["csv"] }
    ]
  });
  if (result.canceled || !result.filePaths.length) {
    return { canceled: true };
  }

  const filePath = result.filePaths[0];
  const text = await fs.readFile(filePath, "utf-8");
  const questions = parseQuestionBankFile(path.basename(filePath), text);
  const stored = await requestJson("/practice/questions/import", {
    method: "POST",
    body: JSON.stringify({ questions })
  });
  return { canceled: false, path: filePath, ...stored };
});

ipcMain.handle("auth:register", async (_event, payload) => {
  const response = await requestJson("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload || {})
  });
  apiToken = response.access_token || apiToken;
  return response;
});

ipcMain.handle("auth:login", async (_event, payload) => {
  const response = await requestJson("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload || {})
  });
  apiToken = response.access_token || apiToken;
  return response;
});

ipcMain.handle("auth:dev-login", async (_event, payload) => {
  const response = await requestJson("/auth/dev-login", {
    method: "POST",
    body: JSON.stringify(payload || {})
  });
  apiToken = response.access_token || apiToken;
  return response;
});

ipcMain.handle("auth:logout", async () => {
  apiToken = "";
  return { ok: true };
});

ipcMain.handle("account:get", async () => {
  return requestJson("/account");
});

ipcMain.handle("settings:get", async () => {
  return requestJson("/settings");
});

ipcMain.handle("settings:update", async (_event, payload) => {
  return requestJson("/settings", {
    method: "PUT",
    body: JSON.stringify(payload || {})
  });
});

ipcMain.handle("account:recharge", async (_event, payload) => {
  return requestJson("/account/recharge", {
    method: "POST",
    body: JSON.stringify(payload || {})
  });
});

ipcMain.handle("payments:create-order", async (_event, payload) => {
  return requestJson("/payments/orders", {
    method: "POST",
    body: JSON.stringify(payload || {})
  });
});

ipcMain.handle("payments:get-order", async (_event, orderId) => {
  return requestJson(`/payments/orders/${encodeURIComponent(orderId)}`);
});

ipcMain.handle("resumes:list", async () => {
  return requestJson("/resumes");
});

ipcMain.handle("resumes:get", async (_event, resumeId) => {
  return requestJson(`/resumes/${resumeId}`);
});

ipcMain.handle("resumes:delete", async (_event, resumeId) => {
  return requestJson(`/resumes/${resumeId}`, { method: "DELETE" });
});

ipcMain.handle("sessions:list", async () => {
  return requestJson("/sessions");
});

ipcMain.handle("sessions:get", async (_event, sessionId) => {
  return requestJson(`/sessions/${sessionId}`);
});

ipcMain.handle("sessions:delete", async (_event, sessionId) => {
  return requestJson(`/sessions/${sessionId}`, { method: "DELETE" });
});

ipcMain.handle("sessions:rewind", async (_event, sessionId, payload) => {
  return requestJson(`/sessions/${sessionId}/rewind`, {
    method: "POST",
    body: JSON.stringify(payload || {})
  });
});

ipcMain.handle("api:create-session", async (_event, payload) => {
  return requestJson("/sessions", {
    method: "POST",
    body: JSON.stringify(payload || {})
  });
});

ipcMain.handle("resume:import", async () => {
  const result = await dialog.showOpenDialog({
    title: "选择简历文件",
    properties: ["openFile"],
    filters: [
      { name: "简历文件", extensions: ["pdf", "md", "markdown"] },
      { name: "PDF", extensions: ["pdf"] },
      { name: "Markdown", extensions: ["md", "markdown"] }
    ]
  });
  if (result.canceled || !result.filePaths.length) {
    return { canceled: true };
  }

  const filePath = result.filePaths[0];
  const buffer = await fs.readFile(filePath);
  const stored = await requestJson("/resumes", {
    method: "POST",
    body: JSON.stringify({
      filename: path.basename(filePath),
      content_base64: buffer.toString("base64"),
      source_path: filePath
    })
  });
  return { canceled: false, path: filePath, ...stored };
});

ipcMain.handle("document:parse", async () => {
  const result = await dialog.showOpenDialog({
    title: "选择面试官要求文件",
    properties: ["openFile"],
    filters: [
      { name: "要求文件", extensions: ["pdf", "md", "markdown", "txt"] },
      { name: "PDF", extensions: ["pdf"] },
      { name: "Markdown / Text", extensions: ["md", "markdown", "txt"] }
    ]
  });
  if (result.canceled || !result.filePaths.length) {
    return { canceled: true };
  }

  const filePath = result.filePaths[0];
  const buffer = await fs.readFile(filePath);
  const parsed = await requestJson("/resume/parse", {
    method: "POST",
    body: JSON.stringify({
      filename: path.basename(filePath),
      content_base64: buffer.toString("base64")
    })
  });
  return { canceled: false, path: filePath, ...parsed };
});

ipcMain.handle("api:send-message", async (_event, payload) => {
  return requestJson(`/sessions/${payload.sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ message: payload.message })
  });
});

ipcMain.handle("api:stream-message", async (event, payload) => {
  const streamId = payload?.streamId;
  if (!streamId) {
    throw new Error("stream id missing");
  }
  return requestEventStream(
    `/sessions/${payload.sessionId}/stream`,
    {
      method: "POST",
      body: JSON.stringify({ message: payload.message })
    },
    (streamEvent) => {
      event.sender.send("api:stream-event", streamId, streamEvent);
    },
    streamId
  );
});

ipcMain.handle("api:stream-cancel", async (_event, streamId) => {
  const controller = streamControllers.get(streamId);
  if (controller) {
    controller.abort();
  }
  return { ok: true };
});

function parseQuestionBankFile(filename, text) {
  const cleanedText = String(text || "").trim();
  if (!cleanedText) {
    throw new Error("题库文件为空。");
  }
  const extension = filename.split(".").pop()?.toLowerCase();
  const questions = extension === "csv"
    ? parseQuestionBankCsv(cleanedText)
    : parseQuestionBankJson(cleanedText);
  if (!questions.length) {
    throw new Error("没有识别到可导入的题目。");
  }
  if (questions.length > 500) {
    throw new Error("单次最多导入 500 道题，请拆分文件后再上传。");
  }
  return questions.map(normalizeQuestionRow);
}

function parseQuestionBankJson(text) {
  let payload;
  try {
    payload = JSON.parse(text);
  } catch (_error) {
    throw new Error("JSON 题库格式不正确。");
  }
  const rows = Array.isArray(payload) ? payload : payload?.questions;
  if (!Array.isArray(rows)) {
    throw new Error("JSON 题库需要是数组，或包含 questions 数组。");
  }
  return rows;
}

function parseQuestionBankCsv(text) {
  const rows = parseCsvRows(text);
  if (rows.length < 2) return [];
  const headers = rows[0].map((header) => normalizeHeader(header));
  return rows.slice(1).map((row) => {
    const item = {};
    headers.forEach((header, index) => {
      if (header) item[header] = row[index] || "";
    });
    return item;
  });
}

function parseCsvRows(text) {
  const rows = [];
  let field = "";
  let row = [];
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (quoted) {
      if (char === "\"" && next === "\"") {
        field += "\"";
        index += 1;
      } else if (char === "\"") {
        quoted = false;
      } else {
        field += char;
      }
      continue;
    }
    if (char === "\"") {
      quoted = true;
    } else if (char === ",") {
      row.push(field.trim());
      field = "";
    } else if (char === "\n") {
      row.push(field.trim());
      rows.push(row);
      row = [];
      field = "";
    } else if (char !== "\r") {
      field += char;
    }
  }
  row.push(field.trim());
  if (row.some(Boolean)) rows.push(row);
  return rows.filter((current) => current.some(Boolean));
}

function normalizeHeader(value) {
  const header = String(value || "").trim();
  const aliases = {
    year: "exam_year",
    examYear: "exam_year",
    question: "prompt",
    type: "question_type",
    practiceCategory: "practice_category",
    practice_category: "practice_category",
    category: "practice_category",
    sourceUrl: "source_url",
    sourceURL: "source_url"
  };
  return aliases[header] || header;
}

function normalizeQuestionRow(row) {
  const normalized = { ...row };
  normalized.source = normalized.source || "user-upload";
  normalized.practice_category = normalizeCategory(normalized.practice_category || normalized.category || inferCategory(normalized));
  normalized.exam_year = Number(normalized.exam_year || normalized.year || 0);
  normalized.exam_name = String(normalized.exam_name || "自定义题库").trim();
  normalized.subject = String(normalized.subject || "general").trim();
  normalized.question_type = String(normalized.question_type || normalized.type || "综合训练").trim();
  normalized.prompt = String(normalized.prompt || normalized.question || "").trim();
  normalized.choices = normalizeList(normalized.choices);
  normalized.tags = normalizeList(normalized.tags);
  normalized.answer = String(normalized.answer || "").trim();
  normalized.explanation = String(normalized.explanation || "").trim();
  normalized.difficulty = String(normalized.difficulty || "medium").trim();
  if (!normalized.prompt) {
    throw new Error("题库中存在空题目，请补充 prompt/question 字段。");
  }
  if (!normalized.exam_year) {
    throw new Error("题库中存在无效年份，请补充 exam_year/year 字段。");
  }
  return normalized;
}

function normalizeCategory(value) {
  const cleaned = String(value || "internet").trim().toLowerCase();
  const aliases = {
    "考公": "civil_service",
    "公考": "civil_service",
    "公务员": "civil_service",
    "civil-service": "civil_service",
    "civil service": "civil_service",
    "互联网": "internet",
    "技术面试": "internet",
    "ai": "ai_engineering",
    "ai工程": "ai_engineering",
    "ai 工程": "ai_engineering",
    "面试": "interview"
  };
  return aliases[cleaned] || cleaned || "internet";
}

function inferCategory(row) {
  const subject = String(row.subject || "").trim().toLowerCase();
  const examName = String(row.exam_name || "").trim().toLowerCase();
  if (["xingce", "shenlun"].includes(subject) || /考公|国考|省考|申论|行测/.test(examName)) {
    return "civil_service";
  }
  if (/ai|rag|agent|llm/.test(examName)) {
    return "ai_engineering";
  }
  return "internet";
}

function normalizeList(value) {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  return String(value || "")
    .split("|")
    .map((item) => item.trim())
    .filter(Boolean);
}

async function requestJson(route, options = {}, attempt = 0) {
  try {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (apiToken) {
      headers.Authorization = `Bearer ${apiToken}`;
    }
    const response = await fetch(`${API_BASE_URL}${route}`, {
      ...options,
      headers
    });
    const text = await response.text();
    const data = text ? JSON.parse(text) : {};
    if (
      data
      && typeof data === "object"
      && Object.prototype.hasOwnProperty.call(data, "code")
      && Object.prototype.hasOwnProperty.call(data, "data")
    ) {
      if (data.code === 0) {
        return data.data;
      }
      throw new Error(data.message || data.error || `HTTP ${response.status}`);
    }
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`);
    }
    return data;
  } catch (error) {
    if (isRetryableApiError(error) && attempt < API_RETRY_COUNT) {
      await delay(API_RETRY_DELAY_MS * (attempt + 1));
      return requestJson(route, options, attempt + 1);
    }
    throw new Error(formatApiError(error));
  }
}

async function requestEventStream(route, options = {}, onEvent, streamId) {
  const controller = new AbortController();
  streamControllers.set(streamId, controller);
  try {
    const headers = { "Content-Type": "application/json", Accept: "text/event-stream", ...(options.headers || {}) };
    if (apiToken) {
      headers.Authorization = `Bearer ${apiToken}`;
    }
    const response = await fetch(`${API_BASE_URL}${route}`, {
      ...options,
      headers,
      signal: controller.signal
    });
    if (!response.ok) {
      const text = await response.text();
      const data = text ? JSON.parse(text) : {};
      throw new Error(data.detail || data.message || `HTTP ${response.status}`);
    }
    if (!response.body) {
      throw new Error("当前运行环境不支持流式响应。");
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
        const streamEvent = parseSseChunk(chunk);
        if (!streamEvent) continue;
        onEvent?.(streamEvent);
        if (streamEvent.event === "message.error") {
          throw new Error(streamEvent.data?.message || "流式生成失败。");
        }
        if (streamEvent.event === "message.done") {
          finalPayload = streamEvent.data;
        }
      }
    }
    if (buffer.trim()) {
      const streamEvent = parseSseChunk(buffer);
      if (streamEvent) {
        onEvent?.(streamEvent);
        if (streamEvent.event === "message.error") {
          throw new Error(streamEvent.data?.message || "流式生成失败。");
        }
        if (streamEvent.event === "message.done") {
          finalPayload = streamEvent.data;
        }
      }
    }
    return finalPayload || {};
  } catch (error) {
    if (error?.name === "AbortError") {
      const stoppedError = new Error("请求已停止。");
      stoppedError.name = "AbortError";
      throw stoppedError;
    }
    throw new Error(formatApiError(error));
  } finally {
    streamControllers.delete(streamId);
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

function isRetryableApiError(error) {
  const code = error?.cause?.code || error?.code;
  return (
    code === "ECONNREFUSED" ||
    code === "ECONNRESET" ||
    code === "ETIMEDOUT" ||
    error?.message === "fetch failed"
  );
}

function formatApiError(error) {
  if (isRetryableApiError(error)) {
    return "本地 API 暂时不可用，请确认 API 已启动后点击刷新。";
  }
  return error?.message || "请求本地 API 失败。";
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
