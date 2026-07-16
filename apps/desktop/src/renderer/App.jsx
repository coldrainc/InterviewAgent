import { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Bot,
  BrainCircuit,
  CheckCircle2,
  Coins,
  Database,
  Globe2,
  Loader2,
  MessageSquarePlus,
  Moon,
  Settings,
  Trash2,
  Upload,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
  X
} from "lucide-react";
import "./styles.css";
import { getInterviewAgentClient } from "./apiClient";

const quickPrompts = [
  "请开始一场 AI Agent 项目面试",
  "我做过 RAG 知识库项目，请追问我生产化细节",
  "请围绕 LLMOps、评测和上线治理提问",
  "我想练习 Agent 工具调用和安全护栏"
];

const interviewModes = [
  { value: "interviewer", label: "Agent 面试我" },
  { value: "candidate", label: "Agent 回答我" }
];

const fallbackIndustries = [
  {
    value: "internet",
    label: "互联网行业",
    description: "面向高并发用户产品、内容/直播/社区/工具类业务。",
    production_signals: ["p95/p99 延迟", "QPS", "灰度通过率"],
    recommended_focus_areas: []
  }
];

const api = getInterviewAgentClient();

const fallbackModels = [
  {
    id: "gpt-5.5",
    provider: "openai",
    display_name: "OpenAI GPT-5.5",
    category: "默认通用",
    input_credits_per_1m: "500.00",
    output_credits_per_1m: "3000.00"
  },
  {
    id: "gpt-5.5-pro",
    provider: "openai",
    display_name: "OpenAI GPT-5.5 Pro",
    category: "最高质量",
    input_credits_per_1m: "3000.00",
    output_credits_per_1m: "18000.00"
  },
  {
    id: "gpt-5.4-mini",
    provider: "openai",
    display_name: "OpenAI GPT-5.4 mini",
    category: "高性价比",
    input_credits_per_1m: "75.00",
    output_credits_per_1m: "450.00"
  },
  {
    id: "claude-fable-5",
    provider: "anthropic",
    display_name: "Claude Fable 5",
    category: "长上下文深度分析",
    input_credits_per_1m: "1000.00",
    output_credits_per_1m: "5000.00"
  },
  {
    id: "gemini-3.5-flash",
    provider: "google",
    display_name: "Gemini 3.5 Flash",
    category: "多模态低延迟",
    input_credits_per_1m: "150.00",
    output_credits_per_1m: "900.00"
  },
  {
    id: "deepseek-v4-pro",
    provider: "deepseek",
    display_name: "DeepSeek V4 Pro",
    category: "高性价比推理",
    input_credits_per_1m: "44.00",
    output_credits_per_1m: "88.00"
  },
  {
    id: "qwen3.7-max",
    provider: "alibaba",
    display_name: "Qwen3.7 Max",
    category: "中文企业旗舰",
    input_credits_per_1m: "250.00",
    output_credits_per_1m: "750.00"
  },
  {
    id: "kimi-k2.7-code",
    provider: "moonshot",
    display_name: "Kimi K2.7 Code",
    category: "代码与 Agent",
    input_credits_per_1m: "100.00",
    output_credits_per_1m: "400.00"
  }
];

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
  const [selectedModelId, setSelectedModelId] = useState("gpt-5.5");
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
        model_id: selectedModelId
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
    setBusy(true);
    try {
      const response = await api.sendMessage({
        sessionId: activeSessionId,
        message: text
      });
      appendMessage("agent", response.message, response);
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
    const guardrails =
      role === "agent" && response.guardrails?.length
        ? [{ role: "system", text: `Harness 护栏：${response.guardrails.join("；")}` }]
        : [];
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
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

function Sidebar({
  screen,
  offline,
  webSearch,
  profile,
  account,
  modelOptions,
  selectedModelId,
  industryOptions,
  resumeImport,
  resumeLibrary,
  selectedResumeId,
  sessionHistory,
  historyState,
  activeSessionId,
  busy,
  onNewSession,
  onImportResume,
  onSelectResume,
  onDeleteResume,
  onReloadResumes,
  onReloadSessions,
  onRestoreSession,
  onDeleteSession,
  onScreenChange,
  onOfflineChange,
  onWebSearchChange,
  onProfileChange,
  onSelectModel
}) {
  const updateProfile = (key, value) => {
    onProfileChange((current) => ({ ...current, [key]: value }));
  };

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <BrainCircuit size={23} strokeWidth={2.2} />
        </div>
        <div>
          <h1>Interview Agent</h1>
          <p>AI 技术面试工作台</p>
        </div>
      </div>

      <button className="primary-action" onClick={onNewSession} disabled={busy}>
        <MessageSquarePlus size={18} />
        {profile.mode === "candidate" ? "开始被面试回答" : "基于简历新建面试"}
      </button>

      <AccountEntry
        account={account}
        active={screen === "account"}
        onOpen={() => onScreenChange("account")}
      />

      <section className="panel mode-panel">
        <div className="panel-heading">
          <span>模式与行业</span>
        </div>
        <SegmentedControl
          value={profile.mode}
          options={interviewModes}
          onChange={(value) => updateProfile("mode", value)}
        />
        <label className="select-field">
          <span>行业</span>
          <select value={profile.industry} onChange={(event) => updateProfile("industry", event.target.value)}>
            {industryOptions.map((industry) => (
              <option key={industry.value} value={industry.value}>
                {industry.label}
              </option>
            ))}
          </select>
        </label>
        <IndustryBrief industry={currentIndustry(industryOptions, profile.industry)} />
        <ModelSelector
          models={modelOptions}
          selectedModelId={selectedModelId}
          onSelectModel={onSelectModel}
        />
      </section>

      <section className="panel resume-panel">
        <div className="panel-heading">
          <span>简历与经历</span>
        </div>
        <button
          className="secondary-action"
          onClick={onImportResume}
          disabled={busy || resumeImport.status === "loading"}
        >
          {resumeImport.status === "loading" ? <Loader2 size={17} className="spin" /> : <Upload size={17} />}
          保存 PDF / Markdown 简历
        </button>
        <ResumeLibrary
          resumes={resumeLibrary}
          selectedResumeId={selectedResumeId}
          onSelect={onSelectResume}
          onReload={onReloadResumes}
          onDelete={onDeleteResume}
          busy={busy}
        />
        <ResumeImportStatus state={resumeImport} />
        <div className="field-grid two">
          <Field
            label="姓名"
            value={profile.candidateName}
            placeholder="例如：张三"
            onChange={(value) => updateProfile("candidateName", value)}
          />
          <Field
            label="级别"
            value={profile.seniority}
            placeholder="中级 / 高级"
            onChange={(value) => updateProfile("seniority", value)}
          />
        </div>
        <Field
          label="目标岗位"
          value={profile.targetRole}
          placeholder="AI 应用工程师 / Agent 工程师"
          onChange={(value) => updateProfile("targetRole", value)}
        />
        <Field
          textarea
          label="简历摘要"
          value={profile.resumeSummary}
          placeholder="粘贴 3-5 行简历摘要：岗位、年限、技术栈、代表项目..."
          onChange={(value) => updateProfile("resumeSummary", value)}
        />
        <Field
          textarea
          tall
          label="完整简历"
          value={profile.resumeText}
          placeholder="可粘贴完整简历，面试官会围绕其中的项目、职责和技术栈追问。"
          onChange={(value) => updateProfile("resumeText", value)}
        />
        <Field
          textarea
          tall
          label="做过的事情"
          value={profile.projectExperience}
          placeholder="写你真实做过的项目：背景、职责、架构、指标、难点、复盘。"
          onChange={(value) => updateProfile("projectExperience", value)}
        />
        <Field
          textarea
          label="面试目标"
          value={profile.interviewGoal}
          placeholder="希望面试官重点考察哪些方向？"
          onChange={(value) => updateProfile("interviewGoal", value)}
        />
      </section>

      <section className="panel history-panel">
        <div className="panel-heading">
          <span>历史会话</span>
          <button className="icon-button" onClick={onReloadSessions} aria-label="刷新历史会话">
            <RefreshCw size={15} />
          </button>
        </div>
        <SessionHistory
          sessions={sessionHistory}
          activeSessionId={activeSessionId}
          state={historyState}
          busy={busy}
          onRestore={onRestoreSession}
          onDelete={onDeleteSession}
        />
      </section>

      <section className="panel">
        <div className="panel-heading">
          <span>会话选项</span>
        </div>
        <Toggle
          icon={<Moon size={16} />}
          label="离线模式"
          checked={offline}
          onChange={onOfflineChange}
        />
        <Toggle
          icon={<Globe2 size={16} />}
          label="联网搜索"
          checked={webSearch}
          onChange={onWebSearchChange}
        />
      </section>

      <section className="panel compact">
        <div className="capability">
          <Search size={16} />
          <span>RAG 知识库自动检索</span>
        </div>
        <div className="capability">
          <ShieldCheck size={16} />
          <span>Harness 输入输出护栏</span>
        </div>
        <div className="capability">
          <Activity size={16} />
          <span>会话记录和记忆沉淀</span>
        </div>
      </section>
    </aside>
  );
}

