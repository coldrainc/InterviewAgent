import { Bot, Coins, Loader2, MessageSquarePlus, PencilLine, Send, ShieldCheck, Sparkles, Square, Undo2, UserRound } from "lucide-react";
import { quickPrompts } from "../../constants/interview";
import { formatCredits } from "../../utils/interview";

export function Topbar({ sessionId, offline, webSearch, completed, status, profile, model, account, screen, onOpenAccount, onOpenChat }) {
  const mode = completed ? "已完成" : offline ? "离线模式" : "模型模式";
  const auxiliaryScreen = screen === "account" || screen === "settings" || screen === "setup" || screen === "study";
  const title =
    screen === "account"
      ? "账户中心"
      : screen === "settings"
      ? "设置"
      : screen === "setup"
      ? "面试配置"
      : screen === "study"
      ? "刷题学习"
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
        {auxiliaryScreen ? (
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
        {!auxiliaryScreen && (
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

export function EmptyState({ busy, mode, industry, onStart, onQuickPrompt }) {
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

export function Message({ message, mode, busy, onEditMessage, onWithdrawMessage }) {
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
          {message.stopped && <strong>已停止</strong>}
          {message.fallback && <strong>降级回复</strong>}
        </div>
        <div className={`message-bubble ${message.role}`}>{message.text}</div>
        {isUser && (
          <div className="message-actions">
            <button type="button" title="重新编辑这条消息" disabled={busy} onClick={() => onEditMessage?.(message)}>
              <PencilLine size={13} />
              重新编辑
            </button>
            <button type="button" title="撤回这条消息及后续回复" disabled={busy} onClick={() => onWithdrawMessage?.(message)}>
              <Undo2 size={13} />
              撤回
            </button>
          </div>
        )}
        {message.usage && <UsageMeta usage={message.usage} modelId={message.modelId} />}
      </div>
    </article>
  );
}

export function UsageMeta({ usage, modelId }) {
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

export function Typing() {
  return (
    <div className="typing">
      <Loader2 size={16} className="spin" />
      面试官正在分析回答、检索知识库并生成追问...
    </div>
  );
}

export function Composer({ value, busy, hasSession, textareaRef, onChange, onSubmit, onKeyDown, onStop, mode }) {
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
      <button
        type={busy ? "button" : "submit"}
        disabled={!busy && !value.trim()}
        aria-label={busy ? "停止生成" : "发送回答"}
        title={busy ? "停止生成" : "发送"}
        onClick={busy ? onStop : undefined}
      >
        {busy ? <Square size={17} /> : <Send size={18} />}
      </button>
    </form>
  );
}
