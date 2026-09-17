import { useCallback, useEffect, useRef, useState } from "react";
import { normalizeDesktopError } from "../../utils/interview";
import { mergeUniqueById } from "../../hooks/useInfiniteScroll";

const INITIAL = {
  status: "idle",
  dashboard: {},
  users: [],
  models: [],
  plans: [],
  orders: [],
  audit: [],
  error: "",
  message: "",
  pages: { users: true, orders: true, audit: true }
};

export function useAdminConsole(client, isAdmin) {
  const [state, setState] = useState(INITIAL);
  const stateRef = useRef(INITIAL);
  const loadingKindsRef = useRef(new Set());

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const load = useCallback(async () => {
    if (!isAdmin || !client) return;
    setState((current) => ({ ...current, status: "loading", error: "", message: "" }));
    try {
      const [dashboard, users, models, plans, orders, audit] = await Promise.all([
        client.getDashboard(), client.listUsers(), client.listModels(), client.listPlans(),
        client.listOrders(), client.listAudit()
      ]);
      setState({
        status: "ready", dashboard, users, models, plans, orders, audit, error: "", message: "",
        pages: { users: users.length === 20, orders: orders.length === 20, audit: audit.length === 20 }
      });
    } catch (error) {
      setState((current) => ({ ...current, status: "error", error: normalizeDesktopError(error.message) }));
    }
  }, [client, isAdmin]);

  async function mutate(action, successMessage) {
    setState((current) => ({ ...current, status: "saving", error: "", message: "" }));
    try {
      await action();
      await load();
      setState((current) => ({ ...current, message: successMessage }));
      return true;
    } catch (error) {
      setState((current) => ({ ...current, status: "error", error: normalizeDesktopError(error.message) }));
      return false;
    }
  }

  async function loadMore(kind) {
    const snapshot = stateRef.current;
    if (!snapshot.pages?.[kind] || loadingKindsRef.current.has(kind)) return;
    loadingKindsRef.current.add(kind);
    setState((current) => ({ ...current, status: "loading-more", error: "" }));
    try {
      const currentItems = snapshot[kind] || [];
      const loader = kind === "users" ? client.listUsers : kind === "orders" ? client.listOrders : client.listAudit;
      const incoming = await loader({ limit: 20, offset: currentItems.length });
      setState((current) => ({
        ...current,
        status: "ready",
        [kind]: mergeUniqueById(current[kind], incoming),
        pages: { ...current.pages, [kind]: incoming.length === 20 }
      }));
    } catch (error) {
      setState((current) => ({ ...current, status: "error", error: normalizeDesktopError(error.message) }));
    } finally {
      loadingKindsRef.current.delete(kind);
    }
  }

  return {
    state,
    load,
    loadMore,
    updateUserStatus: (userId, status, reason) => mutate(
      () => client.updateUserStatus(userId, { status, reason }), "用户状态已更新。"
    ),
    adjustBalance: (userId, amount, reason) => mutate(
      () => client.adjustBalance(userId, { amount_credits: amount, reason }), "用户余额已调整。"
    ),
    grantRole: (userId, role, reason) => mutate(
      () => client.grantRole(userId, { role, reason }), "用户角色已更新。"
    ),
    revokeRole: (userId, role, reason) => mutate(
      () => client.revokeRole(userId, role, reason), "用户角色已移除。"
    ),
    updateModel: (modelId, payload) => mutate(
      () => client.updateModel(modelId, payload), "模型策略已生效。"
    ),
    updatePlan: (code, payload) => mutate(
      () => client.updatePlan(code, payload), "套餐配置已保存。"
    )
  };
}