function ResumeImportStatus({ state }) {
  if (!state || state.status === "idle") {
    return <p className="resume-hint">支持 .pdf、.md、.markdown，上传后会进入历史简历库。</p>;
  }
  if (state.status === "loading") {
    return <p className="resume-hint active">正在解析简历...</p>;
  }
  if (state.status === "error") {
    return <p className="resume-hint error">{state.error}</p>;
  }
  return (
    <p className="resume-hint success">
      当前使用 {state.filename}
      {state.truncated ? "，内容较长已截断" : ""}
    </p>
  );
}

function ResumeLibrary({ resumes, selectedResumeId, onSelect, onReload, onDelete, busy }) {
  const selectedResume = resumes.find((resume) => resume.id === selectedResumeId);
  const confirmDelete = () => {
    if (!selectedResume) return;
    const ok = window.confirm(`确认删除简历「${selectedResume.filename}」？原文件和解析记录都会删除。`);
    if (ok) onDelete();
  };
  return (
    <div className="resume-library">
      <div className="resume-library-head">
        <span>当前简历</span>
        <button type="button" onClick={onReload} aria-label="刷新简历列表">
          <RefreshCw size={13} />
        </button>
      </div>
      <select
        value={selectedResumeId}
        onChange={(event) => onSelect(event.target.value)}
        disabled={!resumes.length}
      >
        <option value="">{resumes.length ? "请选择简历" : "暂无历史简历"}</option>
        {resumes.map((resume) => (
          <option key={resume.id} value={resume.id}>
            {resume.filename}
          </option>
        ))}
      </select>
      {selectedResumeId && (
        <div className="resume-library-actions">
          <small>
            已保存 {resumes.length} 份，当前面试和被面试都会使用选中的这份简历。
          </small>
          <button type="button" className="danger-inline" onClick={confirmDelete} disabled={busy}>
            <Trash2 size={13} />
            删除
          </button>
        </div>
      )}
    </div>
  );
}

