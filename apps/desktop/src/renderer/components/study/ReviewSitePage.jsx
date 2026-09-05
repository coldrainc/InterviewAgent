import { useEffect, useMemo, useRef, useState } from "react";
import {
  Award, BookOpen, Check, ChevronDown, ChevronLeft, ChevronRight, Clock, Download,
  ExternalLink, FileText, Flame, Gauge, Inbox, Loader2, PartyPopper,
  Mic, NotebookPen, Pause, Play, Plus, Printer, RefreshCw, Search, Shuffle,
  Sparkles, Star as StarIcon, Target, Trophy, Upload, Wand2, X, Zap
} from "lucide-react";
import { getInterviewAgentClient } from "../../apiClient";

const api = getInterviewAgentClient();

const TAB_DEFS = [
  { key: "today", label: "今日", icon: <Sparkles size={15} /> },
  { key: "plan", label: "每日打卡", icon: <NotebookPen size={15} /> },
  { key: "practice", label: "题库", icon: <BookOpen size={15} /> },
  { key: "intro", label: "自我介绍", icon: <Mic size={15} /> },
  { key: "star", label: "STAR 卡", icon: <StarIcon size={15} /> },
  { key: "a4", label: "A4 速记", icon: <FileText size={15} /> },
  { key: "awards", label: "成就", icon: <Trophy size={15} /> }
];

const PHASE_PRESETS = [
  { key: "foundation", title: "基础夯实", range: "Day 1-4", goal: "构建知识体系骨架", accent: "#2f63e8" },
  { key: "deepening", title: "专题深挖", range: "Day 5-8", goal: "高频重难点突破", accent: "#0f8f8f" },
  { key: "project", title: "项目打磨", range: "Day 9-11", goal: "STAR 表达与亮点包装", accent: "#16a673" },
  { key: "simulation", title: "模拟冲刺", range: "Day 12-14", goal: "全流程高压模拟", accent: "#c77918" }
];

function normalizePlanDetail(payload) {
  const fallback = { plan: {}, phases: [], days: [], progresses: [], intro_scripts: [], star_cards: [], a4_memory: [] };
  if (!payload || typeof payload !== "object") return fallback;
  const plan = payload.plan && typeof payload.plan === "object"
    ? payload.plan
    : {
        id: payload.id,
        plan_key: payload.plan_key,
        title: payload.title,
        subtitle: payload.subtitle,
        description: payload.description,
        status: payload.status,
        source_root: payload.source_root,
        source_documents: payload.source_documents,
        commercial_positioning: payload.commercial_positioning,
        metadata: payload.metadata
      };
  return {
    ...fallback,
    ...payload,
    plan,
    phases: Array.isArray(payload.phases) ? payload.phases : [],
    days: Array.isArray(payload.days) ? payload.days : [],
    progresses: Array.isArray(payload.progresses) ? payload.progresses : [],
    intro_scripts: Array.isArray(payload.intro_scripts) ? payload.intro_scripts : [],
    star_cards: Array.isArray(payload.star_cards) ? payload.star_cards : [],
    a4_memory: Array.isArray(payload.a4_memory) ? payload.a4_memory : []
  };
}

function useToast() {
  const [toasts, setToasts] = useState([]);
  const addToast = (msg, variant = "info", timeoutMs = 2400) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setToasts((cur) => [...cur, { id, msg, variant }]);
    window.setTimeout(() => {
      setToasts((cur) => cur.filter((t) => t.id !== id));
    }, timeoutMs);
  };
  return { toasts, addToast };
}

function Toast({ toasts }) {
  if (!toasts?.length) return null;
  const iconOf = (v) => {
    if (v === "success") return <Check size={16} />;
    if (v === "warn") return <Zap size={16} />;
    if (v === "error") return <X size={16} />;
    return <Sparkles size={16} />;
  };
  return (
    <div className="v3-toast-layer">
      {toasts.map((t) => (
        <div key={t.id} className={`v3-toast ${t.variant || "info"}`}>
          <span className="v3-toast-icon">{iconOf(t.variant)}</span>
          <span>{t.msg}</span>
        </div>
      ))}
    </div>
  );
}

function V3Stat({ icon, label, value }) {
  return (
    <div className="v3-stat">
      <div className="v3-stat-icon">{icon}</div>
      <div>
        <small className="v3-stat-label">{label}</small>
        <strong className="v3-stat-value">{value}</strong>
      </div>
    </div>
  );
}

function V3MasteryStars({ value = 0, onChange, disabled }) {
  return (
    <div className="v3-stars">
      {[1, 2, 3, 4, 5].map((s) => (
        <StarIcon
          key={s}
          size={12}
          className={`star ${s <= value ? "on" : ""}`}
          onClick={disabled ? undefined : () => onChange?.(s)}
          fill={s <= value ? "currentColor" : "none"}
        />
      ))}
    </div>
  );
}

function V3TaskCard({ task, progress, onUpdate }) {
  const [local, setLocal] = useState({
    done: Boolean(progress?.done),
    note: progress?.note || "",
    mastery: Number(progress?.mastery_score || 0)
  });
  const [noteOpen, setNoteOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const isCritical = task.critical === true || String(task.tags || "").includes("critical");
  const isSim = task.simulation === true;

  async function patch(patchData, optimistic, rollback) {
    setSaving(true);
    const result = await api.reviewSite.patchProgress(task.id, patchData);
    if (result === null) {
      if (rollback) rollback();
      onUpdate?.(task.id, null, true);
    } else {
      onUpdate?.(task.id, { ...progress, ...patchData, ...(result || {}) }, false);
    }
    setSaving(false);
  }

  function toggleDone() {
    const nextDone = !local.done;
    const prevDone = local.done;
    setLocal((cur) => ({ ...cur, done: nextDone }));
    patch(
      { done: nextDone, done_at: nextDone ? new Date().toISOString() : null },
      null,
      () => setLocal((cur) => ({ ...cur, done: prevDone }))
    );
  }

  function changeMastery(score) {
    const prev = local.mastery;
    setLocal((cur) => ({ ...cur, mastery: score }));
    patch({ mastery_score: score }, null, () => setLocal((cur) => ({ ...cur, mastery: prev })));
  }

  const commitNoteDebounced = (() => {
    let timer;
    return (value) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        const prev = local.note;
        patch({ note: value }, null, () => setLocal((cur) => ({ ...cur, note: prev })));
      }, 650);
    };
  })();

  function onNoteChange(e) {
    const v = e.target.value;
    setLocal((cur) => ({ ...cur, note: v }));
    commitNoteDebounced(v);
  }

  return (
    <div className={`v3-task-card ${local.done ? "done" : ""}`} data-task-id={task.id}>
      <input
        type="checkbox"
        className="v3-task-checkbox"
        checked={local.done}
        onChange={toggleDone}
        disabled={saving}
        aria-label={local.done ? "标记未完成" : "标记完成"}
      />
      <div className="v3-task-content">
        <span className="v3-task-title">{task.title || "未命名任务"}</span>
        {task.reason && (
          <span className="v3-task-reason"><Sparkles size={11} /> {task.reason}</span>
        )}
        <div className="v3-task-meta">
          {isCritical && (
            <span className="v3-chip warn"><Flame size={10} /> 核心</span>
          )}
          {isSim && (
            <span className="v3-chip accent"><Zap size={10} /> 模拟</span>
          )}
          {task.link_type === "interview" && !isSim && (
            <span className="v3-chip accent"><Mic size={10} /> 模拟面任务</span>
          )}
          {task.link_type === "practice" && (
            <span className="v3-chip"><BookOpen size={10} /> 刷题任务</span>
          )}
          {task.link_type === "knowledge" && (
            <span className="v3-chip"><FileText size={10} /> 知识复习</span>
          )}
          {(task.tags || []).filter((t) => t && t !== "critical" && t !== "simulation").slice(0, 4).map((t, i) => (
            <span key={i} className="v3-chip">{t}</span>
          ))}
          <div style={{ flex: 1 }} />
          <V3MasteryStars value={local.mastery} onChange={changeMastery} disabled={saving} />
          <button
            className="v3-btn ghost icon-only small"
            onClick={() => setNoteOpen((v) => !v)}
            title="笔记"
            aria-label="笔记"
          >
            <FileText size={13} />
          </button>
          {Array.isArray(task.docs) && task.docs.length > 0 && task.docs.slice(0, 1).map((doc, i) => {
            const href = typeof doc === "string" ? doc : doc?.url || doc?.link || "#";
            const label = typeof doc === "string" ? "资料" : doc?.label || doc?.title || "资料";
            return (
              <a key={i} className="v3-chip doc" href={href} target="_blank" rel="noopener noreferrer">
                <ExternalLink size={10} /> {label}
              </a>
            );
          })}
        </div>
        {noteOpen && (
          <div className="v3-task-note">
            <textarea
              value={local.note}
              onChange={onNoteChange}
              placeholder="笔记、踩坑、要点..."
            />
          </div>
        )}
      </div>
    </div>
  );
}

