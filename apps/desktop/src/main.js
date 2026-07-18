const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const fs = require("fs/promises");
const path = require("path");

const API_BASE_URL = process.env.INTERVIEW_AGENT_API_URL || "http://127.0.0.1:8020";
let apiToken = process.env.INTERVIEW_AGENT_API_TOKEN || process.env.INTERVIEW_API_TOKEN || "";
const RENDERER_DEV_URL = process.env.INTERVIEW_RENDERER_DEV_URL;
const API_RETRY_COUNT = 8;
const API_RETRY_DELAY_MS = 350;

function createWindow() {
  const win = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 920,
    minHeight: 640,
    title: "Interview Agent",
    backgroundColor: "#f6f7fb",
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

ipcMain.handle("api:send-message", async (_event, payload) => {
  return requestJson(`/sessions/${payload.sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ message: payload.message })
  });
});

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
