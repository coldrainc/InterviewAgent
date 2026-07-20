import { BookOpenCheck, History, MessageSquarePlus, RefreshCw, Settings, SlidersHorizontal, Trash2 } from "lucide-react";
import { formatDateTime } from "../../utils/interview";
import { AccountEntry } from "../account/AccountCenter";

export default function Sidebar({
  screen,
  profile,
  account,
  sessionHistory,
  historyState,
  activeSessionId,
  busy,
  onNewSession,
  onReloadSessions,
  onRestoreSession,
  onDeleteSession,
  onScreenChange
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <img src="./favicon.svg" alt="" aria-hidden="true" />
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

      <nav className="sidebar-nav" aria-label="主导航">
        <NavButton
          active={screen === "chat"}
          icon={<MessageSquarePlus size={17} />}
          label="面试工作台"
          detail="对话和追问"
          onClick={() => onScreenChange("chat")}
        />
        <NavButton
          active={screen === "setup"}
          icon={<SlidersHorizontal size={17} />}
          label="面试配置"
          detail={`${profile.targetRole || "目标岗位"} · ${profile.mode === "candidate" ? "Agent 回答" : "Agent 提问"}`}
          onClick={() => onScreenChange("setup")}
        />
        <NavButton
          active={screen === "study"}
          icon={<BookOpenCheck size={17} />}
          label="刷题学习"
          detail="考公题库和学习路径"
          onClick={() => onScreenChange("study")}
        />
      </nav>

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

      <section className="panel history-panel">
        <div className="panel-heading">
          <span><History size={15} /> 历史会话</span>
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
    </aside>
  );
}

function NavButton({ active, icon, label, detail, onClick }) {
  return (
    <button type="button" className={`nav-button ${active ? "active" : ""}`} onClick={onClick}>
      <span className="nav-button-icon">{icon}</span>
      <span>
        <strong>{label}</strong>
        <small>{detail}</small>
      </span>
    </button>
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
