export function createInterviewerClient(apiJson) {
  return {
    listKits: ({ limit = 20, offset = 0 } = {}) => apiJson(`/interviewer-workspace/kits?limit=${limit}&offset=${offset}`),
    createKit: (payload) => apiJson("/interviewer-workspace/kits", json("POST", payload)),
    getKit: (kitId) => apiJson(`/interviewer-workspace/kits/${encodeURIComponent(kitId)}`),
    updateQuestions: (kitId, payload) => apiJson(
      `/interviewer-workspace/kits/${encodeURIComponent(kitId)}/questions`,
      json("PUT", payload)
    ),
    addEvidence: (kitId, payload) => apiJson(
      `/interviewer-workspace/kits/${encodeURIComponent(kitId)}/evidence`,
      json("POST", payload)
    )
  };
}

export function createTrainingClient(apiJson) {
  return {
    createDrill: (payload) => apiJson("/training/drills", json("POST", payload)),
    getDrill: (drillId) => apiJson(`/training/drills/${encodeURIComponent(drillId)}`),
    completeDrill: (drillId) => apiJson(`/training/drills/${encodeURIComponent(drillId)}/complete`, json("POST", {})),
    dueReviews: (limit = 20) => apiJson(`/training/spaced-review/due?limit=${limit}`),
    gradeReview: (itemId, quality) => apiJson(
      `/training/spaced-review/${encodeURIComponent(itemId)}/grade`,
      json("POST", { quality })
    )
  };
}

function json(method, payload) {
  return { method, body: JSON.stringify(payload || {}) };
}