function StreakCheckinCard({ streak, checkedToday, busy, onCheckin }) {
  const [open, setOpen] = useState(false);
  const [minutes, setMinutes] = useState(45);
  const [note, setNote] = useState("");
  const current = Number(streak?.current_streak || 0);
  const longest = Number(streak?.longest_streak || 0);
  const totalDays = Number(streak?.total_checkin_days || 0);

  async function submit() {
    const mins = Math.max(1, Number(minutes) || 0);
    await onCheckin?.({ elapsed_minutes: mins, note: note.trim() });
    setOpen(false);
    setNote("");
  }

  return (
    <div className={`v3-checkin-card ${checkedToday ? "checked" : ""}`}>
      <div className="v3-checkin-flame">
        <Flame size={26} />
      </div>
      <div className="v3-checkin-info">
        <strong>{current > 0 ? `已连续打卡 ${current} 天` : "今天还没有打卡"}</strong>
        <span>最长 {longest} 天 · 累计 {totalDays} 天{checkedToday ? " · 今日已打卡" : "，完成学习后记得打卡"}</span>
      </div>
      {checkedToday ? (
        <span className="v3-chip toggle on"><Check size={12} /> 今日已打卡</span>
      ) : open ? (
        <div className="v3-checkin-form">
          <label>
            今日学习
            <input
              type="number"
              min="1"
              max="1440"
              className="v3-input"
              value={minutes}
              onChange={(e) => setMinutes(e.target.value)}
            />
            分钟
          </label>
          <input
            className="v3-input"
            placeholder="一句话备注（可选）"
            value={note}
            maxLength={80}
            onChange={(e) => setNote(e.target.value)}
          />
          <button className="v3-btn primary small" disabled={busy} onClick={submit}>
            {busy ? <Loader2 size={13} className="v3-spin" /> : <Check size={13} />} 打卡
          </button>
          <button className="v3-btn ghost small" disabled={busy} onClick={() => setOpen(false)}>
            取消
          </button>
        </div>
      ) : (
        <button className="v3-btn primary" disabled={busy} onClick={() => setOpen(true)}>
          {busy ? <Loader2 size={14} className="v3-spin" /> : <Flame size={14} />} 今日打卡
        </button>
      )}
    </div>
  );
}

