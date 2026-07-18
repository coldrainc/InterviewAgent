import { Activity, BrainCircuit, Globe2, Loader2, MessageSquarePlus, Moon, RefreshCw, Search, Settings, ShieldCheck, Trash2, Upload } from "lucide-react";
import { interviewModes, llmModes } from "../../constants/interview";
import { currentIndustry, formatDateTime } from "../../utils/interview";
import { AccountEntry } from "../account/AccountCenter";
import { ModelSelector } from "../common/ModelSelector";

export default function Sidebar({
  screen,
  offline,
  webSearch,
  profile,
  account,
  modelOptions,
  selectedModelId,
  selectedLlmMode,
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
  onDefaultModeChange,
  onSelectModel,
  onSelectLlmMode
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

      <button
        type="button"
        className={`account-entry ${screen === "settings" ? "active" : ""}`}
        onClick={() => onScreenChange("settings")}
      >
        <span className="account-entry-icon">
          <Settings size={17} />
        </span>
        <span className="account-entry-main">
          <strong>设置</strong>
          <small>{profile.mode === "candidate" ? "默认 Agent 回答我" : "默认 Agent 面试我"}</small>
        </span>
        <Settings size={15} />
      </button>

      <section className="panel mode-panel">
        <div className="panel-heading">
          <span>模式与行业</span>
        </div>
        <SegmentedControl
          value={profile.mode}
          options={interviewModes}
          onChange={(value) => onDefaultModeChange?.(value) || updateProfile("mode", value)}
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
          llmModes={llmModes}
          selectedLlmMode={selectedLlmMode}
          onSelectLlmMode={onSelectLlmMode}
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
