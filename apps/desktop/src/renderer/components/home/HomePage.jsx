import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  BookOpenCheck,
  CalendarCheck2,
  ClipboardList,
  Flame,
  Loader2,
  MessageSquarePlus,
  PenLine,
  PlayCircle,
  RefreshCw,
  Sparkles,
  Target,
  Trophy,
  Wand2
} from "lucide-react";
import { getInterviewAgentClient } from "../../apiClient";

const api = getInterviewAgentClient();

function formatMinutes(minutes) {
  const value = Number(minutes || 0);
  if (value < 60) return `${value}分`;
  const h = Math.floor(value / 60);
  const m = value % 60;
  return m ? `${h}小时${m}分` : `${h}小时`;
}

export function HomePage({ account, profile, onRequireAuth, onNavigate, onStartInterview, onOpenSession }) {
  const [state, setState] = useState({ status: "idle", data: null, error: "" });
  const [taskLinks, setTaskLinks] = useState({});
  const [busyTask, setBusyTask] = useState("");
  const [checkingIn, setCheckingIn] = useState(false);

  const load = useCallback(async () => {
    if (!account) {
      setState({ status: "idle", data: null, error: "" });
      return;
    }
    setState((current) => ({ ...current, status: "loading", error: "" }));
    try {
      const data = await api.study.dashboard();
      setState({ status: "ready", data, error: "" });
      const planId = data?.today?.plan_id || data?.plan?.active_plan_id;
      if (planId) {
        try {
          const detail = await api.reviewSite.getPlan(planId);
          const linkMap = {};
          for (const day of detail.days || []) {
            for (const task of day.tasks || []) {
              linkMap[task.id] = task;
            }
          }
          setTaskLinks(linkMap);
        } catch (_error) {
          setTaskLinks({});
        }
      }
    } catch (error) {
      setState({ status: "error", data: null, error: error?.message || "驾驶舱数据加载失败" });
    }
  }, [account]);

  useEffect(() => {
    load();
  }, [load]);

  const streak = state.data?.streak;
  const today = state.data?.today;
  const plan = state.data?.plan;
  const minutes = state.data?.study_minutes;
  const interviews = state.data?.interviews;
  const practice = state.data?.practice;
  const advice = state.data?.advice;
  const weakPoints = state.data?.weak_points || [];
  const checkedToday = Boolean(today?.tasks_done > 0 || today?.elapsed_minutes > 0);

  const tasks = useMemo(() => {
    const list = Array.isArray(today?.tasks) ? today.tasks : [];
    return [...list].sort((a, b) => Number(a.sort_order || 0) - Number(b.sort_order || 0));
  }, [today]);

  async function handleCheckin() {
    if (!account) return onRequireAuth?.();
    const planId = today?.plan_id || plan?.active_plan_id;
    if (!planId) {
      onNavigate?.("planner");
      return;
    }
    setCheckingIn(true);
    try {
      await api.reviewSite.checkin(planId, {});
      await load();
    } catch (error) {
      window.alert(`打卡失败：${error?.message || "请确认计划已激活并设置开始日期"}`);
    } finally {
      setCheckingIn(false);
    }
  }

  async function toggleTask(task) {
    if (!account) return onRequireAuth?.();
    setBusyTask(task.id);
    try {
      await api.reviewSite.patchProgress(task.id, { done: !task.done });
      await load();
    } catch (error) {
      window.alert(`任务更新失败：${error?.message || "未知错误"}`);
    } finally {
      setBusyTask("");
    }
  }

  function handleTaskAction(task) {
    if (!account) return onRequireAuth?.();
    const link = taskLinks[task.id];
    const linkType = link?.link_type || link?.simulation ? "interview" : "";
    if (linkType === "interview" || link?.simulation) {
      const payload = link?.link_payload || {};
      onStartInterview?.(payload.focus || `开始「${task.title}」模拟面试`, {
        plan_task_id: task.id,
        mode: payload.mode || profile?.mode || "interviewer"
      });
      return;
    }
    if (linkType === "practice") {
      onNavigate?.("practice");
      return;
    }
    if (linkType === "knowledge") {
      onNavigate?.("review-site");
      return;
    }
    onNavigate?.("review-site");
  }

  if (!account) {
    return (
      <div className="home-page">
        <div className="home-guest card-v3">
          <div className="home-guest-icon"><Sparkles size={26} /></div>
          <h3>登录后开启你的备考驾驶舱</h3>
          <p>连续打卡、今日任务、面试报告、刷题正确率和 AI 建议都会在这里汇总。</p>
          <button type="button" className="btn-primary-v3" onClick={() => onRequireAuth?.()}>
            登录 / 注册 <ArrowRight size={15} />
          </button>
        </div>
      </div>
    );
  }

  if (state.status === "loading" && !state.data) {
    return (
      <div className="home-page">
        <div className="home-loading">
          <Loader2 size={22} className="spin" /> 正在汇总今日学习数据…
        </div>
      </div>
    );
  }

  if (state.status === "error" && !state.data) {
    return (
      <div className="home-page">
        <div className="home-error card-v3">
          <h3>驾驶舱数据加载失败</h3>
          <p>{state.error}</p>
          <button type="button" className="btn-ghost-v3" onClick={load}>
            <RefreshCw size={14} /> 重试
          </button>
        </div>
      </div>
    );
  }

  const planRate = Math.round(Number(plan?.completion_rate || 0) * 100);
  const todayPct = today?.total_tasks ? Math.round((today.tasks_done / today.total_tasks) * 100) : 0;

  return (
    <div className="home-page">
      <div className="home-hero">
        <section className="home-streak card-v3">
          <div className="home-streak-flame">
            <Flame size={30} />
          </div>
          <div className="home-streak-main">
            <small>连续打卡</small>
            <strong>{streak?.current_streak || 0} 天</strong>
            <span>最长 {streak?.longest_streak || 0} 天 · 累计 {streak?.total_checkin_days || 0} 天</span>
          </div>
          <button
            type="button"
            className={checkedToday ? "btn-ghost-v3 checked" : "btn-primary-v3"}
            onClick={handleCheckin}
            disabled={checkingIn}
          >
            {checkingIn ? <Loader2 size={15} className="spin" /> : <CalendarCheck2 size={15} />}
            {checkedToday ? "今日已打卡" : "今日打卡"}
          </button>
        </section>

        <section className="home-advice card-v3">
          <div className="home-advice-head">
            <span className="home-advice-icon"><Sparkles size={15} /></span>
            <strong>AI 今日建议</strong>
            {advice?.source === "llm" && <span className="v3-chip">个性化</span>}
          </div>
          <p>{advice?.text || "完成一场模拟面试或一组刷题，让系统为你定位水平。"}</p>
          {advice?.action && (
            <button type="button" className="home-advice-action" onClick={() => {
              if (advice.action.includes("面试")) onNavigate?.("chat");
              else if (advice.action.includes("题") || advice.action.includes("专攻")) onNavigate?.("practice");
              else if (advice.action.includes("任务") || advice.action.includes("打卡")) onNavigate?.("review-site");
              else onNavigate?.("review-site");
            }}>
              {advice.action} <ArrowRight size={13} />
            </button>
          )}
        </section>
      </div>

      <section className="home-today card-v3">
        <div className="home-section-head">
          <div>
            <h3>今日任务</h3>
            <p>{today?.plan_title ? `来自计划「${today.plan_title}」` : "还没有进行中的复习计划"}</p>
          </div>
          <div className="home-today-summary">
            <span>{today?.tasks_done || 0}/{today?.total_tasks || 0} 完成</span>
            <div className="home-progress-bar">
              <div style={{ width: `${todayPct}%` }} />
            </div>
          </div>
        </div>
        {tasks.length === 0 ? (
          <div className="home-empty-tasks">
            <p>今天没有安排任务。生成一个计划，或直接开始一场模拟面试。</p>
            <div className="home-empty-actions">
              <button type="button" className="btn-primary-v3" onClick={() => onNavigate?.("planner")}>
                <Wand2 size={14} /> 生成复习计划
              </button>
              <button type="button" className="btn-ghost-v3" onClick={() => onStartInterview?.("", {})}>
                <MessageSquarePlus size={14} /> 直接开始面试
              </button>
            </div>
          </div>
        ) : (
          <ul className="home-task-list">
            {tasks.map((task) => {
              const link = taskLinks[task.id];
              const actionable = Boolean(link?.link_type && link.link_type !== "none") || Boolean(link?.simulation);
              return (
                <li key={task.id} className={`home-task ${task.done ? "done" : ""}`}>
                  <button
                    type="button"
                    className="home-task-check"
                    onClick={() => toggleTask(task)}
                    disabled={Boolean(busyTask)}
                    aria-label={task.done ? "标记未完成" : "标记完成"}
                  >
                    {busyTask === task.id ? <Loader2 size={14} className="spin" /> : task.done ? "✓" : ""}
                  </button>
                  <div className="home-task-body">
                    <strong>
                      {task.title}
                      {task.critical && <span className="home-task-critical">重点</span>}
                    </strong>
                    <span className="home-task-meta">
                      {(task.tags || []).slice(0, 3).map((tag) => <i key={tag}>{tag}</i>)}
                      {link?.reason && <em>{link.reason}</em>}
                    </span>
                  </div>
                  {actionable && (
                    <button type="button" className="home-task-go" onClick={() => handleTaskAction(task)}>
                      {link?.link_type === "interview" || link?.simulation ? (
                        <><PlayCircle size={14} /> 模拟</>
                      ) : link?.link_type === "practice" ? (
                        <><PenLine size={14} /> 去刷</>
                      ) : (
                        <><BookOpenCheck size={14} /> 去看</>
                      )}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <div className="home-quick">
        <QuickAction icon={<MessageSquarePlus size={17} />} label="模拟面试" desc="AI 面试官 / 候选人" onClick={() => (account ? onStartInterview?.("", {}) : onRequireAuth?.())} />
        <QuickAction icon={<PenLine size={17} />} label="刷题训练" desc="题库作答 · 错题本" onClick={() => onNavigate?.("practice")} />
        <QuickAction icon={<CalendarCheck2 size={17} />} label="复习站" desc="计划 · 打卡 · 素材" onClick={() => onNavigate?.("review-site")} />
        <QuickAction icon={<Wand2 size={17} />} label="计划生成" desc="AI 定制复习计划" onClick={() => onNavigate?.("planner")} />
      </div>

      <div className="home-stat-grid">
        <StatCard icon={<Target size={16} />} label="今日学习" value={formatMinutes(minutes?.today_minutes)} sub={`本周 ${formatMinutes(minutes?.week_minutes)}`} />
        <StatCard icon={<ClipboardList size={16} />} label="面试报告" value={`${interviews?.total_reports || 0} 份`} sub={interviews?.latest_score != null ? `最新 ${interviews.latest_score} 分` : "暂无评分"} onClick={() => onNavigate?.("reports")} />
        <StatCard icon={<PenLine size={16} />} label="今日刷题" value={`${practice?.today_attempts || 0} 题`} sub={practice?.total_attempts ? `正确率 ${Math.round(Number(practice.correct_rate || 0) * 100)}%` : "暂无作答"} onClick={() => onNavigate?.("practice")} />
        <StatCard icon={<Trophy size={16} />} label="计划进度" value={`${planRate}%`} sub={`${plan?.tasks_done || 0}/${plan?.total_tasks || 0} 任务`} onClick={() => onNavigate?.("review-site")} />
      </div>

      {weakPoints.length > 0 && (
        <section className="home-weak card-v3">
          <h3>高频薄弱项</h3>
          <div className="home-weak-chips">
            {weakPoints.map((item) => (
              <button key={item.tag} type="button" className="v3-chip weak" onClick={() => onNavigate?.("practice")}>
                {item.tag} · {item.count} 次
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function QuickAction({ icon, label, desc, onClick }) {
  return (
    <button type="button" className="home-quick-item card-v3" onClick={onClick}>
      <span className="home-quick-icon">{icon}</span>
      <strong>{label}</strong>
      <small>{desc}</small>
    </button>
  );
}

function StatCard({ icon, label, value, sub, onClick }) {
  const Comp = onClick ? "button" : "div";
  return (
    <Comp type={onClick ? "button" : undefined} className="home-stat card-v3" onClick={onClick}>
      <span className="home-stat-icon">{icon}</span>
      <small>{label}</small>
      <strong>{value}</strong>
      <em>{sub}</em>
    </Comp>
  );
}
