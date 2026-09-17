import { useState } from "react";
import { normalizeDesktopError } from "../utils/interview";

const INITIAL_SETTINGS = { status: "idle", default_interview_mode: "interviewer" };
const INITIAL_PAYMENT = { status: "idle", amount: "10", provider: "alipay" };
const INITIAL_ADMIN = {
  status: "idle",
  roles: [],
  events: [],
  userId: "",
  role: "support",
  error: "",
  testDataStatus: "idle",
  testDataMessage: ""
};
const INITIAL_AUTH = {
  mode: "login",
  email: "",
  password: "",
  displayName: "",
  status: "idle"
};

export function useAccountController({ api, setProfile, afterAuthenticated, afterLogout }) {
  const [account, setAccount] = useState(null);
  const [settingsState, setSettingsState] = useState(INITIAL_SETTINGS);
  const [paymentState, setPaymentState] = useState(INITIAL_PAYMENT);
  const [billingPlans, setBillingPlans] = useState([]);
  const [adminState, setAdminState] = useState(INITIAL_ADMIN);
  const [authState, setAuthState] = useState(INITIAL_AUTH);
  const [authDialog, setAuthDialog] = useState({ open: false, reason: "" });

  function applyUserSettings(settings) {
    const mode = settings?.default_interview_mode;
    if (mode === "interviewer" || mode === "candidate") {
      setSettingsState((current) => ({ ...current, default_interview_mode: mode, status: "idle" }));
      setProfile((current) => ({ ...current, mode }));
    }
  }

  async function loadAccount() {
    try {
      const result = await api.getAccount();
      setAccount(result);
      applyUserSettings(result.settings);
      return result;
    } catch (_error) {
      setAccount(null);
      return null;
    }
  }

  async function loadUserSettings() {
    if (!api.getSettings) return;
    try {
      const result = await api.getSettings();
      applyUserSettings(result);
    } catch (_error) {
      setSettingsState((current) => ({ ...current, status: "idle" }));
    }
  }

  async function loadBillingPlans() {
    if (!api.listBillingPlans) return [];
    try {
      const plans = await api.listBillingPlans();
      setBillingPlans(Array.isArray(plans) ? plans : []);
      return plans;
    } catch (_error) {
      setBillingPlans([]);
      return [];
    }
  }

  async function changeDefaultMode(mode) {
    if (mode !== "interviewer" && mode !== "candidate") return;
    setProfile((current) => ({ ...current, mode }));
    setSettingsState((current) => ({ ...current, default_interview_mode: mode, status: "saving", error: "" }));
    if (!account || !api.updateSettings) {
      setSettingsState((current) => ({
        ...current,
        status: account ? "idle" : "error",
        error: account ? "" : "登录后才能同步设置。"
      }));
      return;
    }
    try {
      const result = await api.updateSettings({ default_interview_mode: mode });
      setSettingsState({ status: "saved", default_interview_mode: result?.default_interview_mode || mode });
    } catch (error) {
      setSettingsState((current) => ({
        ...current,
        status: "error",
        error: `设置保存失败：${normalizeDesktopError(error.message)}`
      }));
    }
  }

  async function finishAuthentication() {
    const authenticatedAccount = await loadAccount();
    await Promise.all([loadUserSettings(), loadBillingPlans()]);
    await afterAuthenticated?.(authenticatedAccount);
    setAuthState((current) => ({ ...current, password: "", status: "success", error: "" }));
    setAuthDialog({ open: false, reason: "" });
  }

  async function submitAuth(event) {
    event?.preventDefault();
    if (authState.status === "loading") return;
    setAuthState((current) => ({ ...current, status: "loading", error: "" }));
    try {
      const email = authState.email.trim();
      const password = authState.password.trim();
      const payload = {
        email,
        password,
        display_name: authState.displayName.trim() || undefined,
        platform: "desktop"
      };
      if (authState.mode === "register") await api.register(payload);
      else await api.login(payload);
      await finishAuthentication();
    } catch (error) {
      setAuthState((current) => ({ ...current, status: "error", error: normalizeDesktopError(error.message) }));
    }
  }

  async function useDevAccount() {
    setAuthState((current) => ({ ...current, status: "loading", error: "" }));
    try {
      await api.devLogin({ user_id: "desktop-dev-user", display_name: "桌面端开发用户", platform: "desktop" });
      await finishAuthentication();
    } catch (error) {
      setAuthState((current) => ({ ...current, status: "error", error: normalizeDesktopError(error.message) }));
    }
  }

  async function logout() {
    await api.logout();
    setAccount(null);
    setSettingsState(INITIAL_SETTINGS);
    setPaymentState(INITIAL_PAYMENT);
    setBillingPlans([]);
    setAdminState(INITIAL_ADMIN);
    await afterLogout?.();
  }

  async function loadAdminSecurity() {
    if (!api.listSecurityEvents || !api.listRoles) return;
    setAdminState((current) => ({ ...current, status: "loading", error: "" }));
    try {
      const [events, roles] = await Promise.all([api.listSecurityEvents(), api.listRoles()]);
      setAdminState((current) => ({
        ...current,
        status: "ready",
        events: Array.isArray(events) ? events : [],
        roles: Array.isArray(roles) ? roles : [],
        error: ""
      }));
    } catch (error) {
      setAdminState((current) => ({ ...current, status: "error", error: normalizeDesktopError(error.message) }));
    }
  }

  function updateAdminField(key, value) {
    setAdminState((current) => ({ ...current, [key]: value }));
  }

  async function grantAdminRole() {
    if (!adminState.userId.trim()) return;
    setAdminState((current) => ({ ...current, status: "saving", error: "" }));
    try {
      await api.grantRole({ user_id: adminState.userId.trim(), role: adminState.role });
      await loadAdminSecurity();
    } catch (error) {
      setAdminState((current) => ({ ...current, status: "error", error: normalizeDesktopError(error.message) }));
    }
  }

  async function revokeAdminRole(role) {
    if (!role?.user_id || !role?.role) return;
    setAdminState((current) => ({ ...current, status: "saving", error: "" }));
    try {
      await api.revokeRole({ user_id: role.user_id, role: role.role });
      await loadAdminSecurity();
    } catch (error) {
      setAdminState((current) => ({ ...current, status: "error", error: normalizeDesktopError(error.message) }));
    }
  }

  async function createReviewSiteTestData() {
    if (!api.createReviewSiteTestData) return;
    setAdminState((current) => ({
      ...current,
      testDataStatus: "loading",
      testDataMessage: "",
      error: ""
    }));
    try {
      const result = await api.createReviewSiteTestData();
      const created = Number(result?.plan_count || 0) > 0;
      setAdminState((current) => ({
        ...current,
        testDataStatus: "success",
        testDataMessage: created ? "测试计划已创建，可前往复习站查看。" : "测试计划已存在，无需重复创建。"
      }));
    } catch (error) {
      setAdminState((current) => ({
        ...current,
        testDataStatus: "error",
        testDataMessage: normalizeDesktopError(error.message)
      }));
    }
  }

  function requireAccount(reason) {
    if (account) return true;
    setAuthDialog({ open: true, reason });
    return false;
  }

  async function createPayment(provider, amountCredits = paymentState.amount, planCode = paymentState.planCode) {
    if (!requireAccount("充值积分前需要先登录账号。")) return;
    setPaymentState({ status: "loading", provider, amount: amountCredits });
    try {
      const order = await api.createPaymentOrder({
        amount_credits: amountCredits,
        plan_code: planCode || undefined,
        payment_provider: provider,
        metadata: { source: "web_account_center" }
      });
      setPaymentState({ status: "pending", provider, amount: amountCredits, order });
      if (provider === "alipay" && order.pay_url) window.open(order.pay_url, "_blank", "noopener,noreferrer");
      pollPaymentOrder(order.external_order_id);
    } catch (error) {
      setPaymentState({ status: "error", provider, amount: amountCredits, error: normalizeDesktopError(error.message) });
    }
  }

  async function pollPaymentOrder(orderId, attempt = 0) {
    if (!orderId || attempt > 60) return;
    window.setTimeout(async () => {
      try {
        const order = await api.getPaymentOrder(orderId);
        setPaymentState((current) => ({ ...current, order, status: order.status === "paid" ? "paid" : current.status }));
        if (order.status === "paid") {
          await loadAccount();
          return;
        }
        pollPaymentOrder(orderId, attempt + 1);
      } catch (_error) {
        pollPaymentOrder(orderId, attempt + 1);
      }
    }, 3000);
  }

  return {
    account,
    billingPlans,
    adminState,
    authDialog,
    authState,
    paymentState,
    settingsState,
    changeDefaultMode,
    createReviewSiteTestData,
    createPayment,
    grantAdminRole,
    loadAccount,
    loadBillingPlans,
    loadAdminSecurity,
    loadUserSettings,
    logout,
    requireAccount,
    revokeAdminRole,
    setAuthDialog,
    setAuthState,
    setPaymentState,
    submitAuth,
    updateAdminField,
    useDevAccount
  };
}
