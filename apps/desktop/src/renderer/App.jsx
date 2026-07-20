import { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { getInterviewAgentClient } from "./apiClient";
import { fallbackIndustries, fallbackModels, llmModes } from "./constants/interview";
import Sidebar from "./components/sidebar/Sidebar";
import { AccountCenter, AuthDialog } from "./components/account/AccountCenter";
import { SettingsCenter } from "./components/settings/SettingsCenter";
import { SetupCenter } from "./components/setup/SetupCenter";
import { StudyCenter } from "./components/study/StudyCenter";
import { Topbar, EmptyState, Message, Typing, Composer } from "./components/chat/Chat";
import {
  buildFocusAreas,
  buildInterviewGoal,
  currentIndustry,
  currentModel,
  formatTime,
  normalizeDesktopError,
  turnsToMessages
} from "./utils/interview";

const api = getInterviewAgentClient();
const LAST_SESSION_STORAGE_KEY = "interview-agent-last-session-id";
const SESSION_MESSAGES_STORAGE_PREFIX = "interview-agent-session-messages:";

function getLastSessionId() {
  try {
    return window.localStorage.getItem(LAST_SESSION_STORAGE_KEY) || "";
  } catch (_error) {
    return "";
  }
}

function setLastSessionId(value) {
  try {
    if (value) {
      window.localStorage.setItem(LAST_SESSION_STORAGE_KEY, value);
    } else {
      window.localStorage.removeItem(LAST_SESSION_STORAGE_KEY);
    }
  } catch (_error) {
    // Ignore storage failures so private browsing modes still work.
  }
}

function getCachedSessionMessages(sessionId) {
  if (!sessionId) return [];
  try {
    const raw = window.localStorage.getItem(`${SESSION_MESSAGES_STORAGE_PREFIX}${sessionId}`);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (_error) {
    return [];
  }
}

function setCachedSessionMessages(sessionId, value) {
  if (!sessionId) return;
  try {
    if (Array.isArray(value) && value.length) {
      window.localStorage.setItem(
        `${SESSION_MESSAGES_STORAGE_PREFIX}${sessionId}`,
        JSON.stringify(value.map((message) => ({
          id: message.id,
          role: message.role,
          text: message.text,
          fallback: Boolean(message.fallback),
          usage: message.usage || null,
          modelId: message.modelId || "",
          time: message.time || "",
          turnIndex: message.turnIndex || null,
          stopped: Boolean(message.stopped)
        })))
      );
    } else {
      window.localStorage.removeItem(`${SESSION_MESSAGES_STORAGE_PREFIX}${sessionId}`);
    }
  } catch (_error) {
    // Ignore storage failures so private browsing modes still work.
  }
}

function hasPendingCachedMessage(messages) {
  return messages.some((message) => (
    message.role === "agent"
    && (
      String(message.text || "").includes("正在分析回答")
      || String(message.text || "").includes("流式连接中断")
      || String(message.text || "").includes("正在使用普通请求重试")
    )
  ));
}

function shouldUseCachedMessages(cachedMessages, restoredMessages) {
  if (!cachedMessages.length) return false;
  if (hasPendingCachedMessage(cachedMessages)) return false;
  if (restoredMessages.length > cachedMessages.length) return false;
  return true;
}

function App() {
  const [screen, setScreen] = useState("chat");
  const [health, setHealth] = useState({ status: "checking" });
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [offline, setOffline] = useState(false);
  const [webSearch, setWebSearch] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [resumeImport, setResumeImport] = useState({ status: "idle" });
  const [requirementsImport, setRequirementsImport] = useState({ status: "idle" });
  const [resumeLibrary, setResumeLibrary] = useState([]);
  const [selectedResumeId, setSelectedResumeId] = useState("");
  const [sessionHistory, setSessionHistory] = useState([]);
  const [historyState, setHistoryState] = useState({ status: "idle" });
  const [studyState, setStudyState] = useState({
    status: "idle",
    plan: [],
    questions: { items: [], total: 0, limit: 30, offset: 0 },
    importMessage: "",
    seedMessage: ""
  });
  const [studyFilters, setStudyFilters] = useState({ category: "", year: "", subject: "", questionType: "" });
  const [industryOptions, setIndustryOptions] = useState(fallbackIndustries);
  const [modelOptions, setModelOptions] = useState(fallbackModels);
  const [selectedModelId, setSelectedModelId] = useState("deepseek-v4-pro");
  const [selectedLlmMode, setSelectedLlmMode] = useState("standard");
  const [account, setAccount] = useState(null);
  const [settingsState, setSettingsState] = useState({ status: "idle", default_interview_mode: "interviewer" });
  const [paymentState, setPaymentState] = useState({ status: "idle", amount: "10", provider: "alipay" });
  const [authState, setAuthState] = useState({ mode: "login", email: "", password: "", displayName: "", status: "idle" });
  const [authDialog, setAuthDialog] = useState({ open: false, reason: "" });
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
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const activeRequestRef = useRef(null);

  useEffect(() => {
    bootstrap();
  }, []);

  useEffect(() => {
    loadIndustryOptions(profile.targetRole);
  }, [profile.targetRole]);

  useEffect(() => {
    if (screen === "study" && account) {
      loadStudyCenter();
    }
  }, [screen, account, studyFilters.category, studyFilters.year, studyFilters.subject, studyFilters.questionType]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  useEffect(() => {
    if (sessionId && messages.length) {
      setCachedSessionMessages(sessionId, messages);
    }
  }, [sessionId, messages]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 168)}px`;
  }, [input]);

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
        label: "API 未启动",
        tone: "fail",
        detail: health.error || "请先运行 make api"
      };
    }
    return { label: "检查中", tone: "checking", detail: "正在连接本地服务" };
  }, [health]);

  async function bootstrap() {
    await checkHealth();
    await loadIndustryOptions();
    await loadModelOptions();
    if (api.hasToken?.()) {
      await loadAccount();
      await loadUserSettings();
      await loadResumeLibrary();
      await loadSessionHistory();
      await restoreLastSession();
      await loadStudyCenter();
    }
  }

  async function checkHealth() {
    setHealth({ status: "checking" });
    try {
      const result = await api.health();
      setHealth({ status: "ok", ...result });
    } catch (error) {
      setHealth({ status: "error", error: error.message });
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

  async function loadAccount() {
    try {
      const result = await api.getAccount();
      setAccount(result);
      applyUserSettings(result.settings);
    } catch (_error) {
      setAccount(null);
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

  function applyUserSettings(settings) {
    const mode = settings?.default_interview_mode;
    if (mode === "interviewer" || mode === "candidate") {
      setSettingsState((current) => ({ ...current, default_interview_mode: mode, status: "idle" }));
      setProfile((current) => ({ ...current, mode }));
    }
  }

  async function changeDefaultMode(mode) {
    if (mode !== "interviewer" && mode !== "candidate") return;
    setProfile((current) => ({ ...current, mode }));
    setSettingsState((current) => ({ ...current, default_interview_mode: mode, status: "saving", error: "" }));
    if (!account || !api.updateSettings) {
      setSettingsState((current) => ({ ...current, status: account ? "idle" : "error", error: account ? "" : "登录后才能同步设置。" }));
      return;
    }
    try {
      const result = await api.updateSettings({ default_interview_mode: mode });
      const savedMode = result?.default_interview_mode || mode;
      setSettingsState({ status: "saved", default_interview_mode: savedMode });
    } catch (error) {
      setSettingsState((current) => ({ ...current, status: "error", error: `设置保存失败：${normalizeDesktopError(error.message)}` }));
    }
  }

  async function submitAuth(event) {
    event?.preventDefault();
    if (authState.status === "loading") return;
    setAuthState((current) => ({ ...current, status: "loading", error: "" }));
    try {
      const payload = {
        email: authState.email,
        password: authState.password,
        display_name: authState.displayName || undefined,
        platform: "desktop"
      };
      if (authState.mode === "register") {
        await api.register(payload);
      } else {
        await api.login(payload);
      }
      await loadAccount();
      await loadUserSettings();
      await Promise.all([loadResumeLibrary(), loadSessionHistory()]);
      setAuthState((current) => ({ ...current, password: "", status: "success", error: "" }));
      setAuthDialog({ open: false, reason: "" });
    } catch (error) {
      setAuthState((current) => ({ ...current, status: "error", error: normalizeDesktopError(error.message) }));
    }
  }

  async function useDevAccount() {
    setAuthState((current) => ({ ...current, status: "loading", error: "" }));
    try {
      await api.devLogin({
        user_id: "desktop-dev-user",
        display_name: "桌面端开发用户",
        platform: "desktop"
      });
      await loadAccount();
      await loadUserSettings();
      await Promise.all([loadResumeLibrary(), loadSessionHistory()]);
      setAuthState((current) => ({ ...current, status: "success", error: "" }));
      setAuthDialog({ open: false, reason: "" });
    } catch (error) {
      setAuthState((current) => ({ ...current, status: "error", error: normalizeDesktopError(error.message) }));
    }
  }

  async function logout() {
    await api.logout();
    setLastSessionId("");
    setAccount(null);
    setSettingsState({ status: "idle", default_interview_mode: "interviewer" });
    setSessionId("");
    setMessages([]);
    setResumeLibrary([]);
    setSessionHistory([]);
    setScreen("chat");
  }

  async function loadResumeLibrary() {
    try {
      const resumes = await api.listResumes();
      setResumeLibrary(Array.isArray(resumes) ? resumes : []);
      if (!selectedResumeId && Array.isArray(resumes) && resumes.length > 0) {
        applyResume(resumes[0]);
      }
    } catch (error) {
      setResumeLibrary([]);
      setResumeImport({
        status: "error",
        error: `历史简历暂未加载：${normalizeDesktopError(error.message)}`
      });
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
      setResumeLibrary((current) => current.filter((resume) => resume.id !== selectedResumeId));
      setSelectedResumeId("");
      setProfile((current) => ({ ...current, resumeSummary: "", resumeText: "" }));
      setResumeImport({ status: "idle" });
      appendMessage("system", "当前简历已删除。");
    } catch (error) {
      setResumeImport({ status: "error", error: `删除简历失败：${normalizeDesktopError(error.message)}` });
    }
  }

  async function loadSessionHistory() {
    try {
      const sessions = await api.listSessions();
      setSessionHistory(Array.isArray(sessions) ? sessions : []);
      setHistoryState({ status: "idle" });
    } catch (error) {
      setSessionHistory([]);
      setHistoryState({ status: "error", error: `历史会话暂未加载：${normalizeDesktopError(error.message)}` });
    }
  }

  async function loadStudyCenter() {
    const getLearningPlan = api.getPracticeLearningPlan || api.getCivilServiceLearningPlan;
    const listQuestions = api.listPracticeQuestions || api.listCivilServiceQuestions;
    if (!getLearningPlan || !listQuestions) return;
    try {
      setStudyState((current) => ({ ...current, status: "loading", error: "" }));
      const [plan, questions] = await Promise.all([
        getLearningPlan(),
        listQuestions({
          category: studyFilters.category,
          year: studyFilters.year.trim(),
          subject: studyFilters.subject,
          questionType: studyFilters.questionType.trim(),
          limit: 30,
          offset: 0
        })
      ]);
      setStudyState((current) => ({
        ...current,
        status: "idle",
        plan: Array.isArray(plan) ? plan : [],
        questions: questions || { items: [], total: 0, limit: 30, offset: 0 }
      }));
    } catch (error) {
      setStudyState((current) => ({ ...current, status: "error", error: `学习数据加载失败：${normalizeDesktopError(error.message)}` }));
    }
  }

  function updateStudyFilters(patch) {
    setStudyFilters((current) => ({ ...current, ...patch }));
  }

  async function seedPracticeQuestions() {
    if (!requireAccount("初始化练习样题前需要先登录账号。")) return;
    const seedQuestions = api.seedPracticeQuestions || api.seedCivilServiceQuestions;
    if (!seedQuestions) return;
    try {
      setStudyState((current) => ({ ...current, status: "loading", error: "", seedMessage: "" }));
      const result = await seedQuestions();
      setStudyState((current) => ({
        ...current,
        status: "idle",
        seedMessage: `题库已初始化：新增 ${result.created}，更新 ${result.updated}。`
      }));
      await loadStudyCenter();
    } catch (error) {
      setStudyState((current) => ({ ...current, status: "error", error: `初始化样题失败：${normalizeDesktopError(error.message)}` }));
    }
  }

  async function importPracticeQuestionBank() {
    if (!requireAccount("上传题库前需要先登录账号。")) return;
    const importQuestionBank = api.importPracticeQuestionBank || api.importCivilServiceQuestionBank;
    if (!importQuestionBank) return;
    try {
      setStudyState((current) => ({ ...current, status: "loading", error: "", importMessage: "", seedMessage: "" }));
      const result = await importQuestionBank();
      if (result?.canceled) {
        setStudyState((current) => ({ ...current, status: "idle" }));
        return;
      }
      setStudyState((current) => ({
        ...current,
        status: "idle",
        importMessage: `题库已上传：新增 ${result.created}，更新 ${result.updated}。`
      }));
      await loadStudyCenter();
    } catch (error) {
      setStudyState((current) => ({ ...current, status: "error", error: `上传题库失败：${normalizeDesktopError(error.message)}` }));
    }
  }

  async function restoreSession(targetSessionId) {
    if (!targetSessionId || busy) return;
    if (!requireAccount("恢复历史会话前需要先登录账号。")) return;
    setBusy(true);
    try {
      const detail = await restoreSessionById(targetSessionId);
      setHistoryState({ status: "success", message: `已恢复会话 ${detail.id.slice(0, 8)}` });
    } catch (error) {
      setHistoryState({ status: "error", error: `恢复会话失败：${normalizeDesktopError(error.message)}` });
    } finally {
      setBusy(false);
    }
  }

  async function restoreLastSession() {
    const lastSessionId = getLastSessionId();
    if (!lastSessionId) return;
    const cachedMessages = getCachedSessionMessages(lastSessionId);
    if (cachedMessages.length) {
      setSessionId(lastSessionId);
      setMessages(cachedMessages);
    }
    try {
      await restoreSessionById(lastSessionId);
    } catch (_error) {
      setLastSessionId("");
    }
  }

  async function restoreSessionById(targetSessionId) {
    const detail = await api.getSession(targetSessionId);
    const restoredMessages = turnsToMessages(detail.turns || [], detail.mode);
    const cachedMessages = getCachedSessionMessages(detail.id);
    setSessionId(detail.id);
    setLastSessionId(detail.id);
    setCompleted(detail.status === "completed");
    setMessages(shouldUseCachedMessages(cachedMessages, restoredMessages) ? cachedMessages : restoredMessages);
    return detail;
  }

  async function deleteSession(targetSessionId) {
    if (!targetSessionId || busy) return;
    if (!requireAccount("管理历史会话前需要先登录账号。")) return;
    try {
      const result = await api.deleteSession(targetSessionId);
      if (result.deleted) {
        setSessionHistory((current) => current.filter((item) => item.id !== targetSessionId));
        if (sessionId === targetSessionId) {
          setLastSessionId("");
          setCachedSessionMessages(targetSessionId, []);
          setSessionId("");
          setMessages([]);
          setCompleted(false);
        }
        setHistoryState({ status: "success", message: "历史会话已删除。" });
      }
    } catch (error) {
      setHistoryState({ status: "error", error: `删除会话失败：${normalizeDesktopError(error.message)}` });
    }
  }

  async function createSession(seedMessage = "") {
    if (busy) return;
    if (!requireAccount("开始面试前需要先登录账号。登录后会保存会话、简历和用量记录。")) return;
    setBusy(true);
    setCompleted(false);
    setMessages([]);
    try {
      const response = await api.createSession({
        offline,
        web_search: webSearch,
        mode: profile.mode,
        industry: profile.industry,
        candidate_name: profile.candidateName,
        target_role: profile.targetRole,
        seniority: profile.seniority,
        resume_summary: profile.resumeSummary,
        resume_text: profile.resumeText,
        project_experience: profile.projectExperience,
        interview_goal: buildInterviewGoal(profile, seedMessage),
        focus_areas: buildFocusAreas(profile, seedMessage, industryOptions),
        resume_id: selectedResumeId || undefined,
        model_id: selectedModelId,
        thinking_enabled: currentLlmMode()?.thinkingEnabled,
        reasoning_effort: currentLlmMode()?.reasoningEffort
      });
      setSessionId(response.session_id);
      setLastSessionId(response.session_id);
      appendMessage("agent", response.message, response);
      await loadAccount();
      loadSessionHistory();
      if (seedMessage) {
        appendMessage("system", `启动意图：${seedMessage}`);
      }
    } catch (error) {
      appendMessage("system", `创建会话失败：${error.message}`);
    } finally {
      setBusy(false);
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
        return [result, ...withoutDuplicate];
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

  async function sendMessage(explicitText, explicitSessionId) {
    const text = (explicitText ?? input).trim();
    const activeSessionId = explicitSessionId || sessionId;
    if (!text || busy) return;
    if (!requireAccount("发送消息前需要先登录账号。")) return;
    if (!activeSessionId) {
      appendMessage("system", "请先点击“新建面试”。");
      return;
    }

    setInput("");
    const userTurnIndex = nextUserTurnIndex(messages);
    appendMessage("user", text, { turn_index: userTurnIndex });
    const agentMessageId = appendMessage("agent", "正在分析回答，DeepSeek 思考中...");
    const controller = new AbortController();
    activeRequestRef.current = controller;
    setBusy(true);
    try {
      const response = await sendMessageWithStreamFallback(activeSessionId, text, agentMessageId, controller.signal);
      updateMessage(agentMessageId, {
        text: response.message || response.data?.message || "",
        fallback: Boolean(response.fallback_used),
        usage: response.usage || null,
        modelId: response.model_id || "",
        turnIndex: response.turn_index || null
      });
      setCompleted(Boolean(response.completed));
      await refreshSessionMessagesFromServer(activeSessionId);
      await loadAccount();
      loadSessionHistory();
    } catch (error) {
      if (isAbortError(error)) {
        updateMessage(agentMessageId, {
          text: "已停止生成。你可以重新编辑上一条消息后再发送。",
          stopped: true
        });
        return;
      }
      appendMessage("system", `发送失败：${error.message}`);
    } finally {
      if (activeRequestRef.current === controller) {
        activeRequestRef.current = null;
      }
      setBusy(false);
    }
  }

  async function sendMessageWithStreamFallback(activeSessionId, text, agentMessageId, signal) {
    if (!api.streamMessage) {
      return api.sendMessage({
        sessionId: activeSessionId,
        message: text,
        signal
      });
    }
    let streamedText = "";
    try {
      return await api.streamMessage(
        {
          sessionId: activeSessionId,
          message: text,
          signal
        },
        (event) => {
          if (event.event === "tool.notice" && event.data?.message) {
            if (!streamedText) {
              updateMessage(agentMessageId, { text: event.data.message });
            }
          }
          if (event.event === "message.delta" && event.data?.text) {
            streamedText += event.data.text;
            updateMessage(agentMessageId, { text: streamedText });
          }
          if (event.event === "guardrail.notice" && event.data?.message) {
            appendMessage("system", `Harness 护栏：${event.data.message}`);
          }
          if (event.event === "message.done") {
            updateMessage(agentMessageId, {
              text: event.data?.message || "",
              fallback: Boolean(event.data?.fallback_used),
              usage: event.data?.usage || null,
              modelId: event.data?.model_id || "",
              turnIndex: event.data?.turn_index || null
            });
          }
        }
      );
    } catch (error) {
      if (isAbortError(error)) {
        throw error;
      }
      const message = normalizeDesktopError(error.message);
      if (!message.includes("无法连接 API 服务") && !message.includes("请求处理时间较长")) {
        throw error;
      }
      updateMessage(agentMessageId, { text: "流式连接中断，正在使用普通请求重试..." });
      try {
        return await api.sendMessage({
          sessionId: activeSessionId,
          message: text,
          signal
        });
      } catch (fallbackError) {
        const fallbackMessage = normalizeDesktopError(fallbackError.message);
        if (fallbackMessage.includes("无法连接 API 服务")) {
          throw new Error("无法连接 API 服务：/api 同源代理不可用或连接被关闭。请检查 Nginx /api 代理、HTTPS 长连接和后端服务状态。");
        }
        throw fallbackError;
      }
    }
  }

  async function refreshSessionMessagesFromServer(targetSessionId) {
    if (!targetSessionId) return;
    try {
      const detail = await api.getSession(targetSessionId);
      const restoredMessages = turnsToMessages(detail.turns || [], detail.mode);
      setSessionId(detail.id);
      setLastSessionId(detail.id);
      setCompleted(detail.status === "completed");
      setMessages(restoredMessages);
      setCachedSessionMessages(detail.id, restoredMessages);
    } catch (_error) {
      // The optimistic message already rendered; leave it in place if a read-back fails.
    }
  }

  async function createPayment(provider, amountCredits = paymentState.amount) {
    if (!requireAccount("充值积分前需要先登录账号。")) return;
    setPaymentState({ status: "loading", provider, amount: amountCredits });
    try {
      const order = await api.createPaymentOrder({
        amount_credits: amountCredits,
        payment_provider: provider,
        metadata: { source: "web_account_center" }
      });
      setPaymentState({ status: "pending", provider, amount: amountCredits, order });
      if (provider === "alipay" && order.pay_url) {
        window.open(order.pay_url, "_blank", "noopener,noreferrer");
      }
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

  function appendMessage(role, text, response = {}) {
    const id = crypto.randomUUID();
    const guardrails =
      role === "agent" && response.guardrails?.length
        ? [{ role: "system", text: `Harness 护栏：${response.guardrails.join("；")}` }]
        : [];
    setMessages((current) => [
      ...current,
      {
        id,
        role,
        text,
        fallback: Boolean(response.fallback_used),
        usage: response.usage || null,
        modelId: response.model_id || "",
        turnIndex: response.turn_index || response.turnIndex || null,
        stopped: Boolean(response.stopped),
        time: formatTime()
      },
      ...guardrails.map((item) => ({
        id: crypto.randomUUID(),
        time: formatTime(),
        fallback: false,
        ...item
      }))
    ]);
    return id;
  }

  function updateMessage(id, patch) {
    setMessages((current) =>
      current.map((message) => (message.id === id ? { ...message, ...patch } : message))
    );
  }

  function maxTurnIndexFromMessages(sourceMessages = messages) {
    return sourceMessages.reduce((max, message) => {
      const value = Number(message.turnIndex || 0);
      return Number.isFinite(value) ? Math.max(max, value) : max;
    }, 0);
  }

  function nextUserTurnIndex(sourceMessages = messages) {
    if (profile.mode === "candidate") {
      return maxTurnIndexFromMessages(sourceMessages) + 1;
    }
    const activeQuestion = [...sourceMessages]
      .reverse()
      .find((message) => message.role === "agent" && Number(message.turnIndex || 0) > 0);
    return Number(activeQuestion?.turnIndex || 0) || Math.max(1, maxTurnIndexFromMessages(sourceMessages));
  }

  function stopGeneration() {
    activeRequestRef.current?.abort();
  }

  function isAbortError(error) {
    return error?.name === "AbortError" || normalizeDesktopError(error?.message || "").includes("请求已停止");
  }

  async function withdrawMessage(message) {
    await rewindFromUserMessage(message, { edit: false });
  }

  async function editMessage(message) {
    await rewindFromUserMessage(message, { edit: true });
  }

  async function rewindFromUserMessage(message, { edit }) {
    if (busy || !message || message.role !== "user") return;
    const index = messages.findIndex((item) => item.id === message.id);
    if (index < 0) return;
    const nextMessages = messages.slice(0, index);
    setMessages(nextMessages);
    setCachedSessionMessages(sessionId, nextMessages);
    setCompleted(false);
    if (edit) {
      setInput(message.text || "");
      window.setTimeout(() => textareaRef.current?.focus(), 0);
    }
    if (!sessionId || !message.turnIndex || !api.rewindSession) return;
    try {
      await api.rewindSession(sessionId, { turn_index: message.turnIndex });
      await loadSessionHistory();
    } catch (error) {
      appendMessage("system", `会话已在本地回退，但服务端同步失败：${normalizeDesktopError(error.message)}`);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    sendMessage();
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  function requireAccount(reason) {
    if (account) return true;
    setAuthDialog({ open: true, reason });
    return false;
  }

  function currentLlmMode() {
    return llmModes.find((mode) => mode.value === selectedLlmMode) || llmModes[1];
  }

  function selectLlmMode(value) {
    const mode = llmModes.find((item) => item.value === value) || llmModes[1];
    setSelectedLlmMode(mode.value);
    setSelectedModelId(mode.modelId);
  }

  return (
    <main className="app-shell">
      <Sidebar
        screen={screen}
        profile={profile}
        account={account}
        sessionHistory={sessionHistory}
        historyState={historyState}
        activeSessionId={sessionId}
        busy={busy}
        onNewSession={() => createSession()}
        onReloadSessions={loadSessionHistory}
        onRestoreSession={restoreSession}
        onDeleteSession={deleteSession}
        onScreenChange={setScreen}
      />

      <section className="workspace">
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
          onOpenAccount={() => setScreen("account")}
          onOpenChat={() => setScreen("chat")}
        />

        {screen === "account" ? (
          <AccountCenter
            account={account}
            authState={authState}
            modelOptions={modelOptions}
            selectedModelId={selectedModelId}
            onAuthChange={setAuthState}
            onAuthSubmit={submitAuth}
            onDevLogin={useDevAccount}
            onLogout={logout}
            onSelectModel={setSelectedModelId}
            paymentState={paymentState}
            onPaymentStateChange={setPaymentState}
            onCreatePayment={createPayment}
            onBack={() => setScreen("chat")}
          />
        ) : screen === "settings" ? (
          <SettingsCenter
            account={account}
            profile={profile}
            settingsState={settingsState}
            onModeChange={changeDefaultMode}
            onBack={() => setScreen("chat")}
          />
        ) : screen === "setup" ? (
          <SetupCenter
            profile={profile}
            offline={offline}
            webSearch={webSearch}
            modelOptions={modelOptions}
            selectedModelId={selectedModelId}
            selectedLlmMode={selectedLlmMode}
            industryOptions={industryOptions}
            resumeImport={resumeImport}
            requirementsImport={requirementsImport}
            resumeLibrary={resumeLibrary}
            selectedResumeId={selectedResumeId}
            busy={busy}
            onNewSession={() => createSession()}
            onImportResume={importResume}
            onImportRequirements={importInterviewerRequirements}
            onSelectResume={selectResume}
            onDeleteResume={deleteSelectedResume}
            onReloadResumes={loadResumeLibrary}
            onProfileChange={setProfile}
            onDefaultModeChange={changeDefaultMode}
            onOfflineChange={setOffline}
            onWebSearchChange={setWebSearch}
            onSelectModel={setSelectedModelId}
            onSelectLlmMode={selectLlmMode}
            onBack={() => setScreen("chat")}
          />
        ) : screen === "study" ? (
          <StudyCenter
            studyState={studyState}
            studyFilters={studyFilters}
            onFilterChange={updateStudyFilters}
            onReload={loadStudyCenter}
            onSeed={seedPracticeQuestions}
            onImportQuestions={importPracticeQuestionBank}
            onBack={() => setScreen("chat")}
          />
        ) : (
          <section className="chat-panel">
            <div className="messages">
              {messages.length === 0 ? (
                <EmptyState
                  busy={busy}
                  mode={profile.mode}
                  industry={currentIndustry(industryOptions, profile.industry)}
                  onStart={() => createSession()}
                  onQuickPrompt={(prompt) => createSession(prompt)}
                />
              ) : (
                messages.map((message) => (
                  <Message
                    key={message.id}
                    message={message}
                    mode={profile.mode}
                    busy={busy}
                    onEditMessage={editMessage}
                    onWithdrawMessage={withdrawMessage}
                  />
                ))
              )}
              {busy && <Typing />}
              <div ref={messagesEndRef} />
            </div>

            <Composer
              value={input}
              busy={busy}
              hasSession={Boolean(sessionId)}
              textareaRef={textareaRef}
              onChange={setInput}
              onSubmit={handleSubmit}
              onKeyDown={handleKeyDown}
              onStop={stopGeneration}
              mode={profile.mode}
            />
          </section>
        )}

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