function SessionHistory({ sessions, activeSessionId, state, busy, onRestore, onDelete }) {
  if (state?.status === "error") {
    return <p className="resume-hint error">{state.error}</p>;
  }
  if (!sessions.length) {
    return <p className="resume-hint">暂无历史会话，开始一次面试后会自动保存。</p>;
  }
  return (
    <div className="history-list">
      {sessions.slice(0, 6).map((session) => (
        <div key={session.id} className={`history-item ${session.id === activeSessionId ? "active" : ""}`}>
          <button type="button" onClick={() => onRestore(session.id)} disabled={busy}>
            <strong>{session.target_role || "AI 面试"}</strong>
            <span>{session.mode === "candidate" ? "候选人回答" : "模拟面试"} · {formatDateTime(session.updated_at)}</span>
          </button>
          <button
            type="button"
            className="history-delete"
            onClick={() => {
              const ok = window.confirm("确认删除这段历史会话？");
              if (ok) onDelete(session.id);
            }}
            disabled={busy}
            aria-label="删除历史会话"
          >
            <Trash2 size={13} />
          </button>
        </div>
      ))}
      {state?.status === "success" && <p className="resume-hint success">{state.message}</p>}
    </div>
  );
}

function SegmentedControl({ value, options, onChange }) {
  return (
    <div className="segmented-control" role="tablist">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={value === option.value ? "active" : ""}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function Toggle({ icon, label, checked, onChange }) {
  return (
    <label className="toggle-row">
      <span className="toggle-label">
        {icon}
        {label}
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="toggle-track" aria-hidden="true">
        <span />
      </span>
    </label>
  );
}

function Field({ label, value, placeholder, textarea = false, tall = false, onChange }) {
  const Control = textarea ? "textarea" : "input";
  return (
    <label className={`field ${textarea ? "textarea-field" : ""} ${tall ? "tall" : ""}`}>
      <span>{label}</span>
      <Control
        value={value}
        placeholder={placeholder}
        rows={tall ? 5 : 3}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function IndustryBrief({ industry }) {
  if (!industry) return null;
  const signals = (industry.production_signals || []).slice(0, 3).join(" / ");
  return (
    <div className="industry-brief">
      <strong>{industry.label}</strong>
      <span>{industry.description}</span>
      {signals && <small>核心信号：{signals}</small>}
    </div>
  );
}

function AccountEntry({ account, active, onOpen }) {
  return (
    <button type="button" className={`account-entry ${active ? "active" : ""}`} onClick={onOpen}>
      <span className="account-entry-icon">
        <UserRound size={17} />
      </span>
      <span className="account-entry-main">
        <strong>{account ? account.display_name || account.user_id : "登录 / 注册"}</strong>
        <small>
          {account
            ? `${formatCredits(account.credit_balance)} 积分 · ${account.trial_uses_remaining} 次试用`
            : "账户、充值和个人信息"}
        </small>
      </span>
      <Settings size={15} />
    </button>
  );
}

function AccountCenter({
  account,
  authState,
  modelOptions,
  selectedModelId,
  onAuthChange,
  onAuthSubmit,
  onDevLogin,
  onLogout,
  onSelectModel,
  onBack
}) {
  if (account) {
    return (
      <section className="account-center">
        <div className="account-hero">
          <div className="account-avatar">
            <UserRound size={28} />
          </div>
          <div>
            <span className="eyebrow">Account</span>
            <h3>{account.display_name || account.user_id}</h3>
            <p>{account.email || account.user_id}</p>
          </div>
          <div className="account-hero-actions">
            <button type="button" className="secondary-action inline" onClick={onBack}>返回面试</button>
            <button type="button" className="danger-inline large" onClick={onLogout}>退出登录</button>
          </div>
        </div>

        <div className="account-grid">
          <section className="account-block">
            <div className="panel-heading">
              <span>额度</span>
            </div>
            <div className="credit-grid large">
              <div>
                <small>剩余试用</small>
                <b>{account.trial_uses_remaining}</b>
              </div>
              <div>
                <small>积分余额</small>
                <b>{formatCredits(account.credit_balance)}</b>
              </div>
            </div>
            <p className="resume-hint">生产环境充值会由支付平台创建订单，支付成功后通过服务端签名回调入账。</p>
          </section>

          <section className="account-block">
            <div className="panel-heading">
              <span>模型计费</span>
            </div>
            <ModelSelector
              models={modelOptions}
              selectedModelId={selectedModelId}
              onSelectModel={onSelectModel}
            />
            <div className="billing-note">
              <Coins size={15} />
              <span>试用额度优先消耗；试用用完后按模型 token 用量扣除积分。</span>
            </div>
          </section>

          <section className="account-block">
            <div className="panel-heading">
              <span>个人信息</span>
            </div>
            <div className="profile-list">
              <ProfileItem label="租户" value={account.tenant_id} />
              <ProfileItem label="用户 ID" value={account.user_id} />
              <ProfileItem label="平台" value={account.platform} />
              <ProfileItem label="邮箱" value={account.email || "-"} />
            </div>
          </section>

          <section className="account-block">
            <div className="panel-heading">
              <span>安全</span>
            </div>
            <div className="security-list">
              <div>
                <ShieldCheck size={16} />
                <span>桌面端 token 仅保存在当前 Electron 主进程内存中。</span>
              </div>
              <div>
                <Database size={16} />
                <span>简历、会话和用量记录按当前后端存储策略保存。</span>
              </div>
            </div>
          </section>
        </div>
      </section>
    );
  }

  return (
    <section className="account-center">
      <div className="account-auth-layout">
        <div className="account-auth-copy">
          <span className="eyebrow">Account</span>
          <h3>登录后继续使用 Interview Agent</h3>
          <p>账户用于保存简历、历史会话、试用额度、积分余额和模型用量。</p>
          <div className="auth-benefits">
            <div><CheckCircle2 size={16} />默认领取 2 次试用</div>
            <div><CheckCircle2 size={16} />多端共享简历和历史记录</div>
            <div><CheckCircle2 size={16} />按模型 token 用量扣除积分</div>
          </div>
        </div>
        <div className="auth-card standalone">
          <AuthForm
            authState={authState}
            onAuthChange={onAuthChange}
            onAuthSubmit={onAuthSubmit}
            onDevLogin={onDevLogin}
          />
        </div>
      </div>
    </section>
  );
}

function AuthDialog({ reason, authState, onAuthChange, onAuthSubmit, onDevLogin, onClose }) {
  return (
    <div className="auth-dialog-backdrop" role="presentation">
      <section className="auth-dialog" role="dialog" aria-modal="true" aria-label="登录">
        <div className="auth-dialog-head">
          <div>
            <span className="eyebrow">Sign in</span>
            <h3>需要先登录</h3>
            {reason && <p>{reason}</p>}
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭登录弹窗">
            <X size={14} />
          </button>
        </div>
        <AuthForm
          authState={authState}
          onAuthChange={onAuthChange}
          onAuthSubmit={onAuthSubmit}
          onDevLogin={onDevLogin}
        />
      </section>
    </div>
  );
}

function AuthForm({ authState, onAuthChange, onAuthSubmit, onDevLogin }) {
  const update = (key, value) => onAuthChange((current) => ({ ...current, [key]: value }));
  return (
    <>
      <div className="panel-heading">
        <span>账户</span>
        <button
          type="button"
          className="text-button"
          onClick={() => update("mode", authState.mode === "login" ? "register" : "login")}
        >
          {authState.mode === "login" ? "注册" : "登录"}
        </button>
      </div>
      <form className="auth-form" onSubmit={onAuthSubmit}>
        {authState.mode === "register" && (
          <input
            value={authState.displayName}
            placeholder="昵称"
            onChange={(event) => update("displayName", event.target.value)}
          />
        )}
        <input
          value={authState.email}
          placeholder="邮箱"
          onChange={(event) => update("email", event.target.value)}
        />
        <input
          type="password"
          value={authState.password}
          placeholder="密码"
          onChange={(event) => update("password", event.target.value)}
        />
        <button type="submit" disabled={authState.status === "loading"}>
          {authState.status === "loading" ? "处理中..." : authState.mode === "login" ? "登录" : "注册并领取试用"}
        </button>
        <button type="button" className="secondary-auth" onClick={onDevLogin}>
          开发账号试用
        </button>
        {authState.status === "error" && <p>{authState.error}</p>}
      </form>
    </>
  );
}

function ProfileItem({ label, value }) {
  return (
    <div className="profile-item">
      <span>{label}</span>
      <strong>{value || "-"}</strong>
    </div>
  );
}

function ModelSelector({ models, selectedModelId, onSelectModel }) {
  const model = currentModel(models, selectedModelId);
  return (
    <label className="select-field model-selector">
      <span>模型</span>
      <select value={selectedModelId} onChange={(event) => onSelectModel(event.target.value)}>
        {models.map((item) => (
          <option key={item.id} value={item.id}>
            {item.category ? `${item.category} · ` : ""}
            {item.display_name || item.id}
          </option>
        ))}
      </select>
      {model && (
        <small>
          {model.category ? `${model.category} · ` : ""}
          {model.provider} · 输入 {formatCredits(model.input_credits_per_1m)} / 百万 token · 输出{" "}
          {formatCredits(model.output_credits_per_1m)} / 百万 token
        </small>
      )}
    </label>
  );
}

function Topbar({ sessionId, offline, webSearch, completed, status, profile, model, account, screen, onOpenAccount, onOpenChat }) {
  const mode = completed ? "已完成" : offline ? "离线模式" : "模型模式";
  const title =
    screen === "account"
      ? "账户中心"
      : profile.mode === "candidate"
      ? `${profile.targetRole || "AI 工程师"}候选人答题`
      : profile.targetRole
        ? `${profile.targetRole}模拟面试`
        : "中文技术面试";
  return (
    <header className="topbar">
      <div>
        <div className="eyebrow">
          {profile.mode === "candidate" ? "Candidate Answer Mode" : "Resume Driven Interview"}
        </div>
        <h2>{title}</h2>
      </div>
      <div className="topbar-actions">
        {screen === "account" ? (
          <button type="button" className="topbar-button" onClick={onOpenChat}>
            <MessageSquarePlus size={14} />
            面试工作台
          </button>
        ) : (
          <button type="button" className="topbar-button" onClick={onOpenAccount}>
            <UserRound size={14} />
            {account ? "账户中心" : "登录"}
          </button>
        )}
        <span className={`status-chip ${status.tone}`}>{status.label}</span>
        {screen !== "account" && (
          <>
            <span className="session-chip">{sessionId ? `会话 ${sessionId.slice(0, 8)}` : "未开始"}</span>
            <span className="mode-chip">{profile.mode === "candidate" ? "Agent 候选人" : "Agent 面试官"}</span>
            <span className="mode-chip">{webSearch ? `${mode} · 联网` : mode}</span>
            <span className="mode-chip">{model?.display_name || "默认模型"}</span>
            {account && <span className="mode-chip"><Coins size={13} /> {formatCredits(account.credit_balance)} 积分</span>}
          </>
        )}
      </div>
    </header>
  );
}

function EmptyState({ busy, mode, industry, onStart, onQuickPrompt }) {
  const isCandidateMode = mode === "candidate";
  return (
    <div className="empty-state">
      <div className="empty-mark">
        <Sparkles size={28} />
      </div>
      <h3>{isCandidateMode ? "让 Agent 作为候选人回答你的面试题" : "粘贴简历后，开始一场真实项目面试"}</h3>
      <p>
        {isCandidateMode
          ? `你作为面试官提问，Agent 会结合简历、${industry?.label || "行业"}要求和 AI 知识库，用候选人口吻给出结构化回答。`
          : `面试官会结合你的简历、做过的事情、${industry?.label || "行业"}画像、AI 知识库和历史记忆，判断回答质量并决定继续深挖或切换方向。`}
      </p>
      <button className="empty-start" onClick={onStart} disabled={busy}>
        <MessageSquarePlus size={17} />
        {isCandidateMode ? "开始答题模式" : "开始面试"}
      </button>
      <div className="quick-grid">
        {quickPrompts.map((prompt) => (
          <button key={prompt} onClick={() => onQuickPrompt(prompt)} disabled={busy}>
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}

function Message({ message, mode }) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const userLabel = mode === "candidate" ? "面试官" : "候选人";
  const agentLabel = mode === "candidate" ? "候选人" : "面试官";
  return (
    <article className={`message-row ${message.role}`}>
      <div className="avatar" aria-hidden="true">
        {isUser ? <UserRound size={17} /> : isSystem ? <ShieldCheck size={17} /> : <Bot size={18} />}
      </div>
      <div className="message-stack">
        <div className="message-meta">
          <span>{isUser ? userLabel : isSystem ? "系统" : agentLabel}</span>
          <span>{message.time}</span>
          {message.fallback && <strong>降级回复</strong>}
        </div>
        <div className={`message-bubble ${message.role}`}>{message.text}</div>
        {message.usage && <UsageMeta usage={message.usage} modelId={message.modelId} />}
      </div>
    </article>
  );
}

function UsageMeta({ usage, modelId }) {
  return (
    <div className="usage-meta">
      <Coins size={13} />
      <span>
        {usage.trial_used
          ? `试用消耗，剩余 ${usage.trial_uses_remaining} 次`
          : `扣除 ${formatCredits(usage.cost_credits)} 积分`}
      </span>
      <span>{modelId || usage.model_id}</span>
      <span>{usage.total_tokens} tokens</span>
    </div>
  );
}

function Typing() {
  return (
    <div className="typing">
      <Loader2 size={16} className="spin" />
      面试官正在分析回答、检索知识库并生成追问...
    </div>
  );
}

function Composer({ value, busy, hasSession, textareaRef, onChange, onSubmit, onKeyDown, mode }) {
  const placeholder = hasSession
    ? mode === "candidate"
      ? "输入你的面试题或追问，按 Enter 发送，Shift + Enter 换行"
      : "输入你的回答，按 Enter 发送，Shift + Enter 换行"
    : mode === "candidate"
      ? "先开始被面试回答，然后输入面试题"
      : "先新建面试，然后输入你的回答";
  return (
    <form className="composer" onSubmit={onSubmit}>
      <textarea
        ref={textareaRef}
        rows={1}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
      />
      <button type="submit" disabled={busy || !value.trim()} aria-label="发送回答">
        {busy ? <Loader2 size={18} className="spin" /> : <Send size={18} />}
      </button>
    </form>
  );
}

function formatTime() {
  return new Date().toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit"
  });
}

function formatDateTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function turnsToMessages(turns) {
  const restored = [];
  turns.forEach((turn) => {
    if (turn.interviewer) {
      restored.push({
        id: crypto.randomUUID(),
        role: "agent",
        text: turn.interviewer,
        fallback: Boolean(turn.fallback_used),
        time: formatDateTime(turn.created_at)
      });
    }
    if (turn.candidate) {
      restored.push({
        id: crypto.randomUUID(),
        role: "user",
        text: turn.candidate,
        fallback: false,
        time: formatDateTime(turn.updated_at)
      });
    }
  });
  return restored;
}

function normalizeDesktopError(message = "") {
  return message
    .replace(/^Error invoking remote method '[^']+':\s*/u, "")
    .replace(/^Error:\s*/u, "");
}

function buildInterviewGoal(profile, seedMessage = "") {
  const baseGoal =
    profile.interviewGoal ||
    "请基于我的简历和做过的事情进行 AI 工程面试，重点深挖真实项目、RAG/Agent、评测、上线和安全治理。";
  if (!seedMessage) return baseGoal;
  return `${baseGoal}\n本轮启动意图：${seedMessage}`;
}

function buildFocusAreas(profile, seedMessage = "", industryOptions = fallbackIndustries) {
  const role = profile.targetRole || "AI 应用工程师";
  const industry = currentIndustry(industryOptions, profile.industry);
  const label = industry?.label || "";
  const recommended = industry?.recommended_focus_areas || [];
  const areas = recommended.length
    ? recommended
    : [
        `${label}简历项目深挖`,
        `${label}${role}核心能力`,
        `${label}RAG / Agent / LLMOps 生产化`,
        `${label}评测、上线、安全与观测`,
        `${label}行为协作与项目复盘`
      ];
  if (seedMessage.includes("RAG")) {
    return ["简历中的 RAG 项目深挖", ...areas.filter((area) => !area.includes("简历项目"))];
  }
  if (seedMessage.includes("LLMOps") || seedMessage.includes("评测")) {
    return ["LLMOps、评测和上线治理", ...areas.filter((area) => !area.includes("评测"))];
  }
  if (seedMessage.includes("Agent") || seedMessage.includes("工具调用")) {
    return ["Agent 工具调用和安全护栏", ...areas.filter((area) => !area.includes("RAG / Agent"))];
  }
  return areas;
}

function currentIndustry(industryOptions, value) {
  return industryOptions.find((industry) => industry.value === value) || industryOptions[0] || fallbackIndustries[0];
}

function currentModel(modelOptions, value) {
  return modelOptions.find((model) => model.id === value) || modelOptions[0] || fallbackModels[0];
}

function formatCredits(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number)) return String(value || "0");
  if (number >= 100) return number.toFixed(0);
  if (number >= 1) return number.toFixed(2);
  return number.toFixed(6).replace(/0+$/u, "").replace(/\.$/u, "");
}

createRoot(document.getElementById("root")).render(<App />);
