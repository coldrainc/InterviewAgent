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
  apiRequest: (route, options) => ipcRenderer.invoke("api:request", route, options),
  listIndustries: (targetRole) => ipcRenderer.invoke("metadata:industries", targetRole),
  listModels: () => ipcRenderer.invoke("metadata:models"),
  getCivilServiceLearningPlan: () => ipcRenderer.invoke("civil-service:learning-plan"),
  listCivilServiceQuestions: (filters) => ipcRenderer.invoke("civil-service:questions", filters),
  seedCivilServiceQuestions: () => ipcRenderer.invoke("civil-service:seed"),
  importCivilServiceQuestionBank: () => ipcRenderer.invoke("civil-service:import-file"),
  getPracticeLearningPlan: () => ipcRenderer.invoke("practice:learning-plan"),
  listPracticeCategories: () => ipcRenderer.invoke("practice:categories"),
  listPracticeQuestions: (filters) => ipcRenderer.invoke("practice:questions", filters),
  seedPracticeQuestions: () => ipcRenderer.invoke("practice:seed"),
  importPracticeQuestionBank: () => ipcRenderer.invoke("practice:import-file"),
  reviewSite: {
    listPlans: (params) => ipcRenderer.invoke("review-site:plans", params),
    createPlan: (payload) => ipcRenderer.invoke("review-site:create-plan", payload),
    getPlan: (planId) => ipcRenderer.invoke("review-site:plan", planId),
    patchPlan: (planId, payload) => ipcRenderer.invoke("review-site:patch-plan", planId, payload),
    archivePlan: (planId) => ipcRenderer.invoke("review-site:archive-plan", planId),
    patchProgress: (taskId, payload) => ipcRenderer.invoke("review-site:patch-progress", taskId, payload),
    listIntroScripts: (planId) => ipcRenderer.invoke("review-site:intro-scripts", planId),
    listStarCards: (planId) => ipcRenderer.invoke("review-site:star-cards", planId),
    listA4Memory: (planId) => ipcRenderer.invoke("review-site:a4-memory", planId),
    listPracticeQuestions: (filters) => ipcRenderer.invoke("review-site:practice-questions", filters),
    markQuestion: (questionId, payload) => ipcRenderer.invoke("review-site:mark-question", questionId, payload),
    listWrongBook: (params) => ipcRenderer.invoke("review-site:wrong-book", params),
    generatePlan: (payload) => ipcRenderer.invoke("review-site:generate-plan", payload)
  },
  openExternal: (url) => ipcRenderer.invoke("shell:open-external", url),
  notifyTest: () => ipcRenderer.invoke("notify:test"),
  notifySchedule: (payload) => ipcRenderer.invoke("notify:schedule", payload),
  notifyCancel: () => ipcRenderer.invoke("notify:cancel"),
  listJobs: (params) => ipcRenderer.invoke("jobs:list", params),
  getJob: (jobId) => ipcRenderer.invoke("jobs:get", jobId),
  createJob: (payload) => ipcRenderer.invoke("jobs:create", payload),
  cancelJob: (jobId) => ipcRenderer.invoke("jobs:cancel", jobId),
  runWorkflow: (payload) => ipcRenderer.invoke("workflows:run", payload),
  createEvalRun: (payload) => ipcRenderer.invoke("eval-runs:create", payload),
  listEvalRuns: (params) => ipcRenderer.invoke("eval-runs:list", params),
  listAgentTraces: (params) => ipcRenderer.invoke("ops:traces", params),
  getAgentTrace: (traceId) => ipcRenderer.invoke("ops:trace", traceId),
  getOpsMetrics: () => ipcRenderer.invoke("ops:metrics"),
  register: (payload) => ipcRenderer.invoke("auth:register", payload),
  login: (payload) => ipcRenderer.invoke("auth:login", payload),
  devLogin: (payload) => ipcRenderer.invoke("auth:dev-login", payload),
  logout: () => ipcRenderer.invoke("auth:logout"),
  getAccount: () => ipcRenderer.invoke("account:get"),
  getSettings: () => ipcRenderer.invoke("settings:get"),
  updateSettings: (payload) => ipcRenderer.invoke("settings:update", payload),
  listSecurityEvents: () => ipcRenderer.invoke("admin:security-events"),
  listRoles: () => ipcRenderer.invoke("admin:roles"),
  grantRole: (payload) => ipcRenderer.invoke("admin:grant-role", payload),
  revokeRole: (payload) => ipcRenderer.invoke("admin:revoke-role", payload),
  createReviewSiteTestData: () => ipcRenderer.invoke("admin:create-review-site-test-data"),
  recharge: (payload) => ipcRenderer.invoke("account:recharge", payload),
  createPaymentOrder: (payload) => ipcRenderer.invoke("payments:create-order", payload),
  getPaymentOrder: (orderId) => ipcRenderer.invoke("payments:get-order", orderId),
  listResumes: (params) => ipcRenderer.invoke("resumes:list", params),
  getResume: (resumeId) => ipcRenderer.invoke("resumes:get", resumeId),
  deleteResume: (resumeId) => ipcRenderer.invoke("resumes:delete", resumeId),
  listSessions: (params) => ipcRenderer.invoke("sessions:list", params),
  getSession: (sessionId) => ipcRenderer.invoke("sessions:get", sessionId),
  deleteSession: (sessionId) => ipcRenderer.invoke("sessions:delete", sessionId),
  rewindSession: (sessionId, payload) => ipcRenderer.invoke("sessions:rewind", sessionId, payload),
  importResume: () => ipcRenderer.invoke("resume:import"),
  parseDocument: () => ipcRenderer.invoke("document:parse"),
  createSession: (payload) => ipcRenderer.invoke("api:create-session", payload),
  sendMessage: (payload) => ipcRenderer.invoke("api:send-message", payload),
  streamMessage
});
