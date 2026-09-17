export function createPrivacyClient(apiJson) {
  return {
    exportData: () => apiJson("/privacy/export"),
    getDeletion: () => apiJson("/privacy/deletion"),
    scheduleDeletion: (reason = "") => apiJson("/privacy/deletion", {
      method: "POST",
      body: JSON.stringify({ confirmation: "DELETE", reason })
    }),
    cancelDeletion: () => apiJson("/privacy/deletion", { method: "DELETE" })
  };
}
