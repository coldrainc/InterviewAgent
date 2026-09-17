export function createStudyClient(apiJson) {
  return {
    dashboard: () => apiJson("/study/dashboard"),
    achievements: () => apiJson("/study/achievements"),
    listReports: (limit = 20, offset = 0) => apiJson(`/interview-reports?limit=${limit}&offset=${offset}`),
    getReport: (sessionId) => apiJson(`/interview-reports/${encodeURIComponent(sessionId)}`),
    addReportTasks: (planId, sessionId) => apiJson(
      `/review-site/plans/${encodeURIComponent(planId)}/report-tasks`,
      { method: "POST", body: JSON.stringify({ session_id: sessionId }) }
    )
  };
}

export function createLearningClient({ apiJson, requestId }) {
  return {
    today: () => apiJson("/learning/today"),
    sync(cursor = "", limit = 100) {
      const search = new URLSearchParams({ limit: String(limit) });
      if (cursor) search.set("cursor", cursor);
      return apiJson(`/learning/sync?${search.toString()}`);
    },
    listGoals: () => apiJson("/learning/goals"),
    saveGoal: (payload) => apiJson("/learning/goals/active", json("PUT", payload)),
    abilitySnapshot: (refresh = false) => apiJson(`/learning/ability-snapshot${refresh ? "?refresh=true" : ""}`),
    proposeRevision: (planId) => apiJson(`/learning/plans/${encodeURIComponent(planId)}/revisions/propose`, json("POST", {})),
    listRevisions: (planId) => apiJson(`/learning/plans/${encodeURIComponent(planId)}/revisions`),
    decideRevision: (revisionId, action) => apiJson(
      `/learning/revisions/${encodeURIComponent(revisionId)}/decision`,
      json("POST", { action })
    ),
    getTask: (taskId) => apiJson(`/learning/tasks/${encodeURIComponent(taskId)}`),
    command: (taskId, payload, idempotencyKey = requestId()) => apiJson(
      `/learning/tasks/${encodeURIComponent(taskId)}/commands`,
      { ...json("POST", payload), headers: { "Idempotency-Key": idempotencyKey } }
    )
  };
}

function json(method, payload) {
  return { method, body: JSON.stringify(payload || {}) };
}
