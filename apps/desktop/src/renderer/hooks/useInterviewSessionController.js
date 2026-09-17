import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  buildFocusAreas,
  buildInterviewGoal,
  formatTime,
  normalizeDesktopError,
  turnsToMessages
} from "../utils/interview";
import { mergeUniqueById } from "./useInfiniteScroll";

const LAST_SESSION_STORAGE_PREFIX = "interview-agent-last-session-id:";
const SESSION_MESSAGES_STORAGE_PREFIX = "interview-agent-session-messages:";

function getLastSessionId(accountKey) {
  if (!accountKey) return "";
  try {
    return window.localStorage.getItem(`${LAST_SESSION_STORAGE_PREFIX}${accountKey}`) || "";
  } catch {
    return "";
  }
}

function setLastSessionId(accountKey, value) {
  if (!accountKey) return;
  try {
    const key = `${LAST_SESSION_STORAGE_PREFIX}${accountKey}`;
    if (value) window.localStorage.setItem(key, value);
    else window.localStorage.removeItem(key);
  } catch {
    // Private browsing and hardened environments may reject storage writes.
  }
}

function getCachedSessionMessages(accountKey, sessionId) {
  if (!accountKey || !sessionId) return [];
  try {
    const raw = window.localStorage.getItem(`${SESSION_MESSAGES_STORAGE_PREFIX}${accountKey}:${sessionId}`);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function setCachedSessionMessages(accountKey, sessionId, value) {
  if (!accountKey || !sessionId) return;
  try {
    if (!Array.isArray(value) || value.length === 0) {
      window.localStorage.removeItem(`${SESSION_MESSAGES_STORAGE_PREFIX}${accountKey}:${sessionId}`);
      return;
    }
    window.localStorage.setItem(
      `${SESSION_MESSAGES_STORAGE_PREFIX}${accountKey}:${sessionId}`,
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
  } catch {
    // The server remains authoritative when local caching is unavailable.
  }
}

function shouldUseCachedMessages(cachedMessages, restoredMessages) {
  if (!cachedMessages.length || restoredMessages.length > cachedMessages.length) return false;
  return !cachedMessages.some((message) => (
    message.role === "agent"
    && ["正在分析回答", "流式连接中断", "正在使用普通请求重试"]
      .some((fragment) => String(message.text || "").includes(fragment))
  ));
}

export function useInterviewSessionController({
  api,
  profile,
  industryOptions,
  selectedResumeId,
  selectedModelId,
  llmMode,
  accountKey,
  requireAccount,
  loadAccount
}) {
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [offline, setOffline] = useState(false);
  const [webSearch, setWebSearch] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [sessionHistory, setSessionHistory] = useState([]);
  const [historyState, setHistoryState] = useState({ status: "idle" });
  const [reportScores, setReportScores] = useState({});
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const activeRequestRef = useRef(null);
  const historyLoadingRef = useRef(false);
  const sessionHistoryRef = useRef([]);
  const accountKeyRef = useRef(accountKey);

  useLayoutEffect(() => {
    if (accountKeyRef.current === accountKey) return;
    activeRequestRef.current?.abort();
    accountKeyRef.current = accountKey;
    setSessionId("");
    setMessages([]);
    setInput("");
    setBusy(false);
    setCompleted(false);
    setSessionHistory([]);
    sessionHistoryRef.current = [];
    setHistoryState({ status: "idle" });
    setReportScores({});
  }, [accountKey]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  useEffect(() => {
    if (accountKey && sessionId && messages.length) setCachedSessionMessages(accountKey, sessionId, messages);
  }, [accountKey, sessionId, messages]);

  useEffect(() => () => activeRequestRef.current?.abort(), []);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 168)}px`;
  }, [input]);

  async function loadSessionHistory({ append = false } = {}) {
    if (historyLoadingRef.current) return;
    historyLoadingRef.current = true;
    setHistoryState((state) => ({ ...state, status: append ? "loading-more" : "loading" }));
    try {
      const sessions = await api.listSessions({ limit: 20, offset: append ? sessionHistoryRef.current.length : 0 });
      const incoming = Array.isArray(sessions) ? sessions : [];
      setSessionHistory((current) => {
        const next = append ? mergeUniqueById(current, incoming) : incoming;
        sessionHistoryRef.current = next;
        return next;
      });
      setHistoryState({ status: "idle", hasMore: incoming.length === 20 });
    } catch (error) {
      if (!append) {
        sessionHistoryRef.current = [];
        setSessionHistory([]);
      }
      setHistoryState({ status: "error", hasMore: append, error: `历史会话暂未加载：${normalizeDesktopError(error.message)}` });
    } finally {
      historyLoadingRef.current = false;
    }
  }

  async function loadReportScores() {
    try {
      const result = await api.study?.listReports?.(50);
      const reports = Array.isArray(result?.reports) ? result.reports : [];
      const scoreMap = {};
      for (const report of reports) {
        if (report.session_id && typeof report.total_score === "number") {
          scoreMap[report.session_id] = report.total_score;
        }
      }
      setReportScores(scoreMap);
    } catch {
      setReportScores({});
    }
  }

  async function restoreSessionById(targetSessionId, storageAccountKey = accountKey) {
    const detail = await api.getSession(targetSessionId);
    const restoredMessages = turnsToMessages(detail.turns || [], detail.mode);
    const cachedMessages = getCachedSessionMessages(storageAccountKey, detail.id);
    setSessionId(detail.id);
    setLastSessionId(storageAccountKey, detail.id);
    setCompleted(detail.status === "completed");
    setMessages(shouldUseCachedMessages(cachedMessages, restoredMessages) ? cachedMessages : restoredMessages);
    return detail;
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

  async function restoreLastSession(storageAccountKey = accountKey) {
    const lastSessionId = getLastSessionId(storageAccountKey);
    if (!lastSessionId) return;
    const cachedMessages = getCachedSessionMessages(storageAccountKey, lastSessionId);
    if (cachedMessages.length) {
      setSessionId(lastSessionId);
      setMessages(cachedMessages);
    }
    try {
      await restoreSessionById(lastSessionId, storageAccountKey);
    } catch {
      setLastSessionId(storageAccountKey, "");
      setSessionId("");
      setMessages([]);
      setCompleted(false);
    }
  }

  async function deleteSession(targetSessionId) {
    if (!targetSessionId || busy) return;
    if (!requireAccount("管理历史会话前需要先登录账号。")) return;
    try {
      const result = await api.deleteSession(targetSessionId);
      if (!result.deleted) return;
      setSessionHistory((current) => current.filter((item) => item.id !== targetSessionId));
      if (sessionId === targetSessionId) resetActiveSession(targetSessionId);
      setHistoryState({ status: "success", message: "历史会话已删除。" });
    } catch (error) {
      setHistoryState({ status: "error", error: `删除会话失败：${normalizeDesktopError(error.message)}` });
    }
  }

  async function createSession(seedMessage = "", extraPayload = {}) {
    if (busy || !requireAccount("开始面试前需要先登录账号。登录后会保存会话、简历和用量记录。")) return;
    setBusy(true);
    setCompleted(false);
    setMessages([]);
    try {
      const response = await api.createSession({
        offline,
        web_search: webSearch,
        mode: extraPayload.mode || profile.mode,
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
        thinking_enabled: llmMode?.thinkingEnabled,
        reasoning_effort: llmMode?.reasoningEffort,
        ...extraPayload
      });
      setSessionId(response.session_id);
      setLastSessionId(accountKey, response.session_id);
      appendMessage("agent", response.message, response);
      await loadAccount();
      loadSessionHistory();
      if (seedMessage) appendMessage("system", `启动意图：${seedMessage}`);
    } catch (error) {
      appendMessage("system", `创建会话失败：${normalizeDesktopError(error.message)}`);
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage(explicitText, explicitSessionId) {
    const text = (explicitText ?? input).trim();
    const activeSessionId = explicitSessionId || sessionId;
    if (!text || busy || !requireAccount("发送消息前需要先登录账号。")) return;
    if (!activeSessionId) {
      appendMessage("system", "请先点击“新建面试”。");
      return;
    }
    setInput("");
    appendMessage("user", text, { turn_index: nextUserTurnIndex(messages) });
    const agentMessageId = appendMessage("agent", "正在分析你的回答...");
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
      if (response.completed) loadReportScores();
    } catch (error) {
      if (isAbortError(error)) {
        updateMessage(agentMessageId, { text: "已停止生成。你可以重新编辑上一条消息后再发送。", stopped: true });
      } else {
        appendMessage("system", `发送失败：${normalizeDesktopError(error.message)}`);
      }
    } finally {
      if (activeRequestRef.current === controller) activeRequestRef.current = null;
      setBusy(false);
    }
  }

  async function sendMessageWithStreamFallback(activeSessionId, text, agentMessageId, signal) {
    if (!api.streamMessage) return api.sendMessage({ sessionId: activeSessionId, message: text, signal });
    let streamedText = "";
    try {
      return await api.streamMessage({ sessionId: activeSessionId, message: text, signal }, (event) => {
        if (event.event === "tool.notice" && event.data?.message && !streamedText) {
          updateMessage(agentMessageId, { text: event.data.message });
        }
        if (event.event === "message.delta" && event.data?.text) {
          streamedText += event.data.text;
          updateMessage(agentMessageId, { text: streamedText });
        }
        if (event.event === "guardrail.notice" && event.data?.message) {
          appendMessage("system", `内容提示：${event.data.message}`);
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
      });
    } catch (error) {
      if (isAbortError(error)) throw error;
      if (!isRetryableConnectionError(error)) throw error;
      updateMessage(agentMessageId, { text: "连接短暂中断，正在重新尝试..." });
      try {
        return await api.sendMessage({ sessionId: activeSessionId, message: text, signal });
      } catch (fallbackError) {
        if (isRetryableConnectionError(fallbackError)) {
          throw new Error("暂时无法连接服务，请检查网络后重试。");
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
      setLastSessionId(accountKey, detail.id);
      setCompleted(detail.status === "completed");
      setMessages(restoredMessages);
      setCachedSessionMessages(accountKey, detail.id, restoredMessages);
    } catch {
      // Keep optimistic messages when server read-back is temporarily unavailable.
    }
  }

  function appendMessage(role, text, response = {}) {
    const id = crypto.randomUUID();
    const guardrails = role === "agent" && response.guardrails?.length
      ? response.guardrails.map((message) => ({ role: "system", text: `内容提示：${message}` }))
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
      ...guardrails.map((item) => ({ id: crypto.randomUUID(), time: formatTime(), fallback: false, ...item }))
    ]);
    return id;
  }

  function updateMessage(id, patch) {
    setMessages((current) => current.map((message) => (message.id === id ? { ...message, ...patch } : message)));
  }

  function nextUserTurnIndex(sourceMessages) {
    const maxTurn = sourceMessages.reduce((max, message) => {
      const value = Number(message.turnIndex || 0);
      return Number.isFinite(value) ? Math.max(max, value) : max;
    }, 0);
    if (profile.mode === "candidate") return maxTurn + 1;
    const activeQuestion = [...sourceMessages]
      .reverse()
      .find((message) => message.role === "agent" && Number(message.turnIndex || 0) > 0);
    return Number(activeQuestion?.turnIndex || 0) || Math.max(1, maxTurn);
  }

  function isAbortError(error) {
    return error?.name === "AbortError" || normalizeDesktopError(error?.message || "").includes("请求已停止");
  }

  function isRetryableConnectionError(error) {
    return /无法连接|fetch|network|ECONN|超时|timeout|连接.*(?:中断|关闭)/iu.test(String(error?.message || ""));
  }

  async function rewindFromUserMessage(message, { edit }) {
    if (busy || !message || message.role !== "user") return;
    const index = messages.findIndex((item) => item.id === message.id);
    if (index < 0) return;
    const nextMessages = messages.slice(0, index);
    setMessages(nextMessages);
    setCachedSessionMessages(accountKey, sessionId, nextMessages);
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

  function resetActiveSession(targetSessionId = sessionId) {
    setLastSessionId(accountKey, "");
    setCachedSessionMessages(accountKey, targetSessionId, []);
    setSessionId("");
    setMessages([]);
    setCompleted(false);
  }

  function resetAll() {
    activeRequestRef.current?.abort();
    resetActiveSession();
    setInput("");
    setBusy(false);
    setSessionHistory([]);
    setReportScores({});
    setHistoryState({ status: "idle" });
  }

  function switchAccountScope(nextAccountKey) {
    accountKeyRef.current = nextAccountKey || "";
    resetAll();
  }

  return {
    appendMessage,
    busy,
    completed,
    deleteSession,
    editMessage: (message) => rewindFromUserMessage(message, { edit: true }),
    handleKeyDown: (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
    },
    handleSubmit: (event) => {
      event.preventDefault();
      sendMessage();
    },
    historyState,
    input,
    loadReportScores,
    loadSessionHistory,
    messages,
    messagesEndRef,
    offline,
    reportScores,
    resetAll,
    restoreLastSession,
    restoreSession,
    sessionHistory,
    sessionId,
    setInput,
    setOffline,
    setWebSearch,
    startSession: createSession,
    stopGeneration: () => activeRequestRef.current?.abort(),
    switchAccountScope,
    textareaRef,
    webSearch,
    withdrawMessage: (message) => rewindFromUserMessage(message, { edit: false })
  };
}
