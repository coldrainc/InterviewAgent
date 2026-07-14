const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("interviewAgent", {
  health: () => ipcRenderer.invoke("api:health"),
  listIndustries: (targetRole) => ipcRenderer.invoke("metadata:industries", targetRole),
  listModels: () => ipcRenderer.invoke("metadata:models"),
  register: (payload) => ipcRenderer.invoke("auth:register", payload),
  login: (payload) => ipcRenderer.invoke("auth:login", payload),
  devLogin: (payload) => ipcRenderer.invoke("auth:dev-login", payload),
  logout: () => ipcRenderer.invoke("auth:logout"),
  getAccount: () => ipcRenderer.invoke("account:get"),
  recharge: (payload) => ipcRenderer.invoke("account:recharge", payload),
  listResumes: () => ipcRenderer.invoke("resumes:list"),
  getResume: (resumeId) => ipcRenderer.invoke("resumes:get", resumeId),
  deleteResume: (resumeId) => ipcRenderer.invoke("resumes:delete", resumeId),
  listSessions: () => ipcRenderer.invoke("sessions:list"),
  getSession: (sessionId) => ipcRenderer.invoke("sessions:get", sessionId),
  deleteSession: (sessionId) => ipcRenderer.invoke("sessions:delete", sessionId),
  importResume: () => ipcRenderer.invoke("resume:import"),
  createSession: (payload) => ipcRenderer.invoke("api:create-session", payload),
  sendMessage: (payload) => ipcRenderer.invoke("api:send-message", payload)
});
