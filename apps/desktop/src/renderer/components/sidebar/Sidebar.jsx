import { useMemo, useState } from "react";
import {
  Activity,
  CalendarCheck2,
  ClipboardList,
  History,
  House,
  MessageSquareMore,
  MessageSquarePlus,
  PanelLeftClose,
  PenLine,
  RefreshCw,
  Settings,
  SlidersHorizontal,
  Trash2,
  Wand2
} from "lucide-react";
import { formatDateTime } from "../../utils/interview";
import { AccountEntry } from "../account/AccountCenter";

const HISTORY_PREVIEW_COUNT = 6;

export default function Sidebar({
  screen,
  profile,
  account,
  sessionHistory,
  historyState,
  activeSessionId,
  busy,
  reportScores,
  onNewSession,
  onReloadSessions,
  onRestoreSession,
  onDeleteSession,
  onScreenChange,
  onToggleSidebar
}) {
  const isAdmin = account?.role === "admin";
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <img src="./favicon.svg" alt="" aria-hidden="true" />
        </div>
        <div>
          <h1>Interview Agent</h1>
          <p>AI 面试备考工作台</p>
        </div>
        {onToggleSidebar && (
          <button
            type="button"
            className="sidebar-collapse-btn"
            onClick={onToggleSidebar}
            title="收起菜单 (⌘B / Ctrl+B)"
            aria-label="收起菜单"
          >
            <PanelLeftClose size={16} />
          </button>
        )}
      </div>

      <button className="primary-action" onClick={onNewSession} disabled={busy}>
        <MessageSquarePlus size={18} />
        {profile.mode === "candidate" ? "开始被面试回答" : "基于简历新建面试"}
      </button>

      <nav className="sidebar-nav" aria-label="主导航">
        <div className="nav-group-label">今日</div>
        <NavButton
          active={screen === "home"}
          icon={<House size={17} />}
          label="今日驾驶舱"
          detail="打卡 · 任务 · 数据"
          onClick={() => onScreenChange("home")}
        />

        <div className="nav-group-label">面试</div>
        <NavButton
          active={screen === "chat"}
          icon={<MessageSquareMore size={17} />}
          label="模拟面试"
          detail="对话和追问"
          onClick={() => onScreenChange("chat")}
        />
        <NavButton
          active={screen === "reports"}
          icon={<ClipboardList size={17} />}
          label="面试报告"
          detail="评分 · 薄弱项 · 建议"
          onClick={() => onScreenChange("reports")}
        />
        <NavButton
          active={screen === "setup"}
          icon={<SlidersHorizontal size={17} />}
          label="面试配置"
          detail={`${profile.targetRole || "目标岗位"} · ${profile.mode === "candidate" ? "Agent 回答" : "Agent 提问"}`}
          onClick={() => onScreenChange("setup")}
        />

        <div className="nav-group-label">训练</div>
        <NavButton
          active={screen === "practice"}
          icon={<PenLine size={17} />}
          label="刷题训练"
          detail="题库 · 作答 · 错题本"
          onClick={() => onScreenChange("practice")}
        />

        <div className="nav-group-label">复习</div>
        <NavButton
          active={screen === "review-site"}
          icon={<CalendarCheck2 size={17} />}
          label="复习站"
          detail="计划 · 打卡 · 素材"
          onClick={() => onScreenChange("review-site")}
        />
        <NavButton
          active={screen === "planner"}
          icon={<Wand2 size={17} />}
          label="计划生成器"
          detail="AI 定制复习计划"
          onClick={() => onScreenChange("planner")}
        />

        <div className="nav-group-label">我的</div>
        {isAdmin && (
          <NavButton
            active={screen === "ops"}
            icon={<Activity size={17} />}
            label="任务与评测"
            detail="工作流 / AgentOps"
            onClick={() => onScreenChange("ops")}
          />
        )}
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
          <small>提醒 · 主题 · 默认模式</small>
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
          reportScores={reportScores}
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

function SessionHistory({ sessions, activeSessionId, state, busy, reportScores, onRestore, onDelete }) {
  const [modeFilter, setModeFilter] = useState("all");
  const [expanded, setExpanded] = useState(false);

  const filtered = useMemo(() => {
    if (modeFilter === "all") return sessions;
    return sessions.filter((session) => (session.mode || "interviewer") === modeFilter);
  }, [sessions, modeFilter]);

  if (state?.status === "error") {
    return <p className="resume-hint error">{state.error}</p>;
  }
  if (!sessions.length) {
    return <p className="resume-hint">暂无历史会话，开始一次面试后会自动保存。</p>;
  }

  const visible = expanded ? filtered : filtered.slice(0, HISTORY_PREVIEW_COUNT);

  return (
    <div className="history-list">
      <div className="history-filter" role="tablist" aria-label="会话模式筛选">
        {[
          { value: "all", label: "全部" },
          { value: "interviewer", label: "模拟面试" },
          { value: "candidate", label: "候选人答题" }
        ].map((item) => (
          <button
            key={item.value}
            type="button"
            className={`history-filter-chip ${modeFilter === item.value ? "active" : ""}`}
            onClick={() => setModeFilter(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {visible.map((session) => {
        const score = reportScores?.[session.id];
        return (
          <div key={session.id} className={`history-item ${session.id === activeSessionId ? "active" : ""}`}>
            <button type="button" onClick={() => onRestore(session.id)} disabled={busy}>
              <strong>
                {session.target_role || "AI 面试"}
                {typeof score === "number" && <span className="history-score">{score}分</span>}
              </strong>
              <span>
                {session.mode === "candidate" ? "候选人回答" : "模拟面试"}
                {session.status === "completed" ? " · 已完成" : ""} · {formatDateTime(session.updated_at)}
              </span>
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
        );
      })}
      {filtered.length === 0 && <p className="resume-hint">该筛选下暂无会话。</p>}
      {filtered.length > HISTORY_PREVIEW_COUNT && (
        <button type="button" className="history-expand" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "收起" : `查看全部 ${filtered.length} 条`}
        </button>
      )}
      {state?.status === "success" && <p className="resume-hint success">{state.message}</p>}
    </div>
  );
}
