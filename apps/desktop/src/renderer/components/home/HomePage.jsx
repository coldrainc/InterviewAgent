import { useMemo, useState } from "react";
import {
  ArrowRight,
  CalendarCheck2,
  Flame,
  Loader2,
  MessageSquarePlus,
  PenLine,
  RefreshCw,
  Sparkles,
  Wand2
} from "lucide-react";
import { getInterviewAgentClient } from "../../apiClient";
import { TodayOverview } from "../../features/today/TodayOverview";
import { TodayTaskList } from "../../features/today/TodayTaskList";
import { useTodayDashboard } from "../../features/today/useTodayDashboard";
import { taskTarget } from "../../features/today/taskTarget";
import { normalizeDesktopError } from "../../utils/interview";

const api = getInterviewAgentClient();

export function HomePage({ account, profile, onRequireAuth, onNavigate, onStartInterview }) {
  const state = useTodayDashboard(account);
  const [busyTask, setBusyTask] = useState("");
  const [checkingIn, setCheckingIn] = useState(false);
  const data = state.data || {};
  const readOnly = state.status === "offline";
  const today = data.today;
  const tasks = useMemo(
    () => [...(Array.isArray(today?.tasks) ? today.tasks : [])].sort(
      (a, b) => Number(a.sort_order || 0) - Number(b.sort_order || 0)
    ),
    [today]
  );

  async function handleCheckin() {
    if (!account) return onRequireAuth?.();
    const planId = today?.plan_id || data.plan?.active_plan_id;
    if (!planId) return onNavigate?.("planner");
    setCheckingIn(true);
    try {
      await api.reviewSite.checkin(planId, { elapsed_minutes: 15, note: "今日驾驶舱打卡" });
      await state.reload();
    } catch (error) {
      window.alert(`打卡失败：${normalizeDesktopError(error, "请确认计划已激活并设置开始日期。")}`);
    } finally {
      setCheckingIn(false);
    }
  }

  async function toggleTask(task) {
    if (!account) return onRequireAuth?.();
    setBusyTask(task.id);
    try {
      const result = await api.learning.command(task.id, {
        action: task.done ? "reopen" : "complete",
        expected_version: task.version,
        evidence: task.done ? {} : { source: "today_workspace" }
      });
      await state.reload();
      if (!result?.receipt?.accepted) {
        window.alert(result?.receipt?.verification?.reason || "该任务还没有满足完成条件，请先执行任务。");
      }
    } catch (error) {
      await state.reload();
      window.alert(`任务更新失败：${normalizeDesktopError(error, "任务可能已在其他设备更新，请重试。")}`);
    } finally {
      setBusyTask("");
    }
  }

  async function startTask(task, openAfterStart = false) {
    if (!account) return onRequireAuth?.();
    setBusyTask(task.id);
    try {
      await api.learning.command(task.id, { action: "start", expected_version: task.version });
      await state.reload();
    } catch (error) {
      await state.reload();
      window.alert(`任务启动失败：${normalizeDesktopError(error, "请稍后重试。")}`);
      setBusyTask("");
      return;
    }
    setBusyTask("");
    if (openAfterStart) openTask(task);
  }

  function openTask(task) {
    if (!account) return onRequireAuth?.();
    const { screen, payload } = taskTarget(task);
    if (task.task_type === "interview") {
      onStartInterview?.(payload.focus || `开始「${task.title}」模拟面试`, {
        plan_task_id: payload.task_id || task.id,
        mode: payload.mode || profile?.mode || "interviewer"
      });
    } else {
      onNavigate?.(screen, payload);
    }
  }

  if (!account) return <Guest onRequireAuth={onRequireAuth} />;
  if (state.status === "loading" && !state.data) return <Status icon={<Loader2 size={22} className="spin" />} text="正在汇总今日学习数据…" />;
  if (state.status === "error" && !state.data) {
    return (
      <div className="home-page"><div className="home-error card-v3">
        <h3>今日工作台加载失败</h3><p>{state.error}</p>
        <button type="button" className="btn-ghost-v3" onClick={state.reload}><RefreshCw size={14} /> 重试</button>
      </div></div>
    );
  }

  const checkedToday = Boolean(today?.tasks_done > 0 || today?.elapsed_minutes > 0);
  return (
    <div className="home-page">
      <header className="home-context">
        <div>
          <span className="home-date">{formatToday()}</span>
          <h1>{getGreeting()}，{account.display_name || "准备好了吗"}</h1>
          <p>把注意力放在下一步，今天也完成一个扎实的小闭环。</p>
        </div>
        <div className="home-context-status">
          <span className="home-status-dot" />
          学习 Agent 已就绪
        </div>
      </header>
      <div className="home-hero">
        <NextActionCard next={data.next_best_action} readOnly={readOnly} onStart={() => {
          const task = tasks.find((item) => item.id === data.next_best_action?.task_id);
          if (task) startTask(task, true);
          else onStartInterview?.("", {});
        }} />
        <StreakCard streak={data.streak} checked={checkedToday} busy={checkingIn} readOnly={readOnly} onCheckin={handleCheckin} />
      </div>

      {readOnly && (
        <div className="home-offline" role="status">
          当前展示只读缓存，数据保存于 {formatCachedAt(state.cachedAt)}。恢复连接后可继续任务和打卡。
          <button type="button" onClick={state.reload}><RefreshCw size={13} /> 重试</button>
        </div>
      )}

      {(data.risks || []).length > 0 && (
        <div className="home-risks" role="status">
          {(data.risks || []).map((risk) => <span key={risk.code}>{risk.message}</span>)}
        </div>
      )}

      <TodayTaskList
        today={today}
        tasks={tasks}
        busyTask={busyTask}
        readOnly={readOnly}
        onToggle={toggleTask}
        onStart={startTask}
        onOpen={openTask}
        onNavigate={onNavigate}
        onStartInterview={onStartInterview}
      />

      <QuickActions account={account} onRequireAuth={onRequireAuth} onNavigate={onNavigate} onStartInterview={onStartInterview} />
      <TodayOverview
        minutes={data.study_minutes}
        interviews={data.interviews}
        practice={data.practice}
        plan={data.plan}
        onNavigate={onNavigate}
      />
      {(data.weak_points || []).length > 0 && (
        <section className="home-weak card-v3">
          <h3>高频薄弱项</h3>
          <div className="home-weak-chips">
            {data.weak_points.map((item) => (
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

function Guest({ onRequireAuth }) {
  return <div className="home-page"><div className="home-guest card-v3">
    <div className="home-guest-icon"><Sparkles size={26} /></div>
    <h3>登录后开启你的备考工作台</h3>
    <p>今日行动、面试报告、刷题结果和复习计划会在这里形成一个可验证的学习闭环。</p>
    <button type="button" className="btn-primary-v3" onClick={() => onRequireAuth?.()}>登录 / 注册 <ArrowRight size={15} /></button>
  </div></div>;
}

function Status({ icon, text }) {
  return <div className="home-page"><div className="home-loading">{icon} {text}</div></div>;
}

function StreakCard({ streak, checked, busy, readOnly, onCheckin }) {
  return <section className="home-streak card-v3">
    <div className="home-streak-flame"><Flame size={30} /></div>
    <div className="home-streak-main"><small>连续打卡</small><strong>{streak?.current_streak || 0} 天</strong><span>最长 {streak?.longest_streak || 0} 天 · 累计 {streak?.total_checkin_days || 0} 天</span></div>
    <button type="button" className={checked ? "btn-ghost-v3 checked" : "btn-primary-v3"} onClick={onCheckin} disabled={busy || readOnly}>
      {busy ? <Loader2 size={15} className="spin" /> : <CalendarCheck2 size={15} />}{checked ? "今日已打卡" : "今日打卡"}
    </button>
  </section>;
}

function NextActionCard({ next, readOnly, onStart }) {
  return <section className="home-advice card-v3">
    <div className="home-advice-head"><span className="home-advice-icon"><Sparkles size={15} /></span><strong>下一最佳行动</strong></div>
    <h3>{next?.title || "完成一次基线练习"}</h3>
    <p>{next?.reason || "从一次短练习开始，让系统了解你的当前水平。"}</p>
    <button type="button" className="home-advice-action" onClick={onStart} disabled={readOnly}>{next?.action?.label || "立即开始"} <ArrowRight size={13} /></button>
  </section>;
}

function formatCachedAt(value) {
  if (!value) return "上次在线时";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "上次在线时";
  return parsed.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function formatToday() {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long"
  }).format(new Date());
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 11) return "早上好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  return "晚上好";
}

function QuickActions({ account, onRequireAuth, onNavigate, onStartInterview }) {
  const items = [
    [<MessageSquarePlus size={17} />, "模拟面试", "AI 面试官 / 候选人", () => account ? onStartInterview?.("", {}) : onRequireAuth?.()],
    [<PenLine size={17} />, "刷题训练", "题库作答 · 错题本", () => onNavigate?.("practice")],
    [<CalendarCheck2 size={17} />, "复习站", "计划 · 打卡 · 素材", () => onNavigate?.("review-site")],
    [<Wand2 size={17} />, "计划生成", "AI 定制复习计划", () => onNavigate?.("planner")]
  ];
  return <div className="home-quick">{items.map(([icon, label, desc, click]) => (
    <button key={label} type="button" className="home-quick-item card-v3" onClick={click}>
      <span className="home-quick-icon">{icon}</span><strong>{label}</strong><small>{desc}</small>
    </button>
  ))}</div>;
}
