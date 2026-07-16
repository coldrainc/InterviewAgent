import { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { getInterviewAgentClient } from "./apiClient";
import { fallbackIndustries, fallbackModels, llmModes } from "./constants/interview";
import Sidebar from "./components/sidebar/Sidebar";
import { AccountCenter, AuthDialog } from "./components/account/AccountCenter";
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
  const [resumeLibrary, setResumeLibrary] = useState([]);
  const [selectedResumeId, setSelectedResumeId] = useState("");
  const [sessionHistory, setSessionHistory] = useState([]);
  const [historyState, setHistoryState] = useState({ status: "idle" });
  const [industryOptions, setIndustryOptions] = useState(fallbackIndustries);
  const [modelOptions, setModelOptions] = useState(fallbackModels);
  const [selectedModelId, setSelectedModelId] = useState("deepseek-v4-pro");
  const [selectedLlmMode, setSelectedLlmMode] = useState("standard");
  const [account, setAccount] = useState(null);
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
    interviewGoal: "请基于我的简历和做过的事情进行 AI 工程面试，重点深挖真实项目、RAG/Agent、评测、上线和安全治理。"
  });
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    bootstrap();
  }, []);

  useEffect(() => {
    loadIndustryOptions(profile.targetRole);
  }, [profile.targetRole]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

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
      await loadResumeLibrary();
      await loadSessionHistory();
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
    } catch (_error) {
      setAccount(null);
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
      await Promise.all([loadResumeLibrary(), loadSessionHistory()]);
      setAuthState((current) => ({ ...current, status: "success", error: "" }));
      setAuthDialog({ open: false, reason: "" });
    } catch (error) {
      setAuthState((current) => ({ ...current, status: "error", error: normalizeDesktopError(error.message) }));
    }
  }

  async function logout() {
    await api.logout();
    setAccount(null);
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

  async function restoreSession(targetSessionId) {
    if (!targetSessionId || busy) return;
    if (!requireAccount("恢复历史会话前需要先登录账号。")) return;
    setBusy(true);
    try {
      const detail = await api.getSession(targetSessionId);
      setSessionId(detail.id);
      setCompleted(detail.status === "completed");
      setMessages(turnsToMessages(detail.turns || []));
      setHistoryState({ status: "success", message: `已恢复会话 ${detail.id.slice(0, 8)}` });
    } catch (error) {
      setHistoryState({ status: "error", error: `恢复会话失败：${normalizeDesktopError(error.message)}` });
    } finally {
      setBusy(false);
    }
  }

  async function deleteSession(targetSessionId) {
    if (!targetSessionId || busy) return;
    if (!requireAccount("管理历史会话前需要先登录账号。")) return;
    try {
      const result = await api.deleteSession(targetSessionId);
      if (result.deleted) {
        setSessionHistory((current) => current.filter((item) => item.id !== targetSessionId));
        if (sessionId === targetSessionId) {
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
    appendMessage("user", text);
    const agentMessageId = appendMessage("agent", "正在分析回答，DeepSeek 思考中...");
    setBusy(true);
    try {
      const response = api.streamMessage
        ? await api.streamMessage(
            {
              sessionId: activeSessionId,
              message: text
            },
            (event) => {
              if (event.event === "tool.notice" && event.data?.message) {
                updateMessage(agentMessageId, { text: event.data.message });
              }
              if (event.event === "guardrail.notice" && event.data?.message) {
                appendMessage("system", `Harness 护栏：${event.data.message}`);
              }
              if (event.event === "message.done") {
                updateMessage(agentMessageId, {
                  text: event.data?.message || "",
                  fallback: Boolean(event.data?.fallback_used),
                  usage: event.data?.usage || null,
                  modelId: event.data?.model_id || ""
                });
              }
            }
          )
        : await api.sendMessage({
            sessionId: activeSessionId,
            message: text
          });
      updateMessage(agentMessageId, {
        text: response.message || response.data?.message || "",
        fallback: Boolean(response.fallback_used),
        usage: response.usage || null,
        modelId: response.model_id || ""
      });
      setCompleted(Boolean(response.completed));
      await loadAccount();
      loadSessionHistory();
    } catch (error) {
      appendMessage("system", `发送失败：${error.message}`);
    } finally {
      setBusy(false);
    }
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
        offline={offline}
        webSearch={webSearch}
        profile={profile}
        account={account}
        modelOptions={modelOptions}
        selectedModelId={selectedModelId}
        selectedLlmMode={selectedLlmMode}
        industryOptions={industryOptions}
        resumeImport={resumeImport}
        resumeLibrary={resumeLibrary}
        selectedResumeId={selectedResumeId}
        sessionHistory={sessionHistory}
        historyState={historyState}
        activeSessionId={sessionId}
        busy={busy}
        onNewSession={() => createSession()}
        onImportResume={importResume}
        onSelectResume={selectResume}
        onDeleteResume={deleteSelectedResume}
        onReloadResumes={loadResumeLibrary}
        onReloadSessions={loadSessionHistory}
        onRestoreSession={restoreSession}
        onDeleteSession={deleteSession}
        onScreenChange={setScreen}
        onOfflineChange={setOffline}
        onWebSearchChange={setWebSearch}
        onProfileChange={setProfile}
        onSelectModel={setSelectedModelId}
        onSelectLlmMode={selectLlmMode}
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
                messages.map((message) => <Message key={message.id} message={message} mode={profile.mode} />)
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
