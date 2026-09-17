import { useState } from "react";
import {
  Award, BookOpen, Check, ChevronRight, Clock, ExternalLink, FileText, Flame,
  Gauge, Loader2, Mic, NotebookPen, Sparkles, Star as StarIcon, Target, Trophy, Zap
} from "lucide-react";
import { getInterviewAgentClient } from "../../apiClient";
import { V3Stat } from "./ReviewSiteComponents";

const api = getInterviewAgentClient();

function V3MasteryStars({ value = 0, onChange, disabled }) {
  return (
    <div className="v3-stars" onClick={(event) => event.stopPropagation()}>
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

function V3TaskCard({ task, progress, onUpdate, onOpen }) {
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
    <div
      className={`v3-task-card ${local.done ? "done" : ""}`}
      data-task-id={task.id}
      role="button"
      tabIndex={0}
      aria-label={`查看任务详情：${task.title || "未命名任务"}`}
      onClick={() => onOpen?.(task, local)}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen?.(task, local);
        }
      }}
    >
      <input
        type="checkbox"
        className="v3-task-checkbox"
        checked={local.done}
        onChange={toggleDone}
        onClick={(event) => event.stopPropagation()}
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
            onClick={(event) => { event.stopPropagation(); setNoteOpen((v) => !v); }}
            title="笔记"
            aria-label="笔记"
          >
            <FileText size={13} />
          </button>
          {Array.isArray(task.docs) && task.docs.length > 0 && task.docs.slice(0, 1).map((doc, i) => {
            const href = safeTaskDocHref(typeof doc === "string" ? doc : doc?.url || doc?.link);
            const label = typeof doc === "string" ? "资料" : doc?.label || doc?.title || "资料";
            return href ? (
              <a key={i} className="v3-chip doc" href={href} target="_blank" rel="noopener noreferrer" onClick={(event) => event.stopPropagation()}>
                <ExternalLink size={10} /> {label}
              </a>
            ) : null;
          })}
        </div>
        {noteOpen && (
          <div className="v3-task-note">
            <textarea
              value={local.note}
              onChange={onNoteChange}
              onClick={(event) => event.stopPropagation()}
              placeholder="笔记、踩坑、要点..."
            />
          </div>
        )}
      </div>
      <ChevronRight size={16} className="v3-task-open" aria-hidden="true" />
    </div>
  );
}

function safeTaskDocHref(value) {
  try {
    const parsed = new URL(String(value || ""));
    return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : "";
  } catch {
    return "";
  }
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

export function AwardsWall({ data, loading }) {
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

export function TodayView({ planDetail, phases, days, progresses, todayIdx, visibleDays, totalTasks, doneTasks, totalMinutes, masteryAvg, wrongBook, onUpdateProgress, onOpenTask, setTab, setPhaseFilter, scrollToDay, streak, checkedToday, checkinBusy, onCheckin }) {
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
              onOpen={(selectedTask, local) => onOpenTask?.(selectedTask, todayDay, local)}
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

export function PhaseRoadmap({ phases, days, progresses, activePhaseKey, onSelectPhase }) {
  const normalizedPhases = (phases || []).filter(Boolean);
  if (!normalizedPhases.length || !days?.length) return null;
  return (
    <div className="v3-phase-roadmap">
      {normalizedPhases.slice(0, 4).map((phase, index) => {
        const phaseKey = phase.phase_key || phase.key || phase.id;
        const phaseDays = days.filter((day) => day.phase_key === phaseKey);
        const phaseTasks = phaseDays.flatMap((day) => day.tasks || []);
        const done = phaseTasks.filter((task) => progresses.find((progress) => progress.task_id === task.id && progress.done)).length;
        const pct = phaseTasks.length ? Math.round((done / phaseTasks.length) * 100) : 0;
        const range = phase.range_label || phase.range || `Day ${phaseDays[0]?.sort_order || index + 1}`;
        const isActive = activePhaseKey === phaseKey;
        return (
          <button
            type="button"
            key={phaseKey || index}
            className={`v3-phase-route-card p${index + 1} ${isActive ? "active" : ""}`}
            onClick={() => onSelectPhase?.(phaseKey || "")}
          >
            <div className="v3-phase-route-top">
              <span className={`v3-phase-pill p${index + 1}`}>{range}</span>
              <strong>{pct}%</strong>
            </div>
            <h4>{phase.title || phaseKey || `阶段 ${index + 1}`}</h4>
            <p>{phase.goal || "完成该阶段复习任务"}</p>
            <small>{done}/{phaseTasks.length} 个任务</small>
            <div className="v3-phase-progress" aria-hidden="true">
              <span style={{ width: `${pct}%` }} />
            </div>
          </button>
        );
      })}
    </div>
  );
}

export function DayCompletionStrip({ days, progresses, todayIdx, activeDayKey, onSelectDay }) {
  if (!days?.length) return null;
  return (
    <div className="v3-day-strip-panel">
      <div className="v3-section-head compact">
        <h4>14 天完成度</h4>
        <span className="v3-chip">点击跳到当天</span>
      </div>
      <div className="v3-day-strip">
        {days.map((day, index) => {
          const tasks = day.tasks || [];
          const done = tasks.filter((task) => progresses.find((progress) => progress.task_id === task.id && progress.done)).length;
          const pct = tasks.length ? Math.round((done / tasks.length) * 100) : 0;
          const phaseIndex = phaseIndexFromKey(day.phase_key, index);
          const dayKey = day.day_key || day.id || "";
          const isActive = activeDayKey === dayKey;
          return (
            <button
              type="button"
              key={day.day_key || day.id || index}
              className={`v3-day-cell p${phaseIndex} ${pct === 100 ? "done" : ""} ${index === todayIdx ? "today" : ""} ${isActive ? "active" : ""}`}
              onClick={() => onSelectDay?.(day)}
              title={`${day.day_label || `Day ${index + 1}`} · ${day.title || ""} · ${done}/${tasks.length}`}
            >
              <span className="fill" style={{ height: `${pct}%` }} />
              <strong>{day.day_label || `D${index + 1}`}</strong>
              <span>{done}/{tasks.length}</span>
              <em>{pct}%</em>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function V3PhaseDayCard({ day, phases, progresses, onUpdateProgress, onOpenTask, isToday, scrollRef, open, onToggle }) {
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
              onOpen={(selectedTask, local) => onOpenTask?.(selectedTask, day, local)}
            />
          ))}
        </div>
      </div>
    </details>
  );
}

function phaseIndexFromKey(phaseKey, fallbackIndex) {
  const match = String(phaseKey || "").match(/(\d+)/);
  if (match) return Math.max(1, Math.min(4, Number(match[1])));
  return Math.max(1, Math.min(4, Math.floor(fallbackIndex / 4) + 1));
}
