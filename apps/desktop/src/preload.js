const { contextBridge, ipcRenderer } = require("electron");

function streamMessage(payload, onEvent) {
  const streamId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const listener = (_event, incomingStreamId, streamEvent) => {
    if (incomingStreamId === streamId) {
      onEvent?.(streamEvent);
    }
  };
  const abort = () => {
    ipcRenderer.invoke("api:stream-cancel", streamId).catch(() => {});
  };
  ipcRenderer.on("api:stream-event", listener);
  payload?.signal?.addEventListener?.("abort", abort, { once: true });
  return ipcRenderer.invoke("api:stream-message", {
    sessionId: payload?.sessionId,
    message: payload?.message,
    streamId
  }).finally(() => {
    ipcRenderer.removeListener("api:stream-event", listener);
    payload?.signal?.removeEventListener?.("abort", abort);
  });
}

contextBridge.exposeInMainWorld("interviewAgent", {
  health: () => ipcRenderer.invoke("api:health"),
  listIndustries: (targetRole) => ipcRenderer.invoke("metadata:industries", targetRole),
  listModels: () => ipcRenderer.invoke("metadata:models"),
  getCivilServiceLearningPlan: () => ipcRenderer.invoke("civil-service:learning-plan"),
  listCivilServiceQuestions: (filters) => ipcRenderer.invoke("civil-service:questions", filters),
  seedCivilServiceQuestions: () => ipcRenderer.invoke("civil-service:seed"),
  importCivilServiceQuestionBank: () => ipcRenderer.invoke("civil-service:import-file"),
  getPracticeLearningPlan: () => ipcRenderer.invoke("practice:learning-plan"),
  listPracticeQuestions: (filters) => ipcRenderer.invoke("practice:questions", filters),
  seedPracticeQuestions: () => ipcRenderer.invoke("practice:seed"),
  importPracticeQuestionBank: () => ipcRenderer.invoke("practice:import-file"),
  register: (payload) => ipcRenderer.invoke("auth:register", payload),
  login: (payload) => ipcRenderer.invoke("auth:login", payload),
  devLogin: (payload) => ipcRenderer.invoke("auth:dev-login", payload),
  logout: () => ipcRenderer.invoke("auth:logout"),
  getAccount: () => ipcRenderer.invoke("account:get"),
  getSettings: () => ipcRenderer.invoke("settings:get"),
  updateSettings: (payload) => ipcRenderer.invoke("settings:update", payload),
  recharge: (payload) => ipcRenderer.invoke("account:recharge", payload),
  createPaymentOrder: (payload) => ipcRenderer.invoke("payments:create-order", payload),
  getPaymentOrder: (orderId) => ipcRenderer.invoke("payments:get-order", orderId),
  listResumes: () => ipcRenderer.invoke("resumes:list"),
  getResume: (resumeId) => ipcRenderer.invoke("resumes:get", resumeId),
  deleteResume: (resumeId) => ipcRenderer.invoke("resumes:delete", resumeId),
  listSessions: () => ipcRenderer.invoke("sessions:list"),
  getSession: (sessionId) => ipcRenderer.invoke("sessions:get", sessionId),
  deleteSession: (sessionId) => ipcRenderer.invoke("sessions:delete", sessionId),
  rewindSession: (sessionId, payload) => ipcRenderer.invoke("sessions:rewind", sessionId, payload),
  importResume: () => ipcRenderer.invoke("resume:import"),
  parseDocument: () => ipcRenderer.invoke("document:parse"),
  createSession: (payload) => ipcRenderer.invoke("api:create-session", payload),
  sendMessage: (payload) => ipcRenderer.invoke("api:send-message", payload),
  streamMessage
});
