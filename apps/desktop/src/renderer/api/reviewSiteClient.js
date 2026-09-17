const EMPTY_PLAN = {
  plan: {},
  phases: [],
  days: [],
  progresses: [],
  intro_scripts: [],
  star_cards: [],
  a4_memory: []
};

export function createReviewSiteClient({ requestJson, apiJson, longRequestTimeoutMs }) {
  return {
    async listPlans({ limit = 20, offset = 0 } = {}) {
      try {
        const data = await requestJson(`/review-site/plans?limit=${limit}&offset=${offset}`);
        return Array.isArray(data) ? data : [];
      } catch (_error) {
        return [];
      }
    },
    async createPlan(payload) {
      try {
        return await requestJson("/review-site/plans", {
          method: "POST",
          body: JSON.stringify(payload || {})
        }) || {};
      } catch (_error) {
        return {};
      }
    },
    async getPlan(planId) {
      try {
        return await requestJson(`/review-site/plans/${encodeURIComponent(planId)}`) || EMPTY_PLAN;
      } catch (_error) {
        return EMPTY_PLAN;
      }
    },
    async patchPlan(planId, payload) {
      try {
        return await requestJson(`/review-site/plans/${encodeURIComponent(planId)}`, {
          method: "PATCH",
          body: JSON.stringify(payload || {})
        }) || {};
      } catch (_error) {
        return {};
      }
    },
    async archivePlan(planId) {
      try {
        return await requestJson(`/review-site/plans/${encodeURIComponent(planId)}/archive`, { method: "POST" }) || {};
      } catch (_error) {
        return {};
      }
    },
    async patchProgress(taskId, payload) {
      try {
        return await requestJson(`/review-site/progress/task/${encodeURIComponent(taskId)}`, {
          method: "PATCH",
          body: JSON.stringify(payload || {})
        }) || {};
      } catch (_error) {
        return null;
      }
    },
    async listIntroScripts(planId) {
      return listOrEmpty(requestJson, `/review-site/plans/${encodeURIComponent(planId)}/intro-scripts`);
    },
    async listStarCards(planId) {
      return listOrEmpty(requestJson, `/review-site/plans/${encodeURIComponent(planId)}/star-cards`);
    },
    async listA4Memory(planId) {
      return listOrEmpty(requestJson, `/review-site/plans/${encodeURIComponent(planId)}/a4-memory`);
    },
    async listPracticeQuestions(filters = {}) {
      try {
        const params = new URLSearchParams();
        for (const key of ["category", "subject", "question_type", "difficulty", "keyword"]) {
          if (filters[key]) params.set(key, filters[key]);
        }
        params.set("limit", filters.limit || 30);
        params.set("offset", filters.offset || 0);
        return await requestJson(`/review-site/practice-questions?${params.toString()}`)
          || { items: [], total: 0, limit: 30, offset: 0 };
      } catch (_error) {
        return { items: [], total: 0, limit: 30, offset: 0 };
      }
    },
    async markQuestion(questionId, payload) {
      try {
        return await requestJson(`/review-site/practice-questions/${encodeURIComponent(questionId)}/mark`, {
          method: "POST",
          body: JSON.stringify(payload || {})
        }) || {};
      } catch (_error) {
        return null;
      }
    },
    async listWrongBook({ limit = 20, offset = 0 } = {}) {
      return listOrEmpty(requestJson, `/review-site/wrong-book?limit=${limit}&offset=${offset}`);
    },
    async generatePlan(payload) {
      try {
        return await apiJson("/review-site/planner/generate", {
          method: "POST",
          timeoutMs: longRequestTimeoutMs,
          body: JSON.stringify(payload || {})
        }) || {};
      } catch (_error) {
        return {};
      }
    },
    createDay: (planId, payload) => apiJson(`/review-site/plans/${encodeURIComponent(planId)}/days`, json("POST", payload)),
    updateDay: (dayId, payload) => apiJson(`/review-site/days/${encodeURIComponent(dayId)}`, json("PATCH", payload)),
    deleteDay: (dayId) => apiJson(`/review-site/days/${encodeURIComponent(dayId)}`, { method: "DELETE" }),
    createTask: (dayId, payload) => apiJson(`/review-site/days/${encodeURIComponent(dayId)}/tasks`, json("POST", payload)),
    updateTask: (taskId, payload) => apiJson(`/review-site/tasks/${encodeURIComponent(taskId)}`, json("PATCH", payload)),
    deleteTask: (taskId) => apiJson(`/review-site/tasks/${encodeURIComponent(taskId)}`, { method: "DELETE" }),
    upsertMaterial: (planId, kind, payload) => apiJson(
      `/review-site/plans/${encodeURIComponent(planId)}/materials/${encodeURIComponent(kind)}`,
      json("POST", payload)
    ),
    updateMaterial: (kind, itemId, payload) => apiJson(
      `/review-site/materials/${encodeURIComponent(kind)}/${encodeURIComponent(itemId)}`,
      json("PATCH", payload)
    ),
    deleteMaterial: (kind, itemId) => apiJson(
      `/review-site/materials/${encodeURIComponent(kind)}/${encodeURIComponent(itemId)}`,
      { method: "DELETE" }
    ),
    getToday: (planId) => apiJson(`/review-site/plans/${encodeURIComponent(planId)}/today`),
    checkin: (planId, payload) => apiJson(`/review-site/plans/${encodeURIComponent(planId)}/checkin`, json("POST", payload)),
    listCheckins(params = {}) {
      const search = new URLSearchParams();
      if (params.planId) search.set("plan_id", params.planId);
      if (params.dateFrom) search.set("date_from", params.dateFrom);
      if (params.dateTo) search.set("date_to", params.dateTo);
      return apiJson(`/review-site/checkins${search.size ? `?${search.toString()}` : ""}`);
    },
    submitAttempt: (questionId, payload) => apiJson(
      `/review-site/practice-questions/${encodeURIComponent(questionId)}/attempt`,
      { ...json("POST", payload), timeoutMs: longRequestTimeoutMs }
    ),
    listAttempts: (questionId, limit = 20) => apiJson(
      `/review-site/practice-questions/${encodeURIComponent(questionId)}/attempts?limit=${limit}`
    )
  };
}

function json(method, payload) {
  return { method, body: JSON.stringify(payload || {}) };
}

async function listOrEmpty(requestJson, route) {
  try {
    const data = await requestJson(route);
    return Array.isArray(data) ? data : [];
  } catch (_error) {
    return [];
  }
}
