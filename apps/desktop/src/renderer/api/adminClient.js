export function createAdminClient(apiJson) {
  return {
    getDashboard: () => apiJson("/admin/dashboard"),
    listUsers: ({ query = "", status = "", limit = 20, offset = 0 } = {}) => {
      const params = new URLSearchParams();
      if (query) params.set("query", query);
      if (status) params.set("status", status);
      params.set("limit", limit);
      params.set("offset", offset);
      return apiJson(`/admin/users${params.size ? `?${params}` : ""}`);
    },
    updateUserStatus: (userId, payload) => apiJson(`/admin/users/${encodeURIComponent(userId)}/status`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
    adjustBalance: (userId, payload) => apiJson(`/admin/users/${encodeURIComponent(userId)}/balance-adjustments`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
    grantRole: (userId, payload) => apiJson(`/admin/users/${encodeURIComponent(userId)}/roles`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
    revokeRole: (userId, role, reason) => apiJson(
      `/admin/users/${encodeURIComponent(userId)}/roles/${encodeURIComponent(role)}?reason=${encodeURIComponent(reason)}`,
      { method: "DELETE" }
    ),
    listModels: () => apiJson("/admin/models"),
    updateModel: (modelId, payload) => apiJson(`/admin/models/${encodeURIComponent(modelId)}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
    listPlans: () => apiJson("/admin/plans"),
    updatePlan: (code, payload) => apiJson(`/admin/plans/${encodeURIComponent(code)}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
    listOrders: ({ limit = 20, offset = 0 } = {}) => apiJson(`/admin/orders?limit=${limit}&offset=${offset}`),
    listAudit: ({ limit = 20, offset = 0 } = {}) => apiJson(`/admin/audit?limit=${limit}&offset=${offset}`)
  };
}
