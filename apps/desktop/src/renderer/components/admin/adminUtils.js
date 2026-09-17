export function compactNumber(value) {
  return new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 1 }).format(Number(value || 0));
}

export function formatDate(value) {
  return value ? new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value)) : "-";
}

export function shortId(value) {
  const text = String(value || "-");
  return text.length > 22 ? `${text.slice(0, 10)}...${text.slice(-6)}` : text;
}

export function statusLabel(status) {
  return ({ active: "正常", suspended: "已停用", deleted: "已删除", paid: "已支付", pending: "待支付", created: "已创建", failed: "失败", cancelled: "已取消", ready: "可用" })[status] || status || "未知";
}

export function roleLabel(role) {
  return ({ admin: "管理员", support: "客服支持", server: "系统服务", user: "普通用户" })[role] || role;
}

export function actionLabel(action) {
  return ({
    user_status_updated: "更新用户状态", user_balance_adjusted: "调整用户余额",
    model_policy_updated: "更新模型策略", subscription_plan_updated: "更新付费套餐",
    user_role_granted: "授予用户角色", user_role_revoked: "移除用户角色"
  })[action] || action;
}

export function modelDraftChanged(model, draft) {
  return Boolean(model) && ["enabled", "is_default", "input_usd_per_1m", "output_usd_per_1m"].some((key) => String(model[key]) !== String(draft[key]));
}

export function planDraftChanged(plan, draft) {
  return Boolean(plan) && ["name", "enabled", "price_credits", "included_credits", "duration_days", "features"].some((key) => JSON.stringify(plan[key]) !== JSON.stringify(draft[key]));
}
