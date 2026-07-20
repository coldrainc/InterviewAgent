import { Globe2, Loader2, MessageSquarePlus, Moon, RefreshCw, Trash2, Upload } from "lucide-react";
import { interviewModes, llmModes } from "../../constants/interview";
import { currentIndustry } from "../../utils/interview";
import { ModelSelector } from "../common/ModelSelector";

export function SetupCenter({
  profile,
  offline,
  webSearch,
  modelOptions,
  selectedModelId,
  selectedLlmMode,
  industryOptions,
  resumeImport,
  requirementsImport,
  resumeLibrary,
  selectedResumeId,
  busy,
  onNewSession,
  onImportResume,
  onImportRequirements,
  onSelectResume,
  onDeleteResume,
  onReloadResumes,
  onProfileChange,
  onDefaultModeChange,
  onOfflineChange,
  onWebSearchChange,
  onSelectModel,
  onSelectLlmMode,
  onBack
}) {
  const updateProfile = (key, value) => {
    onProfileChange((current) => ({ ...current, [key]: value }));
  };
  const industry = currentIndustry(industryOptions, profile.industry);

  return (
    <section className="setup-center">
      <div className="setup-hero">
        <div>
          <span className="eyebrow">Interview Setup</span>
          <h3>面试配置</h3>
          <p>这里只放开始面试前需要调的内容。配置好后回到工作台直接对话。</p>
        </div>
        <div className="setup-hero-actions">
          <button type="button" className="secondary-action inline" onClick={onBack}>返回工作台</button>
          <button type="button" className="primary-action inline" onClick={onNewSession} disabled={busy}>
            <MessageSquarePlus size={17} />
            {profile.mode === "candidate" ? "开始答题" : "开始面试"}
          </button>
        </div>
      </div>

      <div className="setup-grid">
        <section className="setup-block">
          <div className="panel-heading">
            <span>工作方式</span>
          </div>
          <SegmentedControl
            value={profile.mode}
            options={interviewModes}
            onChange={(value) => onDefaultModeChange?.(value) || updateProfile("mode", value)}
          />
          <label className="select-field">
            <span>行业</span>
            <select value={profile.industry} onChange={(event) => updateProfile("industry", event.target.value)}>
              {industryOptions.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </label>
          <IndustryBrief industry={industry} />
          <div className="setup-toggles">
            <Toggle icon={<Moon size={16} />} label="离线模式" checked={offline} onChange={onOfflineChange} />
            <Toggle icon={<Globe2 size={16} />} label="联网搜索" checked={webSearch} onChange={onWebSearchChange} />
          </div>
        </section>

        <section className="setup-block">
          <div className="panel-heading">
            <span>模型</span>
          </div>
          <ModelSelector
            models={modelOptions}
            selectedModelId={selectedModelId}
            onSelectModel={onSelectModel}
            llmModes={llmModes}
            selectedLlmMode={selectedLlmMode}
            onSelectLlmMode={onSelectLlmMode}
          />
        </section>

        <section className="setup-block wide">
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
            <Field label="姓名" value={profile.candidateName} placeholder="例如：张三" onChange={(value) => updateProfile("candidateName", value)} />
            <Field label="级别" value={profile.seniority} placeholder="中级 / 高级" onChange={(value) => updateProfile("seniority", value)} />
          </div>
          <Field label="目标岗位" value={profile.targetRole} placeholder="AI 应用工程师 / Agent 工程师" onChange={(value) => updateProfile("targetRole", value)} />
          <Field textarea label="简历摘要" value={profile.resumeSummary} placeholder="粘贴 3-5 行简历摘要：岗位、年限、技术栈、代表项目..." onChange={(value) => updateProfile("resumeSummary", value)} />
          <Field textarea tall label="完整简历" value={profile.resumeText} placeholder="可粘贴完整简历，面试官会围绕其中的项目、职责和技术栈追问。" onChange={(value) => updateProfile("resumeText", value)} />
          <Field textarea tall label="做过的事情" value={profile.projectExperience} placeholder="写你真实做过的项目：背景、职责、架构、指标、难点、复盘。" onChange={(value) => updateProfile("projectExperience", value)} />
          <div className="requirements-panel">
            <div className="requirements-panel-head">
              <div>
                <span>面试官要求</span>
                <small>上传 JD、面试通知、考察范围或手动粘贴，回答会同时参考简历和这些要求。</small>
              </div>
              <button
                type="button"
                className="secondary-action inline"
                onClick={onImportRequirements}
                disabled={busy || requirementsImport?.status === "loading"}
              >
                {requirementsImport?.status === "loading" ? <Loader2 size={17} className="spin" /> : <Upload size={17} />}
                上传要求
              </button>
            </div>
            <RequirementsImportStatus state={requirementsImport} />
            <Field
              textarea
              tall
              label="要求内容"
              value={profile.interviewerRequirements}
              placeholder="例如：重点考察 Agent 工程经验、RAG 生产化、评测指标、线上稳定性、安全合规、候选人过往项目真实性..."
              onChange={(value) => updateProfile("interviewerRequirements", value)}
            />
          </div>
          <Field textarea label="面试目标" value={profile.interviewGoal} placeholder="希望面试官重点考察哪些方向？" onChange={(value) => updateProfile("interviewGoal", value)} />
        </section>
      </div>
    </section>
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

function RequirementsImportStatus({ state }) {
  if (!state || state.status === "idle") {
    return <p className="resume-hint">支持 .pdf、.md、.markdown、.txt；导入后仍可手动编辑。</p>;
  }
  if (state.status === "loading") {
    return <p className="resume-hint active">正在解析面试官要求...</p>;
  }
  if (state.status === "error") {
    return <p className="resume-hint error">{state.error}</p>;
  }
  return (
    <p className="resume-hint success">
      当前要求来自 {state.filename}
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
          <option key={resume.id} value={resume.id}>{resume.filename}</option>
        ))}
      </select>
      {selectedResumeId && (
        <div className="resume-library-actions">
          <small>已保存 {resumes.length} 份，当前面试会使用选中的这份简历。</small>
          <button type="button" className="danger-inline" onClick={confirmDelete} disabled={busy}>
            <Trash2 size={13} />
            删除
          </button>
        </div>
      )}
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
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span className="toggle-track" aria-hidden="true"><span /></span>
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