function AwardsWall({ data, loading }) {
  const list = Array.isArray(data?.achievements) ? data.achievements : [];
  if (loading) {
    return (
      <div style={{ display: "grid", gap: 12 }}>
        <div className="skeleton" style={{ height: 80 }} />
        <div className="skeleton" style={{ height: 80 }} />
        <div className="skeleton" style={{ height: 80 }} />
      </div>
    );
  }
  if (!list.length) {
    return (
      <div className="empty-state v3-empty">
        <Trophy size={28} style={{ color: "var(--v3-text-3)" }} />
        <h4>成就即将解锁</h4>
        <p>完成首场模拟面、连续打卡、攻克错题都会解锁徽章，先去完成今日任务吧。</p>
      </div>
    );
  }
  return (
    <>
      <div className="v3-awards-summary">
        <Trophy size={16} />
        <strong>已解锁 {data?.unlocked_count || 0} / {data?.total_count || list.length} 枚徽章</strong>
      </div>
      <div className="v3-awards-grid">
        {list.map((a) => {
          const goal = Math.max(1, Number(a.goal || 1));
          const progress = Math.min(goal, Number(a.progress || 0));
          const pct = Math.round((progress / goal) * 100);
          return (
            <article key={a.key} className={`v3-award-card ${a.unlocked ? "unlocked" : ""}`}>
              <div className="v3-award-icon">
                {a.category === "streak" ? <Flame size={20} />
                  : a.category === "practice" ? <Target size={20} />
                  : a.category === "interview" ? <Gauge size={20} />
                  : <Award size={20} />}
              </div>
              <div className="v3-award-body">
                <strong>{a.title || a.key}</strong>
                <p>{a.description || ""}</p>
                {a.unlocked ? (
                  <span className="v3-chip toggle on"><Check size={11} /> 已解锁{a.unlocked_at ? ` · ${String(a.unlocked_at).slice(0, 10)}` : ""}</span>
                ) : (
                  <div className="v3-award-progress">
                    <div className="v3-award-progress-bar"><div style={{ width: `${pct}%` }} /></div>
                    <span>{progress}/{goal}</span>
                  </div>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </>
  );
}

function TodayView({ planDetail, phases, days, progresses, todayIdx, visibleDays, totalTasks, doneTasks, totalMinutes, masteryAvg, wrongBook, onUpdateProgress, setTab, setPhaseFilter, scrollToDay, streak, checkedToday, checkinBusy, onCheckin }) {
  const todayDay = visibleDays[todayIdx] || visibleDays[0];
  const todayTasks = todayDay?.tasks || [];
  const todayDone = todayTasks.filter((t) => progresses.find((p) => p.task_id === t.id && p.done)).length;
  const todayPct = todayTasks.length ? Math.round((todayDone / todayTasks.length) * 100) : 0;
  const currentPhase = phases.find((p) => p.phase_key === todayDay?.phase_key) || phases[0];

  const circumference = 2 * Math.PI * 52;
  const offset = circumference - (todayPct / 100) * circumference;

  return (
    <>
      <StreakCheckinCard
        streak={streak}
        checkedToday={checkedToday}
        busy={checkinBusy}
        onCheckin={onCheckin}
      />
      <div className="v3-progress-card">
        <div className="v3-progress-info">
          <div className="v3-progress-day">Day {todayDay?.sort_order || 1} of {visibleDays.length}</div>
          <h3>今天你该完成 {todayTasks.length} 个任务</h3>
          <p className="v3-progress-subtitle">
            {currentPhase?.title || ""}：{currentPhase?.goal || "继续加油"}
          </p>
        </div>
        <div className="v3-ring">
          <svg viewBox="0 0 120 120" width="130" height="130">
            <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(47, 99, 232, 0.12)" strokeWidth="8" />
            <circle
              cx="60" cy="60" r="52" fill="none" stroke="#2f63e8" strokeWidth="8"
              strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset}
              transform="rotate(-90 60 60)"
            />
          </svg>
          <span className="v3-pct">{todayPct}%</span>
        </div>
      </div>

      <div className="v3-stat-grid">
        <V3Stat icon={<Target size={18} />} label="总任务" value={totalTasks} />
        <V3Stat icon={<Check size={18} />} label="已完成" value={doneTasks} />
        <V3Stat icon={<Clock size={18} />} label="已用时" value={`${Math.round((totalMinutes / 60) * 10) / 10}h`} />
        <V3Stat icon={<Gauge size={18} />} label="掌握度" value={`${masteryAvg || 0}/5`} />
      </div>

      <div className="v3-today-tasks">
        <div className="v3-section-head">
          <h4>
            今日 · Day {todayDay?.sort_order || 1} 任务
          </h4>
          {todayDay?.acceptance && (
            <span className="v3-chip" title={todayDay.acceptance}>验收标准</span>
          )}
        </div>
        <div style={{ display: "grid", gap: 10 }}>
          {todayTasks.length === 0 ? (
            <p style={{ color: "var(--v3-text-3)" }}>今日暂无任务</p>
          ) : todayTasks.slice(0, 6).map((task) => (
            <V3TaskCard
              key={task.id || task.task_key}
              task={task}
              progress={progresses.find((p) => p.task_id === task.id)}
              onUpdate={onUpdateProgress}
            />
          ))}
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
          <button className="v3-btn ghost small" onClick={() => { setTab("plan"); setPhaseFilter(""); }}>
            <NotebookPen size={13} /> 查看全部 {visibleDays.length} 天
          </button>
          <button className="v3-btn ghost small" onClick={() => setTab("practice")}>
            <BookOpen size={13} /> 开始今日刷题
          </button>
        </div>
      </div>
    </>
  );
}

function V3PhaseDayCard({ day, phases, progresses, onUpdateProgress, isToday, scrollRef, open, onToggle }) {
  const phaseIdx = Math.max(0, phases.findIndex((p) => p.phase_key === day.phase_key));
  const phase = phases[phaseIdx];
  const phaseClass = `p${phaseIdx + 1}`;
  const tasks = day.tasks || [];
  const total = tasks.length;
  const done = tasks.filter((t) => progresses.find((p) => p.task_id === t.id && p.done)).length;
  const pct = total ? Math.round((done / total) * 100) : 0;

  return (
    <details
      className={`v3-day-item ${phaseClass} ${isToday ? "today" : ""}`}
      open={open}
      onToggle={(e) => onToggle?.(day, e.currentTarget.open)}
      ref={scrollRef}
    >
      <summary className="v3-day-summary">
        <ChevronRight size={16} className="chevron" />
        <div className="v3-day-marker" />
        <div className="v3-day-title">
          <strong>{day.title || day.day_label || "未命名日"}</strong>
          <span>
            {phase?.title || ""} · {day.day_label || `Day ${day.sort_order || ""}`} · {done}/{total} · {pct}%
          </span>
        </div>
      </summary>
      <div className="v3-day-body">
        {day.acceptance && (
          <div className="v3-day-acceptance">
            <strong>验收标准：</strong>{day.acceptance}
          </div>
        )}
        <div>
          {tasks.length === 0 ? (
            <p style={{ color: "var(--v3-text-3)" }}>暂无任务，导入或生成计划后会自动显示。</p>
          ) : tasks.map((task) => (
            <V3TaskCard
              key={task.id || task.task_key}
              task={task}
              progress={progresses.find((p) => p.task_id === task.id)}
              onUpdate={onUpdateProgress}
            />
          ))}
        </div>
      </div>
    </details>
  );
}

function V3FilterToolbar({ filters, setFilters, onRefresh, onShuffle, onlyWrong, setOnlyWrong, onlyUnmastered, setOnlyUnmastered, loading, todayCount, todayCorrect }) {
  const pct = todayCount ? Math.min(100, (todayCount / 10) * 100) : 0;
  const correctPct = todayCount ? Math.round((todayCorrect / todayCount) * 100) : 0;
  return (
    <>
      <div className="v3-practice-progress">
        <span>
          今日已刷 {todayCount} 题 · 正确率 {correctPct}%
        </span>
        <div className="v3-practice-progress-bar">
          <div className="v3-practice-progress-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>
      <div className="v3-filter-bar" style={{ padding: 0 }}>
        <div className="v3-filter-row">
          <div className="v3-field">
            <label>训练类型</label>
            <select className="v3-input" value={filters.category || ""} onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))}>
              <option value="">全部</option>
              <option value="ai_application">AI 应用</option>
              <option value="internet">互联网</option>
              <option value="leetcode">算法</option>
              <option value="behavioral">行为面试</option>
              <option value="system_design">系统设计</option>
            </select>
          </div>
          <div className="v3-field">
            <label>科目</label>
            <select className="v3-input" value={filters.subject || ""} onChange={(e) => setFilters((f) => ({ ...f, subject: e.target.value }))}>
              <option value="">全部</option>
              <option value="rag">RAG</option>
              <option value="agent_harness">Agent</option>
              <option value="algorithm">算法</option>
              <option value="project">项目深挖</option>
              <option value="frontend">前端</option>
              <option value="backend">后端</option>
            </select>
          </div>
          <div className="v3-field">
            <label>难度</label>
            <select className="v3-input" value={filters.difficulty || ""} onChange={(e) => setFilters((f) => ({ ...f, difficulty: e.target.value }))}>
              <option value="">全部</option>
              <option value="easy">简单</option>
              <option value="medium">中等</option>
              <option value="hard">困难</option>
            </select>
          </div>
          <div className="v3-field grow">
            <label>关键词</label>
            <div className="v3-search">
              <Search size={14} className="search-icon" />
              <input
                className="v3-input"
                placeholder="搜索题目..."
                value={filters.keyword || ""}
                onChange={(e) => setFilters((f) => ({ ...f, keyword: e.target.value }))}
              />
              {filters.keyword && (
                <button className="clear-btn" onClick={() => setFilters((f) => ({ ...f, keyword: "" }))}>
                  <X size={14} />
                </button>
              )}
            </div>
          </div>
        </div>
        <div className="v3-filter-chips">
          <button className={`v3-chip toggle ${onlyWrong ? "on" : ""}`} onClick={() => setOnlyWrong((v) => !v)}>
            <Target size={12} /> 只看错题
          </button>
          <button className={`v3-chip toggle ${onlyUnmastered ? "on" : ""}`} onClick={() => setOnlyUnmastered((v) => !v)}>
            <X size={12} /> 只看未掌握
          </button>
          <button className="v3-chip toggle" onClick={onShuffle} disabled={loading}>
            <Shuffle size={12} /> 随机 10 题
          </button>
          <div style={{ flex: 1 }} />
          <button className="v3-btn ghost small" onClick={onRefresh} disabled={loading}>
            {loading ? <Loader2 size={13} className="v3-spin" /> : <RefreshCw size={13} />} 刷新
          </button>
        </div>
      </div>
    </>
  );
}

function V3QaCard({ q, onMark }) {
  const [open, setOpen] = useState(false);
  const meta = [q.category, q.subject, q.difficulty, q.question_type].filter(Boolean);
  return (
    <article className={`v3-qa-card ${open ? "open" : ""}`}>
      {meta.length > 0 && (
        <div className="v3-qa-meta">
          {meta.map((m, i) => <span key={i} className="v3-chip">{m}</span>)}
          {q.mastery_level != null && (
            <span className={`v3-chip toggle ${(q.mastery_level || 0) >= 4 ? "on" : ""}`}>掌握 {q.mastery_level}/5</span>
          )}
        </div>
      )}
      <div className="v3-qa-q" onClick={() => setOpen((v) => !v)}>
        {q.prompt || q.title || "未命名题目"}
      </div>
      {open && (
        <>
          <div className="v3-qa-body">
            {q.answer && <p>{q.answer}</p>}
            {q.answer_detail && <div>{q.answer_detail}</div>}
            {q.code && (
              <pre><code>{typeof q.code === "string" ? q.code : JSON.stringify(q.code, null, 2)}</code></pre>
            )}
          </div>
          <div className="v3-qa-actions">
            <button className="v3-btn ghost icon-only" title="已掌握" onClick={() => onMark(q, { mastery_level: 5, mark_type: "mastered" })}>
              <Check size={15} />
            </button>
            <button className="v3-btn ghost icon-only" title="加入错题" onClick={() => onMark(q, { mark_type: "wrong" })}>
              <Target size={15} />
            </button>
            <button className="v3-btn ghost icon-only" title="不太懂" onClick={() => onMark(q, { mastery_level: 1, mark_type: "confused", note: "不太懂" })}>
              <X size={15} />
            </button>
          </div>
        </>
      )}
    </article>
  );
}

function V3StarCard({ card }) {
  const [flipped, setFlipped] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [dragX, setDragX] = useState(0);
  const drawerRef = useRef(null);
  const startX = useRef(0);
  const title = card.title || card.project_title || "未命名项目";
  const tags = Array.isArray(card.tags) ? card.tags : (card.tag ? String(card.tag).split(/[,，、]/).filter(Boolean) : []);
  const s = card.situation || card.background || card.s || "无";
  const t = card.task || card.challenge || card.t || "无";
  const a = card.action || card.solution || card.a || "无";
  const r = card.result || card.r || "无";
  const rPct = Math.min(100, Number(card.result_pct || card.result_score || 82));

  function onHandlePointerDown(e) {
    startX.current = e.clientX;
    const onMove = (ev) => {
      const dx = ev.clientX - startX.current;
      if (dx > 0) setDragX(dx);
    };
    const onUp = (ev) => {
      const dx = ev.clientX - startX.current;
      const w = drawerRef.current?.clientWidth || 440;
      if (dx >= w * 0.35) setDrawerOpen(false);
      setDragX(0);
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
    };
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
  }

  useEffect(() => {
    const h = () => setDrawerOpen(false);
    window.addEventListener("v3-close-all-drawers", h);
    return () => window.removeEventListener("v3-close-all-drawers", h);
  }, []);

  return (
    <>
      <div className="v3-star-card" onClick={() => setDrawerOpen(true)}>
        <button
          className="v3-btn ghost icon-only v3-star-flip-btn"
          onClick={(e) => { e.stopPropagation(); setFlipped((v) => !v); }}
          title="翻面"
        >
          <RefreshCw size={14} />
        </button>
        {!flipped ? (
          <>
            <div className="v3-star-tags">
              {tags.slice(0, 3).map((tg, i) => <span key={i} className="v3-chip">{tg}</span>)}
            </div>
            <div className="v3-star-title">{title}</div>
            <div className="v3-star-section">
              <span>S · 背景</span>
              <strong>{s}</strong>
            </div>
            <div className="v3-star-section">
              <span>T · 挑战</span>
              <strong>{t}</strong>
            </div>
          </>
        ) : (
          <>
            <div className="v3-star-tags">
              {tags.slice(0, 3).map((tg, i) => <span key={i} className="v3-chip">{tg}</span>)}
            </div>
            <div className="v3-star-title">{title}</div>
            <div className="v3-star-detail-block">
              <span>Action / 行动</span>
              <p>{a}</p>
            </div>
            <div className="v3-star-detail-block">
              <span>Result / 结果</span>
              <p>{r}</p>
            </div>
            <div className="v3-result-bar">
              <div className="fill" style={{ width: `${rPct}%` }} />
            </div>
          </>
        )}
      </div>
      {drawerOpen && (
        <div
          className="v3-drawer open"
          onClick={(e) => { if (e.target === e.currentTarget) setDrawerOpen(false); }}
        >
          <div
            ref={drawerRef}
            className="v3-drawer-inner"
            style={{ transform: dragX > 0 ? `translateX(${dragX}px)` : undefined }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="v3-drawer-handle"
              onPointerDown={onHandlePointerDown}
            />
            <div className="v3-drawer-head">
              <h4>{title}</h4>
              <button className="v3-btn ghost icon-only" onClick={() => setDrawerOpen(false)} aria-label="关闭">
                <X size={16} />
              </button>
            </div>
            <div className="v3-drawer-section">
              <h4>S · 背景</h4>
              <p>{s}</p>
            </div>
            <div className="v3-drawer-section">
              <h4>T · 挑战</h4>
              <p>{t}</p>
            </div>
            <div className="v3-drawer-section">
              <h4>A · 行动</h4>
              <p>{a}</p>
            </div>
            <div className="v3-drawer-section">
              <h4>R · 结果</h4>
              <p>{r}</p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function A4FaceCard({ items, side, title }) {
  return (
    <div className="v3-a4-card">
      <h5><FileText size={16} /> A4 速记 · {title || side}</h5>
      {(items || []).map((item, i) => {
        const text = item.content || item.text || item.point || item.title || "要点";
        return (
          <div key={item.id || item.key || i} className="point">
            <div className="num">{i + 1}</div>
            <p>{text}</p>
          </div>
        );
      })}
      {(!items || !items.length) && (
        <p style={{ color: "var(--v3-text-3)", marginTop: 20, fontSize: 13 }}>
          暂无要点。点击右上角「导入」按钮导入默认 A4 速记，或在计划生成器中开启 A4 选项。
        </p>
      )}
    </div>
  );
}

const MATERIAL_META = {
  intro_scripts: { title: "自我介绍话术", add: "新增话术" },
  star_cards: { title: "STAR 项目卡", add: "新增项目卡" },
  a4_memory: { title: "A4 速记要点", add: "新增速记" }
};

function materialEmptyForm(kind) {
  if (kind === "intro_scripts") return { label: "", duration_seconds: 90, scenario: "", text: "" };
  if (kind === "star_cards") return { title: "", tag: "", background: "", challenge: "", solution: "", result: "" };
  return { side: "ALL", content: "" };
}

function materialItemToForm(kind, item) {
  if (kind === "intro_scripts") {
    return {
      label: item.label || item.title || "",
      duration_seconds: Number(item.duration_seconds || item.duration || 90),
      scenario: item.scenario || "",
      text: item.text || item.content || ""
    };
  }
  if (kind === "star_cards") {
    const tags = Array.isArray(item.tags) ? item.tags.join(", ") : (item.tag || "");
    return {
      title: item.title || item.project_title || "",
      tag: tags,
      background: item.background || item.situation || item.s || "",
      challenge: item.challenge || item.task || item.t || "",
      solution: item.solution || item.action || item.a || "",
      result: item.result || item.r || ""
    };
  }
  return { side: item.side || "ALL", content: item.content || item.text || "" };
}

function materialItemTitle(kind, item) {
  if (kind === "intro_scripts") return item.label || item.title || item.script_key || "未命名话术";
  if (kind === "star_cards") return item.title || item.project_title || item.card_key || "未命名项目卡";
  return (item.content || "").slice(0, 24) || "未命名速记";
}

function MaterialManager({ kind, planId, items, onSaved, addToast }) {
  const meta = MATERIAL_META[kind];
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(() => materialEmptyForm(kind));

  function openNew() {
    setEditingId(null);
    setForm(materialEmptyForm(kind));
    setOpen(true);
  }

  function openEdit(item) {
    setEditingId(item.id);
    setForm(materialItemToForm(kind, item));
    setOpen(true);
  }

  function setField(key, value) {
    setForm((cur) => ({ ...cur, [key]: value }));
  }

  async function save() {
    if (!planId) {
      addToast("请先生成或导入一份计划", "warn");
      return;
    }
    setBusy(true);
    try {
      const payload = { ...form };
      if (kind === "intro_scripts") payload.duration_seconds = Number(payload.duration_seconds) || 90;
      if (editingId) {
        await api.reviewSite.updateMaterial(kind, editingId, payload);
      } else {
        await api.reviewSite.upsertMaterial(planId, kind, payload);
      }
      addToast(editingId ? "已保存修改" : "已新增", "success");
      setOpen(false);
      await onSaved?.();
    } catch (err) {
      addToast(`保存失败：${err?.message || "请稍后重试"}`, "error");
    } finally {
      setBusy(false);
    }
  }

  async function remove(item) {
    if (!window.confirm(`确定删除「${materialItemTitle(kind, item)}」？`)) return;
    setBusy(true);
    try {
      await api.reviewSite.deleteMaterial(kind, item.id);
      addToast("已删除", "success");
      if (editingId === item.id) setEditingId(null);
      await onSaved?.();
    } catch (err) {
      addToast(`删除失败：${err?.message || "请稍后重试"}`, "error");
    } finally {
      setBusy(false);
    }
  }

  const fields = kind === "intro_scripts" ? (
    <>
      <div className="v3-field"><label>版本名称</label>
        <input className="v3-input" value={form.label} onChange={(e) => setField("label", e.target.value)} placeholder="如 90 秒标准版" />
      </div>
      <div className="v3-field"><label>时长（秒）</label>
        <input className="v3-input" type="number" min={20} max={600} value={form.duration_seconds} onChange={(e) => setField("duration_seconds", e.target.value)} />
      </div>
      <div className="v3-field"><label>使用场景（可选）</label>
        <input className="v3-input" value={form.scenario} onChange={(e) => setField("scenario", e.target.value)} placeholder="如 一面开场 / HR 面" />
      </div>
      <div className="v3-field"><label>逐字稿（**关键词** 可高亮）</label>
        <textarea className="v3-input" rows={7} value={form.text} onChange={(e) => setField("text", e.target.value)} />
      </div>
    </>
  ) : kind === "star_cards" ? (
    <>
      <div className="v3-field"><label>项目标题</label>
        <input className="v3-input" value={form.title} onChange={(e) => setField("title", e.target.value)} placeholder="如 企业级 RAG 问答平台" />
      </div>
      <div className="v3-field"><label>标签（逗号分隔）</label>
        <input className="v3-input" value={form.tag} onChange={(e) => setField("tag", e.target.value)} placeholder="如 RAG, Go, 多租户" />
      </div>
      <div className="v3-field"><label>S · 背景 / 情境</label>
        <textarea className="v3-input" rows={3} value={form.background} onChange={(e) => setField("background", e.target.value)} />
      </div>
      <div className="v3-field"><label>T · 任务 / 挑战</label>
        <textarea className="v3-input" rows={3} value={form.challenge} onChange={(e) => setField("challenge", e.target.value)} />
      </div>
      <div className="v3-field"><label>A · 行动</label>
        <textarea className="v3-input" rows={4} value={form.solution} onChange={(e) => setField("solution", e.target.value)} />
      </div>
      <div className="v3-field"><label>R · 结果（含量化指标）</label>
        <textarea className="v3-input" rows={3} value={form.result} onChange={(e) => setField("result", e.target.value)} />
      </div>
    </>
  ) : (
    <>
      <div className="v3-field"><label>归属面</label>
        <select className="v3-input" value={form.side} onChange={(e) => setField("side", e.target.value)}>
          <option value="ALL">通用（A/B 自动分配）</option>
          <option value="A">A 面 · 知识主干</option>
          <option value="B">B 面 · 实战要点</option>
        </select>
      </div>
      <div className="v3-field"><label>速记要点（**关键词** 可高亮）</label>
        <textarea className="v3-input" rows={6} value={form.content} onChange={(e) => setField("content", e.target.value)} placeholder="一条速记一个知识点，打印后一页纸复习" />
      </div>
    </>
  );

  return (
    <>
      <div className="v3-material-bar">
        <button className="v3-btn primary small" onClick={openNew} disabled={!planId}>
          <Plus size={13} /> {meta.add}
        </button>
        <button className="v3-btn ghost small" onClick={() => setOpen(true)}>
          <NotebookPen size={13} /> 管理已有（{items?.length || 0}）
        </button>
      </div>
      {open && (
        <div className="modal-mask" onClick={(e) => { if (e.target === e.currentTarget) setOpen(false); }}>
          <div className="modal-card v3-material-modal">
            <div className="modal-head">
              <h3>{meta.title}</h3>
              <button className="icon-button" onClick={() => setOpen(false)} aria-label="关闭"><X size={16} /></button>
            </div>
            <div className="v3-material-list">
              {(items || []).length === 0 && <p style={{ color: "var(--v3-text-3)", fontSize: 13, margin: "4px 0 10px" }}>还没有内容，新增一条吧。</p>}
              {(items || []).map((item) => (
                <div key={item.id} className={`v3-material-row ${editingId === item.id ? "editing" : ""}`}>
                  <span>{materialItemTitle(kind, item)}</span>
                  <div>
                    <button className="v3-btn ghost icon-only" title="编辑" onClick={() => openEdit(item)}><NotebookPen size={13} /></button>
                    <button className="v3-btn ghost icon-only" title="删除" disabled={busy} onClick={() => remove(item)}><X size={13} /></button>
                  </div>
                </div>
              ))}
            </div>
            <div className="v3-material-form">
              <strong>{editingId ? "编辑" : "新增"}</strong>
              {fields}
              <div className="v3-material-form-actions">
                <button className="v3-btn ghost small" onClick={() => { setEditingId(null); setForm(materialEmptyForm(kind)); }}>
                  清空
                </button>
                <button className="v3-btn primary small" disabled={busy} onClick={save}>
                  {busy ? <Loader2 size={13} className="v3-spin" /> : <Check size={13} />} 保存
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function IntroPlayer({ scripts, onRunImport, addToast }) {
  const [tab, setTab] = useState(0);
  const list = scripts?.length ? scripts : [
    { key: "30s", title: "30 秒电梯", duration: 30, text: "面试官您好，我是**候选人**，\n在过去 6 年专注 **AI Native 全栈**工程，\n主导过 **RAG / Agent / 多模态** 产品落地。" },
    { key: "90s", title: "90 秒标准版", duration: 90, text: "您好，我是**候选人**。\n我是 **6 年 AI Native 全栈工程师**，\n熟悉 **前后端 + 大模型 + 数据 + 评测**。\n核心亮点：\n1) 设计并落地 **企业级 RAG 平台**，支撑 10+ 业务线；\n2) 主导 **多 Agent 协作框架**，任务成功率提升至 92%；\n3) 深耕 **质量评测与护栏**，线上事故率下降 65%。" },
    { key: "role", title: "岗位定制", duration: 120, text: "您好，我对 **AI Native 全栈** 岗位理解如下：\n- **产品思维**：从业务价值倒推技术方案；\n- **工程能力**：端到端交付，关注 **性能 / 成本 / 上线**；\n- **AI 深度**：RAG、Agent、Harness、**评测闭环**；\n- **跨端广度**：Web / 小程序 / 桌面端 / 服务端统一架构。\n\n我非常期待把我的经验带到贵团队，谢谢。" }
  ];
  const current = list[Math.min(tab, list.length - 1)];
  const currentKey = current?.id || current?.script_key || current?.key || "default";
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timerRef = useRef(null);
  const duration = Number(current?.duration_seconds || current?.duration || 90);
  const remaining = Math.max(0, duration - elapsed);
  const min = String(Math.floor(remaining / 60)).padStart(1, "0");
  const sec = String(remaining % 60).padStart(2, "0");
  const warning = remaining <= 30 && remaining > 0;

  const stats = useMemo(() => {
    try {
      const key = `v3:intro:${currentKey}`;
      const raw = JSON.parse(localStorage.getItem(key) || '{"count":0,"sumS":0,"timeout":0}');
      return { count: raw.count, avgS: raw.count ? Math.round(raw.sumS / raw.count) : 0, timeout: raw.timeout };
    } catch { return { count:0, avgS:0, timeout:0 }; }
  }, [tab, currentKey]);

  useEffect(() => {
    window.clearInterval(timerRef.current);
    setElapsed(0);
    setPlaying(false);
  }, [tab]);

  useEffect(() => {
    if (!playing) return;
    timerRef.current = window.setInterval(() => {
      setElapsed((cur) => {
        const next = cur + 1;
        if (next >= duration) {
          setPlaying(false);
          return duration;
        }
        return next;
      });
    }, 1000);
    return () => window.clearInterval(timerRef.current);
  }, [playing, duration]);

  const recordedRef = useRef(false);
  useEffect(() => {
    if (playing) {
      recordedRef.current = false;
      return;
    }
    if (recordedRef.current || elapsed < 10 || !duration) return;
    recordedRef.current = true;
    try {
      const key = `v3:intro:${currentKey}`;
      const raw = JSON.parse(localStorage.getItem(key) || '{"count":0,"sumS":0,"timeout":0}');
      raw.count += 1;
      raw.sumS += elapsed;
      if (elapsed >= duration) raw.timeout += 1;
      localStorage.setItem(key, JSON.stringify(raw));
    } catch {}
  }, [playing, elapsed, duration, currentKey]);

  function renderHighlighted(text) {
    const parts = String(text || "").split(/(\*\*[^*]+\*\*)/g);
    return parts.map((p, i) => p.startsWith("**") && p.endsWith("**")
      ? <b key={i}>{p.slice(2, -2)}</b>
      : <span key={i}>{p}</span>
    );
  }

  return (
    <div className="v3-intro">
      <div className="intro-chips">
        {list.map((s, i) => (
          <button key={s.id || s.script_key || s.key || i} className={`v3-chip toggle ${tab === i ? "on" : ""}`} onClick={() => setTab(i)}>
            <Clock size={12} /> {s.label || s.title || `${s.duration_seconds || s.duration || 30}s 版本`}
          </button>
        ))}
        {!scripts?.length && (
          <button className="v3-chip toggle" onClick={async () => {
            addToast("正在导入数据...", "info");
            const r = await api.reviewSite.runImport({});
            if (r?.ok || r?.created) addToast("导入完成，刷新页面即可查看", "success");
            else onRunImport?.();
          }}><Upload size={12} /> 导入示例数据</button>
        )}
      </div>
      <div className="intro-player">
        <div className="script-box">
          <div className="panel-title">
            <h4><FileText size={15} /> 逐字稿 · {current?.label || current?.title || "标准版本"}</h4>
            <span className="hint">预计 {duration}s{stats.count > 0 ? ` · 已练习 ${stats.count} 次` : " · 尚未练习"}</span>
          </div>
          <div className="content">{renderHighlighted(current?.text || current?.content || "")}</div>
        </div>
        <div className="timer-panel">
          <div className={`timer-display ${playing ? "playing" : ""} ${warning ? "warning" : ""}`}>
            <div className="time">{min}:{sec}</div>
            <div>
              {playing ? "正在练习中..." : warning ? "倒计时 30 秒内" : "准备就绪"}
            </div>
          </div>
          <div className="timer-actions">
            {!playing ? (
              <button className="play" onClick={() => setPlaying(true)}>
                <Play size={14} /> 开始
              </button>
            ) : (
              <button className="pause" onClick={() => setPlaying(false)}>
                <Pause size={14} /> 暂停
              </button>
            )}
            <button className="reset" onClick={() => { setPlaying(false); setElapsed(0); }}>
              <RefreshCw size={13} /> 重置
            </button>
          </div>
          <div className="intro-tips">
            <strong>练习要点</strong>
            90s 版本按「背景 → 亮点 1/2/3 → 期待」结构。
            关键词保持 <b style={{ color: "var(--v3-primary)" }}>高亮</b>，注意时间把控。
          </div>
          <div className="v3-intro-stats">
            <div><small>练习次数</small><b>{stats.count}</b></div>
            <div><small>平均用时</small><b>{stats.avgS || 0}s</b></div>
            <div><small>练满次数</small><b>{stats.timeout}</b></div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function ReviewSitePage({ onBack, onOpenPlanner }) {
  const planMenuRef = useRef(null);
  const qaListRef = useRef(null);
  const [celebrate, setCelebrate] = useState(null);
  const [practiceProgressSS, setPracticeProgressSS] = useState(null);
  const todayDoneRef = useRef(0);

  const { toasts, addToast } = useToast();
  const [tab, setTab] = useState("today");
  const [plans, setPlans] = useState([]);
  const [planId, setPlanId] = useState("");
  const [loading, setLoading] = useState(true);
  const [planDetail, setPlanDetail] = useState(() => normalizePlanDetail());
  const [phaseFilter, setPhaseFilter] = useState("");
  const [practiceState, setPracticeState] = useState({ items: [], total: 0, limit: 20, offset: 0, loading: false, onlyWrong: false, onlyUnmastered: false });
  const [practiceFilters, setPracticeFilters] = useState({ category: "", subject: "", difficulty: "", keyword: "" });
  const [wrongBook, setWrongBook] = useState([]);
  const [creatingPlan, setCreatingPlan] = useState(false);
  const [importing, setImporting] = useState(false);
  const [planMenuOpen, setPlanMenuOpen] = useState(false);
  const [collapsedAll, setCollapsedAll] = useState(false);
  const [openDayKeys, setOpenDayKeys] = useState(() => new Set());
  const [studyData, setStudyData] = useState(null);
  const [awardsData, setAwardsData] = useState(null);
  const [awardsLoading, setAwardsLoading] = useState(false);
  const [checkinBusy, setCheckinBusy] = useState(false);
  const dayScrollRefs = useRef({});

  const phases = planDetail.phases?.length ? planDetail.phases : PHASE_PRESETS;
  const days = planDetail.days || [];
  const progresses = planDetail.progresses || [];
  const allTasks = days.flatMap((d) => d.tasks || []);
  const totalTasks = allTasks.length;
  const doneTasks = allTasks.filter((t) => progresses.find((p) => p.task_id === t.id && p.done)).length;
  const totalMinutes = progresses.reduce((s, p) => s + (Number(p.elapsed_minutes) || 0), 0);
  const masteryAvg = progresses.length
    ? Math.round(progresses.reduce((s, p) => s + (Number(p.mastery_score) || 0), 0) / progresses.length * 10) / 10
    : 0;
  const visibleDays = useMemo(() => {
    const sorted = [...days].sort((a, b) => (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0));
    return (phaseFilter ? sorted.filter((d) => d.phase_key === phaseFilter) : sorted).map((d, idx) => ({ ...d, _idx: idx }));
  }, [days, phaseFilter]);
  const todayIdx = Math.min(
    doneTasks === totalTasks ? visibleDays.length - 1 : Math.floor((doneTasks / Math.max(1, totalTasks)) * visibleDays.length),
    visibleDays.length - 1
  );
  const todayDay = visibleDays[todayIdx] || visibleDays[0];
  const currentPhase = phases.find((p) => p.phase_key === todayDay?.phase_key) || phases[0];
  const currentPhaseLabel = todayDay
    ? `Day ${todayDay.sort_order || (todayIdx + 1)} · ${currentPhase?.title || ""}`
    : "";
  const practiceTouched = practiceState.items.filter((i) => i.mastery_level !== undefined && i.mastery_level !== null);
  const practiceTodayCount = practiceTouched.length;
  const practiceTodayCorrect = practiceTouched.filter((i) => (i.mastery_level || 0) >= 4).length;
  const localToday = (() => {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 10);
  })();
  const checkedToday = studyData?.streak?.last_checkin_date === localToday;

  useEffect(() => {
    const handleKey = (e) => {
      const target = e.target;
      const isInput = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable);

      const TAB_KEY_ORDER = ["today", "plan", "practice", "intro", "star", "a4", "awards"];
      if ((e.metaKey || e.ctrlKey) && !e.altKey && e.key >= "1" && e.key <= "7") {
        e.preventDefault();
        const idx = Number(e.key) - 1;
        setTab(TAB_DEFS[idx]?.key || tab);
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k" && !e.shiftKey) {
        e.preventDefault();
        setPlanMenuOpen(v => !v);
        return;
      }
      if (e.key === "Escape") {
        setPlanMenuOpen(false);
        window.dispatchEvent(new CustomEvent("v3-close-all-drawers"));
        return;
      }
      if (tab === "practice" && !isInput) {
        const cards = document.querySelectorAll(".v3-qa-card");
        if (!cards.length) return;
        let idx = -1;
        cards.forEach((c, i) => { if (c.classList.contains("card-active")) idx = i; });
        if (idx < 0) idx = 0;
        if (e.key === "ArrowDown" || e.key === "Enter" || e.key === "ArrowUp") {
          e.preventDefault();
          const q = cards[idx].querySelector(".v3-qa-q");
          q && q.click();
          return;
        }
        if (["1", "2", "3"].includes(e.key)) {
          e.preventDefault();
          const btns = cards[idx].querySelectorAll(".v3-qa-actions .v3-btn");
          const map = { 1: 0, 2: 1, 3: 2 };
          btns[map[e.key]]?.click();
          return;
        }
        if (e.key === "ArrowRight" || e.key.toLowerCase() === "n") {
          e.preventDefault();
          cards[idx].classList.remove("card-active");
          const next = (idx + 1) % cards.length;
          cards[next].classList.add("card-active");
          cards[next].scrollIntoView({ behavior: "smooth", block: "center" });
          return;
        }
        if (e.key === "ArrowLeft" || e.key.toLowerCase() === "p") {
          e.preventDefault();
          cards[idx].classList.remove("card-active");
          const prev = (idx - 1 + cards.length) % cards.length;
          cards[prev].classList.add("card-active");
          cards[prev].scrollIntoView({ behavior: "smooth", block: "center" });
          return;
        }
      }
      if (tab === "intro" && (e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        const playBtn = document.querySelector(".timer-actions .play");
        const pauseBtn = document.querySelector(".timer-actions .pause");
        (playBtn || pauseBtn)?.click();
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [tab]);

  useEffect(() => {
    if (!planMenuOpen) return;
    const onDocDown = (e) => {
      if (planMenuRef.current && !planMenuRef.current.contains(e.target)) {
        setPlanMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocDown);
    return () => document.removeEventListener("mousedown", onDocDown);
  }, [planMenuOpen]);

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem("v3:practice-filters");
      if (saved) {
        const payload = JSON.parse(saved);
        setPracticeFilters(payload.filters || {});
        setPracticeState(c => ({ ...c, onlyWrong: !!payload.onlyWrong, onlyUnmastered: !!payload.onlyUnmastered }));
      }
    } catch {}
  }, []);

  useEffect(() => {
    try {
      sessionStorage.setItem("v3:practice-filters", JSON.stringify({
        filters: practiceFilters,
        onlyWrong: practiceState.onlyWrong,
        onlyUnmastered: practiceState.onlyUnmastered
      }));
    } catch {}
  }, [practiceFilters, practiceState.onlyWrong, practiceState.onlyUnmastered]);

  useEffect(() => {
    setAwardsLoading(true);
    bootstrap();
    loadStudyData();
  }, []);

  useEffect(() => {
    if (planId) {
      loadPlanDetail(planId);
      loadStudyData();
    }
  }, [planId]);

  useEffect(() => {
    loadPractice();
    loadWrongBook();
  }, [practiceFilters, planId, practiceState.limit, practiceState.offset]);

  useEffect(() => {
    if (!visibleDays.length) return;
    const today = visibleDays[todayIdx] || visibleDays[0];
    const key = today?.day_key || today?.id;
    if (key && openDayKeys.size === 0) {
      setOpenDayKeys(new Set([key]));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleDays.length, todayIdx]);

  async function bootstrap() {
    setLoading(true);
    let list = await api.reviewSite.listPlans();
    if (!Array.isArray(list) || list.length === 0) {
      const imported = await api.reviewSite.runImport({});
      const changed = Number(imported?.plan_count || 0) + Number(imported?.question_count || 0);
      if (changed > 0) {
        addToast("已载入默认 14 天计划和 Interview 资料", "success", 2200);
        list = await api.reviewSite.listPlans();
      }
    }
    setPlans(Array.isArray(list) ? list : []);
    if (Array.isArray(list) && list.length) {
      setPlanId(list[0].id || "");
    } else {
      setLoading(false);
    }
  }

  async function loadPlanDetail(id) {
    setLoading(true);
    try {
      const d = await api.reviewSite.getPlan(id);
      setPlanDetail(normalizePlanDetail(d));
    } finally {
      setLoading(false);
    }
  }

  async function loadPractice() {
    setPracticeState((cur) => ({ ...cur, loading: true }));
    const result = await api.reviewSite.listPracticeQuestions({
      ...practiceFilters,
      limit: practiceState.limit,
      offset: practiceState.offset
    });
    setPracticeState((cur) => ({
      ...cur,
      items: Array.isArray(result?.items) ? result.items : [],
      total: Number(result?.total || 0),
      loading: false
    }));
  }

  async function loadWrongBook() {
    const list = await api.reviewSite.listWrongBook();
    setWrongBook(Array.isArray(list) ? list.slice(0, 5) : []);
  }

  async function loadStudyData() {
    try {
      const [dashboard, achievements] = await Promise.all([
        api.study.dashboard().catch(() => null),
        api.study.achievements().catch(() => null)
      ]);
      setStudyData(dashboard);
      setAwardsData(achievements);
    } catch {
      // 未登录或后端不可用时静默，保持空态
    } finally {
      setAwardsLoading(false);
    }
  }

  async function handleCheckin(payload) {
    if (!planId) {
      addToast("还没有复习计划，请先生成或导入一份计划", "warn");
      return;
    }
    setCheckinBusy(true);
    try {
      const result = await api.reviewSite.checkin(planId, payload);
      const streak = result?.streak || result?.checkin?.streak;
      setStudyData((cur) => ({ ...(cur || {}), streak: streak || cur?.streak }));
      const days = Number(streak?.current_streak || 0);
      addToast(days > 1 ? `打卡成功，已连续 ${days} 天，继续保持！` : "打卡成功，开启新的连续记录", "success", 2600);
      setCelebrate({ msg: `打卡成功！连续 ${days} 天${payload?.note ? ` · ${payload.note}` : ""}`, key: `checkin-${Date.now()}` });
      window.setTimeout(() => setCelebrate(null), 6000);
      await loadStudyData();
    } catch (err) {
      addToast(`打卡失败：${err?.message || "请稍后重试"}`, "error", 3000);
    } finally {
      setCheckinBusy(false);
    }
  }

  function handleUpdateProgress(taskId, merged, offline) {
    setPlanDetail((cur) => {
      const arr = [...(cur.progresses || [])];
      const idx = arr.findIndex((p) => p.task_id === taskId);
      if (merged === null) {
        if (offline) {
          addToast("离线保存，联网后自动同步（简化版：下次刷新会丢失）", "warn");
        }
        return cur;
      }
      if (idx >= 0) arr[idx] = { ...arr[idx], ...merged };
      else arr.push({ task_id: taskId, ...merged });
      return { ...cur, progresses: arr };
    });
    if (merged?.done !== undefined) {
      const today = visibleDays[todayIdx];
      const todayTasks = today?.tasks || [];
      const updatedProgresses = merged === null ? progresses : [...(progresses || [])].map(p => p.task_id === taskId ? ({...p,...merged}) : p);
      const doneNow = todayTasks.filter(t => updatedProgresses.find(p => p.task_id === t.id && p.done)).length;
      const total = todayTasks.length;
      const prevDone = todayDoneRef.current;
      todayDoneRef.current = doneNow;
      if (merged?.done === true && doneNow > prevDone) {
        loadStudyData();
        setTimeout(() => {
          const card = document.querySelector(`[data-task-id="${taskId}"]`);
          card?.classList.add("flash-just-done");
          setTimeout(() => card?.classList.remove("flash-just-done"), 500);
        }, 0);
        if (doneNow === 1 || doneNow % 3 === 0 || doneNow === total) {
          addToast(`今日进度：${doneNow}/${total} 完成${doneNow === total ? " ✦ 全部完成！" : ""}`, "success", 1800);
        }
        if (total > 0 && doneNow === total) {
          const key = `${Date.now()}-${today?.day_key}`;
          setCelebrate({ msg: "你已完成今日全部任务，干得漂亮！", key });
          setTimeout(() => setCelebrate(null), 8500);
        }
      }
    }
  }

  async function handleMarkQuestion(q, payload) {
    const res = await api.reviewSite.markQuestion(q.id, payload);
    if (res === null) {
      addToast("标记失败，已在本地缓存状态（下次刷新会丢失）", "warn");
    } else {
      if (payload.mark_type === "wrong") addToast("已加入错题本", "success", 1600);
      else if (payload.mastery_level === 5) addToast("已标记为掌握", "success", 1400);
      else addToast("已记录题目状态", "success", 1400);
    }
    setPracticeState((cur) => ({
      ...cur,
      items: cur.items.map((it) => (it.id === q.id ? { ...it, ...payload } : it))
    }));
    if (payload.mark_type === "wrong") loadWrongBook();
  }

  async function handleRunImport(payload) {
    setImporting(true);
    addToast("正在导入数据...", "info");
    const result = await api.reviewSite.runImport(payload || {});
    setImporting(false);
    const changed = Number(result?.plan_count || 0) + Number(result?.question_count || 0) + Number(result?.wrong_book_count || 0);
    if (result?.ok || result?.created || result?.plan_id || changed > 0) {
      addToast("导入完成：计划 / 题库 / 自我介绍 / STAR / A4 已就位", "success", 2600);
      await bootstrap();
    } else {
      addToast("导入无变更或未连接后端，使用模拟数据演示界面", "warn", 2600);
      injectMockDemo();
    }
  }

  function injectMockDemo() {
    const mockDays = PHASE_PRESETS.flatMap((ph, pi) =>
      [1, 2, 3, 4].map((d, di) => {
        const idx = pi * 4 + di;
        const phaseKey = ph.key;
        return {
          day_key: `day-${idx + 1}`,
          day_label: `Day ${idx + 1}`,
          phase_key: phaseKey,
          title: `${ph.title} · 第 ${d} 天`,
          acceptance: `完成当日核心任务 ≥ 80%，且笔记 ≥ 3 条，关键产出物已归档。`,
          sort_order: idx + 1,
          tasks: [
            { id: `t${idx}-1`, task_key: `${ph.key}-core-${d}`, title: `${ph.goal} 核心知识点串讲（共 ${2 + di} 节）`, tags: ["理论", pi === 3 ? "simulation" : "critical"], critical: d === 1, simulation: pi === 3, docs: [{ label: "资料链接", url: "#docs" }], sort_order: 1 },
            { id: `t${idx}-2`, task_key: `${ph.key}-practice-${d}`, title: `动手练习：${ph.title} 配套题 ${4 + di} 道`, tags: ["练习"], sort_order: 2 },
            { id: `t${idx}-3`, task_key: `${ph.key}-note-${d}`, title: `写复盘笔记：今日 3 条收获 + 1 条未解决`, tags: ["复盘"], docs: [{ label: "模板", url: "#template" }], sort_order: 3 },
            { id: `t${idx}-4`, task_key: `${ph.key}-quiz-${d}`, title: `小测：关键概念口头复述一遍`, tags: ["小测", "critical"], critical: d === 2, sort_order: 4 }
          ]
        };
      })
    );
    setPlanDetail({
      plan: { id: "demo", title: "默认演示计划（未连接后端）", plan_key: "demo-14", description: "导入失败或后端未启动时的 UI 演示数据，支持完整交互但不会持久化。" },
      phases: PHASE_PRESETS.map((p) => ({ ...p, phase_key: p.key })),
      days: mockDays,
      progresses: [
        { task_id: "t0-1", done: true, note: "笔记：基础阶段从 JS 运行时、React 渲染模型、Node 事件循环三条主线推进。", mastery_score: 4, done_at: new Date().toISOString(), elapsed_minutes: 45 },
        { task_id: "t0-2", done: true, note: "", mastery_score: 3, done_at: new Date().toISOString(), elapsed_minutes: 30 },
        { task_id: "t1-1", done: false, note: "专题深挖：Agent 模式需要对比 ReAct / Plan-and-Execute / Reflection", mastery_score: 2 }
      ],
      intro_scripts: [],
      star_cards: [
        { id: "s1", title: "企业级 RAG 问答平台", tags: ["RAG", "检索增强", "Go"], situation: "企业内部文档分散，员工查不到答案，支持成本高。", task: "构建统一 RAG 平台，覆盖 12+ 业务线，降低 60% 支持工单。", action: "设计向量检索 + 重排 + 分块 + 引用溯源；自研评测集 + Guardrails。", result: "线上答案准确率 92%，NPS 46，月调用量 300w+。", result_pct: 92 },
        { id: "s2", title: "多 Agent 工作流引擎", tags: ["Agent", "Workflow", "Node.js"], situation: "复杂任务需要多个步骤和角色协作，手写 prompt 难以维护。", task: "提供可视化编排 + 可靠执行的多 Agent 引擎。", action: "DAG 编排、上下文记忆、错误重试、工具调用 DSL。", result: "任务成功率 92%，平均迭代周期从 7 天降到 1 天。", result_pct: 88 },
        { id: "s3", title: "面试模拟器桌面端", tags: ["跨端", "Tauri", "AI Native"], situation: "候选人找工作缺少高质量模拟面试，平台产品体验割裂。", task: "交付桌面级一体化面试工作台（对话 + 刷题 + 复习站）。", action: "Tauri + React，本地 + 云端混合架构，流式响应 + 护栏。", result: "内测留存 72%，平均单次使用时长 38 分钟。", result_pct: 85 }
      ],
      a4_memory: [
        { id: "a1", content: "前端：**React 渲染模型** → Fiber / Scheduler / Concurrent Mode；**状态** → 派生状态避免重复，优先 useMemo/useCallback 精确边界。" },
        { id: "a2", content: "服务端：**事件循环** → macrotask / microtask 分层；**性能** → 慢查询 Top-N、索引覆盖、连接池、超时熔断。" },
        { id: "a3", content: "AI：**RAG 质量链** → 分块策略 → Embedding → 检索 Top-K → 重排 → 生成；失败模式：未引用、幻觉、长上下文溢出。" },
        { id: "a4", content: "Agent：**ReAct** 框架；核心保证：工具调用 Schema 校验 + 超时 + 回退 LLM + 成本上限；评测：任务成功率 / 重试次数 / 单步耗时。" }
      ]
    });
  }

  async function handleCreatePlan() {
    if (onOpenPlanner) {
      onOpenPlanner();
      return;
    }
    setCreatingPlan(true);
    const title = window.prompt("计划名称", "我的复习计划");
    if (!title) { setCreatingPlan(false); return; }
    const result = await api.reviewSite.createPlan({ title });
    setCreatingPlan(false);
    if (result?.id) {
      addToast("计划已创建", "success");
      await bootstrap();
      setPlanId(result.id);
    } else {
      addToast("创建失败，打开计划生成器向导填写详细参数", "warn");
      if (onOpenPlanner) onOpenPlanner();
    }
  }

  function scrollToDay(day) {
    if (!day) return;
    setTab("plan");
    setPhaseFilter("");
    setOpenDayKeys(cur => new Set([...cur, day.day_key || day.id]));
    window.setTimeout(() => {
      const ref = dayScrollRefs.current[day.day_key || day.id];
      if (ref) {
        ref.classList.add("highlight-target");
        ref.scrollIntoView({ behavior: "smooth", block: "start" });
        setTimeout(() => ref.classList.remove("highlight-target"), 900);
      }
    }, 80);
  }

  function loadMore() {
    setPracticeState((cur) => ({ ...cur, offset: cur.offset + cur.limit }));
  }

  function randomPick() {
    setPracticeFilters({ category: "", subject: "", difficulty: "", keyword: "" });
    addToast("已重置筛选并随机抽题", "info", 1400);
  }

  function exportA4Text() {
    const all = (planDetail.a4_memory || []).map((it, i) => `${i + 1}. ${it.content || it.text || it.point || ""}`).join("\n");
    const blob = new Blob([`A4 速记要点\n\n${all || "暂无内容"}\n`], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "a4-memory.txt";
    a.click();
    URL.revokeObjectURL(url);
    addToast("A4 速记已导出为文本", "success", 1600);
  }

  function toggleDay(day) {
    const key = day.day_key || day.id;
    if (!key) return;
    setOpenDayKeys((cur) => {
      const next = new Set(cur);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  function collapseAllDays() {
    setCollapsedAll(true);
    setOpenDayKeys(new Set());
  }

  function expandToday() {
    setCollapsedAll(false);
    const today = visibleDays[todayIdx] || visibleDays[0];
    const key = today?.day_key || today?.id;
    setOpenDayKeys(new Set(key ? [key] : []));
  }

  return (
    <section className="review-site v3">
      {celebrate && (
        <div key={celebrate.key} className="v3-celebrate-bar">
          <PartyPopper size={16} /> {celebrate.msg}
        </div>
      )}
      <Toast toasts={toasts} />

      <header className="v3-header">
        <div className="v3-header-left">
          {onBack && (
            <button className="v3-btn ghost icon-only" onClick={onBack} aria-label="返回">
              <ChevronLeft size={16} />
            </button>
          )}
          <h2>面试复习工作台</h2>
          <span className="v3-header-chip">{currentPhaseLabel}</span>
        </div>
        <div className="v3-header-center">
          <button className="v3-plan-menu" onClick={() => setPlanMenuOpen((v) => !v)}>
            <span className="name">{planDetail.plan?.title || "选择复习计划"}</span>
            <span className="key">{planDetail.plan?.plan_key || ""}</span>
            <ChevronDown size={16} style={{ transition: "transform .2s", transform: planMenuOpen ? "rotate(180deg)" : "none" }} />
          </button>
          {planMenuOpen && (
            <div ref={planMenuRef} className="v3-plan-pop">
              {plans.length === 0 && <p style={{ padding: "8px 12px", color: "var(--v3-text-3)", margin: 0 }}>暂无计划，导入或新建一个</p>}
              {plans.map((p) => (
                <div
                  key={p.id}
                  className={`plan-item ${p.id === planId ? "selected" : ""}`}
                  onClick={() => { setPlanId(p.id); setPlanMenuOpen(false); }}
                >
                  <span>{p.title || p.plan_key}</span>
                  <span className="status-chip" style={{ fontSize: 11, color: "var(--v3-text-3)" }}>{p.status || "draft"}</span>
                </div>
              ))}
              <div className="plan-divider" />
              <button className="plan-action" onClick={() => { onOpenPlanner ? onOpenPlanner() : handleCreatePlan(); setPlanMenuOpen(false); }}>
                <span><Plus size={14} /> 新建计划</span>
              </button>
              <button className="plan-action" onClick={() => { handleRunImport({}); setPlanMenuOpen(false); }}>
                <span><Upload size={14} /> 导入示例数据</span>
              </button>
            </div>
          )}
        </div>
        <div className="v3-header-right">
          <button
            className="v3-btn ghost icon-only"
            title="导入示例数据（计划 / 题库 / STAR / A4）"
            aria-label="导入示例数据"
            disabled={importing}
            onClick={() => handleRunImport({})}
          >
            {importing ? <Loader2 size={15} className="v3-spin" /> : <Upload size={15} />}
          </button>
          <button className="v3-btn primary" onClick={() => (onOpenPlanner ? onOpenPlanner() : handleCreatePlan())} disabled={creatingPlan}>
            <Plus size={14} /> 新建计划
          </button>
        </div>
      </header>

      <div className="v3-tab-bar">
        {TAB_DEFS.map((t) => (
          <button key={t.key} className={`v3-tab ${tab === t.key ? "active" : ""}`} onClick={() => setTab(t.key)}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      <div className="rs-body">
        {loading && !days.length ? (
          <div style={{ display: "grid", gap: 12 }}>
            <div className="skeleton" style={{ height: 140 }} />
            <div className="skeleton" style={{ height: 180 }} />
            <div className="skeleton" style={{ height: 240 }} />
          </div>
        ) : (!plans.length && !days.length) ? (
          <div className="empty-state v3-empty">
            <svg className="v3-empty-illust" viewBox="0 0 200 140" fill="none">
              <rect x="30" y="20" width="80" height="100" rx="8" stroke="#c7d7d1" strokeWidth="1.5" />
              <rect x="42" y="36" width="56" height="6" rx="3" fill="#8da19a" />
              <rect x="42" y="50" width="44" height="5" rx="2.5" fill="#d9e5df" />
              <rect x="42" y="62" width="40" height="5" rx="2.5" fill="#d9e5df" />
              <rect x="42" y="74" width="50" height="5" rx="2.5" fill="#d9e5df" />
              <rect x="42" y="90" width="28" height="12" rx="3" fill="#2f63e8" opacity=".85"/>
              <circle cx="156" cy="52" r="22" stroke="#8da19a" strokeWidth="1.5" fill="#f7faf8"/>
              <path d="M148 52 l6 6 l14-14" stroke="#2f63e8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M120 108 l12-8 l12 6 l10-10 l12 10" stroke="#0f8f8f" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
              <path d="M30 114 h140" stroke="#c7d7d1" strokeWidth="1.5" strokeDasharray="4 4"/>
            </svg>
            <h4>还没有复习计划</h4>
            <p>导入默认模板体验完整界面（14 天四阶段 + 刷题 + STAR 卡 + A4 速记），或者使用计划生成器定制你的专属节奏。</p>
            <div>
              <button className="v3-btn primary cta-pulse" disabled={importing} onClick={() => handleRunImport({})}>
                {importing ? <Loader2 size={14} className="v3-spin" /> : <Upload size={14} />} 导入示例数据
              </button>
              <button className="v3-btn ghost" onClick={() => (onOpenPlanner ? onOpenPlanner() : handleCreatePlan())}>
                <Wand2 size={14} /> 用生成器定制
              </button>
            </div>
          </div>
        ) : tab === "today" ? (
          <TodayView
            planDetail={planDetail}
            phases={phases}
            days={days}
            progresses={progresses}
            todayIdx={todayIdx}
            visibleDays={visibleDays}
            totalTasks={totalTasks}
            doneTasks={doneTasks}
            totalMinutes={totalMinutes}
            masteryAvg={masteryAvg}
            wrongBook={wrongBook}
            onUpdateProgress={handleUpdateProgress}
            setTab={setTab}
            setPhaseFilter={setPhaseFilter}
            scrollToDay={scrollToDay}
            streak={studyData?.streak}
            checkedToday={checkedToday}
            checkinBusy={checkinBusy}
            onCheckin={handleCheckin}
          />
        ) : tab === "awards" ? (
          <AwardsWall data={awardsData} loading={awardsLoading} />
        ) : tab === "plan" ? (
          <>
            <div className="v3-filter-bar">
              <div className="v3-filter-chips">
                <button className={`v3-chip toggle ${phaseFilter === "" ? "on" : ""}`} onClick={() => setPhaseFilter("")}>
                  <Target size={12} /> 全部阶段
                </button>
                {phases.map((ph, i) => (
                  <button
                    key={ph.phase_key || i}
                    className={`v3-chip toggle ${phaseFilter === ph.phase_key ? "on" : ""}`}
                    onClick={() => setPhaseFilter(ph.phase_key)}
                  >
                    {ph.title || ph.phase_key}
                  </button>
                ))}
                <div className="v3-toolbar-actions">
                  <button className="v3-btn ghost small" onClick={collapseAllDays}>
                    <ChevronDown size={13} /> 折叠全部
                  </button>
                  <button className="v3-btn ghost small" onClick={expandToday}>
                    展开今天
                  </button>
                </div>
              </div>
            </div>
            {visibleDays.length === 0 ? (
              <div className="empty-state v3-empty">
                <svg className="v3-empty-illust" viewBox="0 0 200 140" fill="none">
                  <rect x="30" y="20" width="80" height="100" rx="8" stroke="#c7d7d1" strokeWidth="1.5" />
                  <rect x="42" y="36" width="56" height="6" rx="3" fill="#8da19a" />
                  <rect x="42" y="50" width="44" height="5" rx="2.5" fill="#d9e5df" />
                  <rect x="42" y="62" width="40" height="5" rx="2.5" fill="#d9e5df" />
                  <rect x="42" y="74" width="50" height="5" rx="2.5" fill="#d9e5df" />
                  <rect x="42" y="90" width="28" height="12" rx="3" fill="#2f63e8" opacity=".85"/>
                  <circle cx="156" cy="52" r="22" stroke="#8da19a" strokeWidth="1.5" fill="#f7faf8"/>
                  <path d="M148 52 l6 6 l14-14" stroke="#2f63e8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d="M120 108 l12-8 l12 6 l10-10 l12 10" stroke="#0f8f8f" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
                  <path d="M30 114 h140" stroke="#c7d7d1" strokeWidth="1.5" strokeDasharray="4 4"/>
                </svg>
                <h4>暂无打卡任务</h4>
                <p>当前阶段下还没有安排任务，切换阶段或导入默认计划开始体验。</p>
                <div>
                  <button className="v3-btn primary" onClick={() => handleRunImport({})}>
                    <Upload size={14} /> 导入示例数据
                  </button>
                </div>
              </div>
            ) : visibleDays.map((day) => (
              <V3PhaseDayCard
                key={day.day_key || day.id || day._idx}
                day={day}
                phases={phases}
                progresses={progresses}
                onUpdateProgress={handleUpdateProgress}
                isToday={day._idx === todayIdx}
                open={openDayKeys.has(day.day_key || day.id)}
                onToggle={toggleDay}
                scrollRef={(el) => { if (el) dayScrollRefs.current[day.day_key || day.id] = el; }}
              />
            ))}
          </>
        ) : tab === "practice" ? (
          <>
            <V3FilterToolbar
              filters={practiceFilters}
              setFilters={setPracticeFilters}
              onRefresh={loadPractice}
              onShuffle={randomPick}
              loading={practiceState.loading}
              onlyWrong={practiceState.onlyWrong}
              setOnlyWrong={(v) => { setPracticeState((c) => ({ ...c, onlyWrong: v })); }}
              onlyUnmastered={practiceState.onlyUnmastered}
              setOnlyUnmastered={(v) => { setPracticeState((c) => ({ ...c, onlyUnmastered: v })); }}
              todayCount={practiceTodayCount}
              todayCorrect={practiceTodayCorrect}
            />
            <div className="v3-stat-grid">
              <V3Stat icon={<BookOpen size={17} />} label="题库总量" value={practiceState.total || 0} />
              <V3Stat icon={<Check size={17} />} label="累计作答" value={studyData?.practice?.total_attempts ?? 0} />
              <V3Stat icon={<Flame size={17} />} label="本周作答" value={studyData?.practice?.week_attempts ?? practiceTodayCount} />
              <V3Stat icon={<Target size={17} />} label="错题待清" value={studyData?.practice?.wrong_book_count ?? wrongBook.length} />
            </div>
            <div style={{ display: "grid", gap: 8 }}>
              {(practiceState.items?.length ? practiceState.items : samplePracticeQuestions()).map((q) => (
                <V3QaCard key={q.id || q.question_id} q={q} onMark={handleMarkQuestion} />
              ))}
            </div>
            {practiceState.items.length > 0 && (practiceState.offset + practiceState.limit) < practiceState.total && (
              <button className="load-more" onClick={loadMore} disabled={practiceState.loading}>
                {practiceState.loading ? <Loader2 size={15} className="v3-spin" /> : <ChevronRight size={15} />} 加载更多
              </button>
            )}
          </>
        ) : tab === "intro" ? (
          <>
            <MaterialManager kind="intro_scripts" planId={planId} items={planDetail.intro_scripts} onSaved={() => loadPlanDetail(planId)} addToast={addToast} />
            <IntroPlayer scripts={planDetail.intro_scripts} onRunImport={() => handleRunImport({})} addToast={addToast} />
          </>
        ) : tab === "star" ? (
          <>
            <MaterialManager kind="star_cards" planId={planId} items={planDetail.star_cards} onSaved={() => loadPlanDetail(planId)} addToast={addToast} />
            <div className="star-grid">
            {(planDetail.star_cards?.length ? planDetail.star_cards : sampleStarCards()).map((c, i) => (
              <V3StarCard key={c.id || c.key || i} card={c} />
            ))}
          </div>
          </>
        ) : tab === "a4" ? (
          <>
            <div className="a4-actions">
              <MaterialManager kind="a4_memory" planId={planId} items={planDetail.a4_memory} onSaved={() => loadPlanDetail(planId)} addToast={addToast} />
              <button className="v3-btn ghost" onClick={() => window.print()}>
                <Printer size={14} /> 打印
              </button>
              <button className="v3-btn ghost" onClick={exportA4Text}>
                <Download size={14} /> 导出文本
              </button>
            </div>
            <div className="a4-grid">
              <A4FaceCard
                side="A"
                title="A 面 · 知识主干"
                items={(() => {
                  const items = planDetail.a4_memory || [];
                  const hasSide = items.some((it) => it.side === "A" || it.side === "B");
                  return hasSide ? items.filter((it) => it.side === "A" || it.side === "ALL") : items.filter((_, i) => i % 2 === 0);
                })()}
              />
              <A4FaceCard
                side="B"
                title="B 面 · 实战要点"
                items={(() => {
                  const items = planDetail.a4_memory || [];
                  const hasSide = items.some((it) => it.side === "A" || it.side === "B");
                  return hasSide ? items.filter((it) => it.side === "B" || it.side === "ALL") : items.filter((_, i) => i % 2 === 1);
                })()}
              />
            </div>
          </>
        ) : null}
      </div>
      <div className="v3-kbd-hint">
        快捷键：<kbd>⌘</kbd><kbd>1~7</kbd> 切 Tab · <kbd>⌘</kbd><kbd>K</kbd> 计划菜单 · <kbd>Esc</kbd> 关闭弹层<br/>
        刷题：<kbd>1/2/3</kbd> 打标 · <kbd>→/←</kbd> 切题 · <kbd>↵</kbd> 展开
      </div>
    </section>
  );
}

function samplePracticeQuestions() {
  return [
    { id: "demo-q1", category: "ai_application", subject: "rag", difficulty: "hard", question_type: "简答", prompt: "请说明 RAG 中 chunk 策略（大小 / 重叠 / 语义块）对检索召回率与生成质量的影响，并给出你认为的默认策略。", answer: "建议：默认 512 tokens / 64 overlap；技术文档用语义切分；配合重排器和 Top-K 动态调整。", answer_detail: "小 chunk 更精确但上下文不足；大 chunk 噪声高。生产常使用混合策略 + 父子块。", mastery_level: 0 },
    { id: "demo-q2", category: "internet", subject: "frontend", difficulty: "medium", question_type: "代码", prompt: "React 18 并发模式下 useEffect 为什么会双调用？如何在开发 / 生产下规避不必要副作用？", answer: "StrictMode 双调用帮助检测不纯；生产只执行一次；副作用应可重入或使用 ref 作为开关。", code: "useEffect(() => {\n  let alive = true;\n  fetch('/x').then(r => alive && setData(r));\n  return () => { alive = false; };\n}, []);", mastery_level: 3 },
    { id: "demo-q3", category: "leetcode", subject: "algorithm", difficulty: "medium", question_type: "算法", prompt: "无重复字符的最长子串，时间 O(n) 解法请口述实现。", answer: "滑动窗口 + hashmap 存下标；左边界取 max(left, map[c] + 1)，维护最大长度。" }
  ];
}

function sampleStarCards() {
  return [
    { id: "d1", title: "企业级 RAG 问答平台", tags: ["RAG", "Go", "多租户"], situation: "企业文档分散，员工找不到答案。", task: "统一 RAG 平台，覆盖 12+ 业务。", action: "向量检索 + 重排 + Guardrails。", result: "准确率 92%，月调用 300w+。", result_pct: 92 },
    { id: "d2", title: "多 Agent 协作工作流引擎", tags: ["Agent", "DAG"], situation: "复杂任务多个步骤和角色协作，手写 prompt 难维护。", task: "提供可视化编排 + 可靠执行的多 Agent 引擎。", action: "DAG 编排 / 上下文记忆 / 工具调用 DSL / 错误重试。", result: "任务成功率 92%，迭代从 7 天降到 1 天。", result_pct: 88 }
  ];
}
