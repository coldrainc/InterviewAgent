import { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { PanelLeftOpen } from "lucide-react";
import "./styles.css";
import "./styles/foundation.css";
import "./styles/today.css";
import "./styles/workspaces.css";
import "./styles/auth.css";
import "./styles/admin.css";
import { getInterviewAgentClient } from "./apiClient";
import { useAccountController } from "./hooks/useAccountController";
import { useInterviewSessionController } from "./hooks/useInterviewSessionController";
import { useSidebarNavigation } from "./hooks/useSidebarNavigation";
import { useAdminConsole } from "./features/admin/useAdminConsole";
import { mergeUniqueById } from "./hooks/useInfiniteScroll";
import { AppScreenRouter } from "./app/AppScreenRouter";
import { fallbackIndustries, fallbackModels, llmModes } from "./constants/interview";
import Sidebar from "./components/sidebar/Sidebar";
import { SidebarBackdrop } from "./components/sidebar/SidebarBackdrop";
import { AuthDialog } from "./components/account/AccountCenter";
import { AuthGate } from "./components/account/AuthGate";
import { Topbar } from "./components/chat/Chat";
import {
  currentModel,
  normalizeDesktopError
} from "./utils/interview";

const api = getInterviewAgentClient();
const THEME_STORAGE_KEY = "interview-agent-theme";

function readStoredTheme() {
  try {
    return localStorage.getItem(THEME_STORAGE_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

try {
  document.documentElement.dataset.theme = readStoredTheme();
} catch {}

function App() {
  const accountIdentityRef = useRef(null);
  const [authReady, setAuthReady] = useState(false);
  const [screen, setScreen] = useState("home");
  const [navigationTarget, setNavigationTarget] = useState(null);
  const sidebar = useSidebarNavigation();
  const [theme, setTheme] = useState(readStoredTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {}
  }, [theme]);
  const [health, setHealth] = useState({ status: "checking" });
  const [resumeImport, setResumeImport] = useState({ status: "idle" });
  const [requirementsImport, setRequirementsImport] = useState({ status: "idle" });
  const [resumeLibrary, setResumeLibrary] = useState([]);
  const [resumeLibraryState, setResumeLibraryState] = useState({ loading: false, hasMore: true, error: "" });
  const resumeLibraryRef = useRef([]);
  const resumeLoadingRef = useRef(false);
  const [selectedResumeId, setSelectedResumeId] = useState("");
  const [opsState, setOpsState] = useState({
    status: "idle",
    jobs: [],
    traces: [],
    evalRuns: [],
    metrics: {},
    message: "",
    pages: { jobs: true, traces: true, evalRuns: true },
    loadingKinds: []
  });
  const opsRefs = useRef({ jobs: [], traces: [], evalRuns: [] });
  const opsLoadingRef = useRef(new Set());
  const [industryOptions, setIndustryOptions] = useState(fallbackIndustries);
  const [modelOptions, setModelOptions] = useState(fallbackModels);
  const [selectedModelId, setSelectedModelId] = useState("deepseek-v4-pro");
  const [selectedLlmMode, setSelectedLlmMode] = useState("standard");
  const [profile, setProfile] = useState({
    mode: "interviewer",
    industry: "internet",
    candidateName: "",
    targetRole: "AI 应用工程师",
    seniority: "高级",
    resumeSummary: "",
    resumeText: "",
    projectExperience: "",
    interviewerRequirements: "",
    interviewGoal: "请基于我的简历和做过的事情进行 AI 工程面试，重点深挖真实项目、RAG/Agent、评测、上线和安全治理。"
  });
  const {
    account,
    billingPlans,
    adminState,
    authDialog,
    authState,
    paymentState,
    settingsState,
    changeDefaultMode,
    createPayment,
    createReviewSiteTestData,
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
  } = useAccountController({
    api,
    setProfile,
    afterAuthenticated: async (authenticatedAccount) => {
      const authenticatedIdentity = authenticatedAccount
        ? `${authenticatedAccount.tenant_id}:${authenticatedAccount.user_id}`
        : "";
      resetPrivateClientState(authenticatedIdentity);
      accountIdentityRef.current = authenticatedIdentity;
      await Promise.all([loadResumeLibrary(), sessionController.loadSessionHistory()]);
    },
    afterLogout: () => {
      resetPrivateClientState("");
      accountIdentityRef.current = "";
    }
  });
  const sessionController = useInterviewSessionController({
    api,
    profile,
    industryOptions,
    selectedResumeId,
    selectedModelId,
    llmMode: llmModes.find((mode) => mode.value === selectedLlmMode) || llmModes[1],
    accountKey: account ? `${account.tenant_id}:${account.user_id}` : "",
    requireAccount,
    loadAccount
  });
  const adminConsole = useAdminConsole(api.admin, account?.role === "admin" || account?.role === "server");
  const {
    appendMessage, busy, completed, deleteSession, editMessage, handleKeyDown, handleSubmit,
    historyState, input, loadReportScores, loadSessionHistory, messages, messagesEndRef,
    offline, reportScores, restoreLastSession, restoreSession, sessionHistory,
    sessionId, setInput, setOffline, setWebSearch, startSession: createSession,
    stopGeneration, textareaRef, webSearch, withdrawMessage
  } = sessionController;

  useEffect(() => {
    bootstrap();
  }, []);

  useEffect(() => {
    const nextIdentity = account ? `${account.tenant_id}:${account.user_id}` : "";
    const previousIdentity = accountIdentityRef.current;
    if (previousIdentity === null) {
      accountIdentityRef.current = nextIdentity;
      return;
    }
    if (previousIdentity && previousIdentity !== nextIdentity) {
      resetPrivateClientState(nextIdentity);
    }
    accountIdentityRef.current = nextIdentity;
  }, [account?.tenant_id, account?.user_id]);

  useEffect(() => {
    loadIndustryOptions(profile.targetRole);
  }, [profile.targetRole]);

  useEffect(() => {
    if (screen === "ops" && account) {
      loadOperationsCenter();
    }
  }, [screen, account]);

  useEffect(() => {
    if (screen === "account" && account?.role === "admin") {
      loadAdminSecurity();
    }
  }, [screen, account?.role]);

  useEffect(() => {
    if (screen === "admin" && (account?.role === "admin" || account?.role === "server")) {
      adminConsole.load();
    }
  }, [screen, account?.role, adminConsole.load]);

  useEffect(() => {
    if (screen === "admin" && account?.role !== "admin" && account?.role !== "server") {
      setScreen("home");
    }
  }, [screen, account?.role]);

  const status = useMemo(() => {
    if (health.status === "ok") {
      return {
        label: "已连接",
        tone: "ok",
        detail: "服务在线，可以开始面试"
      };
    }
    if (health.status === "error") {
      return {
        label: "服务暂不可用",
        tone: "fail",
        detail: normalizeDesktopError(health.error, "暂时无法连接服务，请稍后重试。")
      };
    }
    return { label: "检查中", tone: "checking", detail: "正在连接本地服务" };
  }, [health]);

  function resetPrivateClientState(nextIdentity = "") {
    sessionController.switchAccountScope(nextIdentity);
    setResumeLibrary([]);
    resumeLibraryRef.current = [];
    resumeLoadingRef.current = false;
    setResumeLibraryState({ loading: false, hasMore: true, error: "" });
    setSelectedResumeId("");
    setResumeImport({ status: "idle" });
    setRequirementsImport({ status: "idle" });
    setProfile((current) => ({
      ...current,
      candidateName: "",
      resumeSummary: "",
      resumeText: "",
      projectExperience: "",
      interviewerRequirements: ""
    }));
    opsRefs.current = { jobs: [], traces: [], evalRuns: [] };
    opsLoadingRef.current.clear();
    setOpsState({ status: "idle", jobs: [], traces: [], evalRuns: [], metrics: {}, message: "", pages: { jobs: true, traces: true, evalRuns: true }, loadingKinds: [] });
    setScreen("home");
  }

  async function bootstrap() {
    try {
      await Promise.all([checkHealth(), loadIndustryOptions(), loadModelOptions()]);
      if (api.hasToken?.()) {
        const authenticatedAccount = await loadAccount();
        if (!authenticatedAccount) {
          resetPrivateClientState("");
          return;
        }
        const authenticatedAccountKey = `${authenticatedAccount.tenant_id}:${authenticatedAccount.user_id}`;
        resetPrivateClientState(authenticatedAccountKey);
        accountIdentityRef.current = authenticatedAccountKey;
        await Promise.all([loadUserSettings(), loadBillingPlans()]);
        await loadResumeLibrary();
        await loadSessionHistory();
        await loadReportScores();
        await restoreLastSession(authenticatedAccountKey);
        await loadOperationsCenter();
      }
    } finally {
      setAuthReady(true);
    }
  }

  async function checkHealth() {
    setHealth({ status: "checking" });
    try {
      const result = await api.health();
      setHealth({ status: "ok", ...result });
    } catch (error) {
      setHealth({ status: "error", error: normalizeDesktopError(error) });
    }
  }

  async function loadIndustryOptions(targetRole = profile.targetRole) {
    try {
      const result = await api.listIndustries(targetRole || "AI 应用工程师");
      const options = Array.isArray(result) && result.length ? result : fallbackIndustries;
      setIndustryOptions(options);
      if (!options.some((item) => item.value === profile.industry)) {
        setProfile((current) => ({ ...current, industry: options[0].value }));
      }
    } catch (_error) {
      setIndustryOptions(fallbackIndustries);
    }
  }

  async function loadModelOptions() {
    try {
      const result = await api.listModels();
      const options = Array.isArray(result) && result.length ? result : fallbackModels;
      setModelOptions(options);
      if (!options.some((item) => item.id === selectedModelId)) {
        setSelectedModelId(options[0].id);
      }
    } catch (_error) {
      setModelOptions(fallbackModels);
    }
  }

  async function loadResumeLibrary({ append = false } = {}) {
    if (resumeLoadingRef.current || (append && !resumeLibraryState.hasMore)) return;
    resumeLoadingRef.current = true;
    setResumeLibraryState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const resumes = await api.listResumes({ limit: 20, offset: append ? resumeLibraryRef.current.length : 0 });
      const incoming = Array.isArray(resumes) ? resumes : [];
      const existing = append ? resumeLibraryRef.current : [];
      const ids = new Set(existing.map((resume) => resume.id));
      const next = existing.concat(incoming.filter((resume) => !ids.has(resume.id)));
      resumeLibraryRef.current = next;
      setResumeLibrary(next);
      setResumeLibraryState({ loading: false, hasMore: incoming.length === 20, error: "" });
      if (!selectedResumeId && next.length > 0) {
        applyResume(next[0]);
      }
    } catch (error) {
      const message = `历史简历暂未加载：${normalizeDesktopError(error.message)}`;
      if (!append) {
        resumeLibraryRef.current = [];
        setResumeLibrary([]);
        setResumeImport({ status: "error", error: message });
      }
      setResumeLibraryState((current) => ({ ...current, loading: false, error: message }));
    } finally {
      resumeLoadingRef.current = false;
    }
  }

  function applyResume(resume) {
    if (!resume) return;
    setSelectedResumeId(resume.id);
    setProfile((current) => ({
      ...current,
      resumeSummary: resume.summary || current.resumeSummary,
      resumeText: resume.text || current.resumeText
    }));
    setResumeImport({
      status: "success",
      filename: resume.filename,
      fileType: resume.file_type,
      truncated: Boolean(resume.truncated),
      persisted: true
    });
  }

  async function selectResume(resumeId) {
    if (!resumeId) {
      setSelectedResumeId("");
      return;
    }
    const cached = resumeLibrary.find((resume) => resume.id === resumeId);
    if (cached?.text) {
      applyResume(cached);
      return;
    }
    try {
      const resume = await api.getResume(resumeId);
      applyResume(resume);
    } catch (error) {
      setResumeImport({ status: "error", error: `选择简历失败：${normalizeDesktopError(error.message)}` });
    }
  }

  async function deleteSelectedResume() {
    if (!selectedResumeId || busy) return;
    try {
      const result = await api.deleteResume(selectedResumeId);
      if (!result.deleted) {
        setResumeImport({ status: "error", error: "删除简历失败：未找到当前简历。" });
        return;
      }
      setResumeLibrary((current) => {
        const next = current.filter((resume) => resume.id !== selectedResumeId);
        resumeLibraryRef.current = next;
        return next;
      });
      setSelectedResumeId("");
      setProfile((current) => ({ ...current, resumeSummary: "", resumeText: "" }));
      setResumeImport({ status: "idle" });
      appendMessage("system", "当前简历已删除。");
    } catch (error) {
      setResumeImport({ status: "error", error: `删除简历失败：${normalizeDesktopError(error.message)}` });
    }
  }

  async function loadOperationsCenter({ appendKind = "" } = {}) {
    if (!api.listJobs || !api.listAgentTraces || !api.getOpsMetrics) return;
    if (appendKind) {
      if (opsLoadingRef.current.has(appendKind) || !opsState.pages?.[appendKind]) return;
      const loaders = { jobs: api.listJobs, traces: api.listAgentTraces, evalRuns: api.listEvalRuns };
      const loader = loaders[appendKind];
      if (!loader) return;
      opsLoadingRef.current.add(appendKind);
      setOpsState((current) => ({ ...current, error: "", loadingKinds: [...current.loadingKinds, appendKind] }));
      try {
        const incoming = await loader({ limit: 20, offset: opsRefs.current[appendKind].length });
        const next = mergeUniqueById(opsRefs.current[appendKind], Array.isArray(incoming) ? incoming : []);
        opsRefs.current[appendKind] = next;
        setOpsState((current) => ({
          ...current,
          [appendKind]: next,
          pages: { ...current.pages, [appendKind]: incoming.length === 20 }
        }));
      } catch (error) {
        setOpsState((current) => ({ ...current, error: `更多任务数据加载失败：${normalizeDesktopError(error.message)}` }));
      } finally {
        opsLoadingRef.current.delete(appendKind);
        setOpsState((current) => ({ ...current, loadingKinds: current.loadingKinds.filter((kind) => kind !== appendKind) }));
      }
      return;
    }
    if (opsLoadingRef.current.has("all")) return;
    opsLoadingRef.current.add("all");
    try {
      setOpsState((current) => ({ ...current, status: "loading", error: "", message: "" }));
      const [jobs, traces, metrics, evalRuns] = await Promise.all([
        api.listJobs({ limit: 20, offset: 0 }),
        api.listAgentTraces({ limit: 20, offset: 0 }),
        api.getOpsMetrics(),
        api.listEvalRuns ? api.listEvalRuns({ limit: 20, offset: 0 }) : Promise.resolve([])
      ]);
      opsRefs.current = { jobs, traces, evalRuns };
      setOpsState({
        status: "idle",
        jobs: Array.isArray(jobs) ? jobs : [],
        traces: Array.isArray(traces) ? traces : [],
        evalRuns: Array.isArray(evalRuns) ? evalRuns : [],
        metrics: metrics || {},
        message: "",
        pages: { jobs: jobs.length === 20, traces: traces.length === 20, evalRuns: evalRuns.length === 20 },
        loadingKinds: []
      });
    } catch (error) {
      setOpsState((current) => ({ ...current, status: "error", error: `任务数据加载失败：${normalizeDesktopError(error.message)}` }));
    } finally {
      opsLoadingRef.current.delete("all");
    }
  }

  async function runOperationsJob(kind) {
    if (!requireAccount("运行任务与评测前需要先登录账号。")) return;
    try {
      setOpsState((current) => ({ ...current, status: "loading", error: "", message: "" }));
      const baseInput = {
        session_id: sessionId || undefined,
        category: profile.industry || "internet",
        target_role: profile.targetRole,
        seniority: profile.seniority,
        profile: {
          targetRole: profile.targetRole,
          industry: profile.industry,
          seniority: profile.seniority,
          mode: profile.mode
        }
      };
      if (kind === "evaluation") {
        await api.createEvalRun?.({
          name: "当前会话与题库质量评估",
          metadata: { ...baseInput, scenario: "quality_gate" }
        });
      } else if (kind === "multi_agent") {
        await api.runWorkflow?.({
          workflow_type: "multi_agent",
          title: "多 Agent 审核当前准备度",
          input: { ...baseInput, scenario: "session_review" }
        });
      } else if (kind === "study_plan") {
        await api.runWorkflow?.({
          workflow_type: "workflow",
          title: "刷题与学习计划生成",
          input: { ...baseInput, scenario: "study_plan" }
        });
      } else {
        await api.runWorkflow?.({
          workflow_type: "workflow",
          title: "面试准备度复盘",
          input: { ...baseInput, scenario: "interview_readiness" }
        });
      }
      setOpsState((current) => ({ ...current, message: "任务已提交，正在后台执行。" }));
      window.setTimeout(loadOperationsCenter, 500);
      window.setTimeout(loadOperationsCenter, 1500);
      window.setTimeout(loadOperationsCenter, 3500);
    } catch (error) {
      setOpsState((current) => ({ ...current, status: "error", error: `任务提交失败：${normalizeDesktopError(error.message)}` }));
    }
  }

  async function cancelOperationsJob(jobId) {
    if (!jobId || !api.cancelJob) return;
    try {
      await api.cancelJob(jobId);
      await loadOperationsCenter();
    } catch (error) {
      setOpsState((current) => ({ ...current, status: "error", error: `取消任务失败：${normalizeDesktopError(error.message)}` }));
    }
  }

  async function importResume() {
    if (busy || resumeImport.status === "loading") return;
    if (!requireAccount("上传和保存简历前需要先登录账号。")) return;
    setResumeImport({ status: "loading" });
    try {
      const result = await api.importResume();
      if (result.canceled) {
        setResumeImport({ status: "idle" });
        return;
      }
      applyResume(result);
      setResumeLibrary((current) => {
        const withoutDuplicate = current.filter((resume) => resume.id !== result.id);
        const next = [result, ...withoutDuplicate];
        resumeLibraryRef.current = next;
        return next;
      });
      appendMessage(
        "system",
        `已保存并使用简历：${result.filename}${result.truncated ? "（内容较长，已截断到安全长度）" : ""}`
      );
    } catch (error) {
      const message = normalizeDesktopError(error.message);
      setResumeImport({ status: "error", error: message });
      appendMessage("system", `导入简历失败：${message}`);
    }
  }

  async function importInterviewerRequirements() {
    if (busy || requirementsImport.status === "loading") return;
    if (!requireAccount("上传面试官要求前需要先登录账号。")) return;
    if (!api.parseDocument) {
      setRequirementsImport({ status: "error", error: "当前客户端暂不支持上传解析，请直接粘贴面试官要求。" });
      return;
    }
    setRequirementsImport({ status: "loading" });
    try {
      const result = await api.parseDocument({
        accept: ".pdf,.md,.markdown,.txt,application/pdf,text/markdown,text/plain"
      });
      if (result.canceled) {
        setRequirementsImport({ status: "idle" });
        return;
      }
      setProfile((current) => ({
        ...current,
        interviewerRequirements: result.text || result.summary || current.interviewerRequirements
      }));
      setRequirementsImport({
        status: "success",
        filename: result.filename || result.path,
        truncated: Boolean(result.truncated)
      });
      appendMessage(
        "system",
        `已导入面试官要求：${result.filename || result.path}${result.truncated ? "（内容较长，已截断到安全长度）" : ""}`
      );
    } catch (error) {
      setRequirementsImport({ status: "error", error: normalizeDesktopError(error.message) });
    }
  }

  function selectLlmMode(value) {
    const mode = llmModes.find((item) => item.value === value) || llmModes[1];
    setSelectedLlmMode(mode.value);
    setSelectedModelId(mode.modelId);
  }

  function changeScreen(nextScreen, target = null) {
    setNavigationTarget(target ? { ...target, nonce: Date.now() } : null);
    setScreen(nextScreen);
    sidebar.closeAfterNavigation();
  }

  async function openReportSession(sessionId) {
    if (!sessionId) return;
    await restoreSession(sessionId);
    setScreen("chat");
  }

  if (!account) {
    return (
      <AuthGate
        authReady={authReady}
        authState={authState}
        theme={theme}
        onAuthChange={setAuthState}
        onAuthSubmit={submitAuth}
        onToggleTheme={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
      />
    );
  }

  return (
    <main className={`app-shell ${sidebar.open ? "sidebar-open" : "sidebar-collapsed"}`}>
      <Sidebar
        screen={screen}
        profile={profile}
        account={account}
        sessionHistory={sessionHistory}
        historyState={historyState}
        activeSessionId={sessionId}
        busy={busy}
        reportScores={reportScores}
        onNewSession={() => createSession()}
        onReloadSessions={loadSessionHistory}
        onRestoreSession={restoreSession}
        onDeleteSession={deleteSession}
        onScreenChange={changeScreen}
        onToggleSidebar={sidebar.closeSidebar}
      />
      <SidebarBackdrop
        open={sidebar.compact && sidebar.open}
        onClose={sidebar.closeSidebar}
      />
      <button
        type="button"
        className="sidebar-fab"
        onClick={sidebar.openSidebar}
        title="展开菜单 (⌘B / Ctrl+B)"
        aria-label="展开菜单"
        aria-controls="app-sidebar"
        aria-expanded={sidebar.open}
      >
        <PanelLeftOpen size={17} />
      </button>

      <section
        className="workspace"
        inert={sidebar.compact && sidebar.open ? true : undefined}
        aria-hidden={sidebar.compact && sidebar.open ? "true" : undefined}
      >
        <Topbar
          sessionId={sessionId}
          offline={offline}
          webSearch={webSearch}
          completed={completed}
          status={status}
          profile={profile}
          model={currentModel(modelOptions, selectedModelId)}
          account={account}
          screen={screen}
          theme={theme}
          onToggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
          onOpenAccount={() => setScreen("account")}
          onOpenChat={() => setScreen("chat")}
        />

        <AppScreenRouter
          screen={screen}
          model={{
            account: {
              account, authState, modelOptions, selectedModelId, paymentState, adminState, billingPlans, client: api,
              onAuthChange: setAuthState, onAuthSubmit: submitAuth, onDevLogin: useDevAccount,
              onLogout: logout, onSelectModel: setSelectedModelId, onPaymentStateChange: setPaymentState,
              onCreatePayment: createPayment, onReloadAdmin: loadAdminSecurity,
              onAdminFieldChange: updateAdminField, onGrantRole: grantAdminRole,
              onRevokeRole: revokeAdminRole, onCreateReviewSiteTestData: createReviewSiteTestData,
              onBack: () => setScreen("chat")
            },
            admin: {
              account,
              state: adminConsole.state,
              actions: adminConsole,
              onBack: () => setScreen("home")
            },
            settings: {
              account, profile, settingsState, onModeChange: changeDefaultMode,
              onBack: () => setScreen("chat")
            },
            operations: {
              opsState, onReload: loadOperationsCenter, onCancelJob: cancelOperationsJob,
              onLoadMore: (kind) => loadOperationsCenter({ appendKind: kind }),
              onRunWorkflow: () => runOperationsJob("workflow"),
              onRunStudyPlan: () => runOperationsJob("study_plan"),
              onRunEvaluation: () => runOperationsJob("evaluation"),
              onRunMultiAgent: () => runOperationsJob("multi_agent"),
              onBack: () => setScreen("chat")
            },
            setup: {
              profile, offline, webSearch, modelOptions, selectedModelId, selectedLlmMode,
              industryOptions, resumeImport, requirementsImport, resumeLibrary, resumeLibraryState, selectedResumeId, busy,
              onNewSession: () => createSession(), onImportResume: importResume,
              onImportRequirements: importInterviewerRequirements, onSelectResume: selectResume,
              onDeleteResume: deleteSelectedResume, onReloadResumes: loadResumeLibrary,
              onLoadMoreResumes: () => loadResumeLibrary({ append: true }),
              onProfileChange: setProfile, onDefaultModeChange: changeDefaultMode,
              onOfflineChange: setOffline, onWebSearchChange: setWebSearch,
              onSelectModel: setSelectedModelId, onSelectLlmMode: selectLlmMode,
              onBack: () => setScreen("chat")
            },
            home: {
              account, profile, onNavigate: changeScreen, onOpenSession: openReportSession,
              onRequireAuth: () => setAuthDialog({ open: true, reason: "登录后才能同步学习数据。" }),
              onStartInterview: async (seed, extra) => {
                await createSession(seed, extra);
                setScreen("chat");
              }
            },
            reports: {
              account, onOpenSession: openReportSession, onNavigate: changeScreen,
              onRequireAuth: () => setAuthDialog({ open: true, reason: "登录后才能查看面试报告。" }),
              onChat: () => setScreen("chat")
            },
            interviewer: {
              account, profile,
              onRequireAuth: () => setAuthDialog({ open: true, reason: "登录后才能保存面试题纲与评价证据。" }),
              onStartInterview: (seed, extra) => createSession(seed, extra)
            },
            training: {
              account,
              navigationTarget,
              onRequireAuth: () => setAuthDialog({ open: true, reason: "登录后作答才会记录进度与错题。" })
            },
            review: {
              navigationTarget,
              onBack: () => setScreen("home"),
              onNavigate: changeScreen,
              onOpenPlanner: () => setScreen("planner"),
              onStartInterview: async (seed, extra) => {
                await createSession(seed, extra);
                setScreen("chat");
              }
            },
            planner: { onBack: () => setScreen("review-site"), onGenerated: () => setScreen("review-site") },
            chat: {
              busy, industryOptions, input, messages, messagesEndRef, profile, sessionId, textareaRef,
              onEditMessage: editMessage, onInputChange: setInput, onKeyDown: handleKeyDown,
              onQuickPrompt: (prompt) => createSession(prompt), onStart: () => createSession(),
              onStop: stopGeneration, onSubmit: handleSubmit, onWithdrawMessage: withdrawMessage
            }
          }}
        />

        {authDialog.open && (
          <AuthDialog
            reason={authDialog.reason}
            authState={authState}
            onAuthChange={setAuthState}
            onAuthSubmit={submitAuth}
            onDevLogin={useDevAccount}
            onClose={() => setAuthDialog({ open: false, reason: "" })}
          />
        )}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
