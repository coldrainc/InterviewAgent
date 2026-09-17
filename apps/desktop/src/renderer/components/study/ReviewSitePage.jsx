import { useEffect, useMemo, useRef, useState } from "react";
import {
  BookOpen, Check, ChevronDown, ChevronLeft, ChevronRight, Download, Flame,
  Loader2, PartyPopper, Plus, Printer, Target, Wand2
} from "lucide-react";
import { getInterviewAgentClient } from "../../apiClient";
import {
  A4FaceCard,
  AwardsWall,
  DayCompletionStrip,
  IntroPlayer,
  MaterialManager,
  PHASE_PRESETS,
  PhaseRoadmap,
  ReviewTaskDetailPage,
  TAB_DEFS,
  Toast,
  TodayView,
  V3FilterToolbar,
  V3PhaseDayCard,
  V3QaCard,
  V3StarCard,
  V3Stat,
  useToast
} from "../../features/review-site/ReviewSiteComponents";
import { useReviewSiteData } from "../../features/review-site/useReviewSiteData";
import { InfiniteScrollSentinel } from "../common/InfiniteScrollSentinel";

const api = getInterviewAgentClient();

export function ReviewSitePage({ navigationTarget, onBack, onNavigate, onOpenPlanner, onStartInterview }) {
  const planMenuRef = useRef(null);
  const qaListRef = useRef(null);
  const [celebrate, setCelebrate] = useState(null);
  const [practiceProgressSS, setPracticeProgressSS] = useState(null);
  const todayDoneRef = useRef(0);

  const { toasts, addToast } = useToast();
  const [tab, setTab] = useState("today");
  const [phaseFilter, setPhaseFilter] = useState("");
  const [creatingPlan, setCreatingPlan] = useState(false);
  const [planMenuOpen, setPlanMenuOpen] = useState(false);
  const [collapsedAll, setCollapsedAll] = useState(false);
  const [openDayKeys, setOpenDayKeys] = useState(() => new Set());
  const [checkinBusy, setCheckinBusy] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const dayScrollRefs = useRef({});
  const {
    awardsData, awardsLoading, bootstrap, loadPlanDetail, loadPractice,
    loadTodayData, loadWrongBook, loading, planDetail, planId, plans, plansState,
    practiceFilters, practiceState, setPlanDetail, setPlanId, setPracticeFilters,
    setPracticeState, setStudyData, studyData, wrongBook
  } = useReviewSiteData({ api, addToast, initialPlanId: navigationTarget?.plan_id || "", activeTab: tab });

  useEffect(() => {
    bootstrap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    if (!navigationTarget?.nonce) return;
    if (navigationTarget.plan_id) setPlanId(navigationTarget.plan_id);
    setTab("plan");
  }, [navigationTarget?.nonce, navigationTarget?.plan_id, setPlanId]);

  useEffect(() => {
    if (!navigationTarget?.nonce || loading || !days.length) return;
    const day = days.find((item) => item.id === navigationTarget.day_id)
      || days.find((item) => (item.tasks || []).some((task) => task.id === navigationTarget.task_id));
    if (!day) return;
    scrollToDay(day);
    window.setTimeout(() => {
      const task = document.querySelector(`[data-task-id="${navigationTarget.task_id}"]`);
      task?.scrollIntoView({ behavior: "smooth", block: "center" });
      task?.classList.add("highlight-target");
      window.setTimeout(() => task?.classList.remove("highlight-target"), 900);
    }, 160);
  }, [navigationTarget?.nonce, loading, days]);

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
    bootstrap();
    const onDocDown = (e) => {
      if (planMenuRef.current && !planMenuRef.current.contains(e.target)) {
        setPlanMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocDown);
    return () => document.removeEventListener("mousedown", onDocDown);
  }, [planMenuOpen]);

  useEffect(() => {
    if (!visibleDays.length) return;
    const today = visibleDays[todayIdx] || visibleDays[0];
    const key = today?.day_key || today?.id;
    if (key && openDayKeys.size === 0) {
      setOpenDayKeys(new Set([key]));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleDays.length, todayIdx]);

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
      await loadTodayData({ force: true });
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
          addToast("当前仅在本页临时保留；刷新前请恢复网络后重新保存", "warn");
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
        loadTodayData({ force: true });
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

  function openTaskDetail(task, day, local) {
    setSelectedTask({ task, day, progress: local });
  }

  async function startTask(task) {
    const payload = task?.link_payload && typeof task.link_payload === "object" ? task.link_payload : {};
    setSelectedTask(null);
    if (task?.link_type === "interview" || task?.simulation) {
      await onStartInterview?.(payload.focus || `围绕「${task.title}」开始模拟面试`, {
        mode: payload.mode || "interviewer",
        plan_task_id: task.id
      });
      return;
    }
    if (task?.link_type === "practice") {
      onNavigate?.("practice", { ...payload, task_id: task.id });
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

  function scrollToDay(day, options = {}) {
    if (!day) return;
    const { clearPhase = true } = options;
    setTab("plan");
    if (clearPhase) setPhaseFilter("");
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

  function toggleDay(day, nextOpen) {
    const key = day.day_key || day.id;
    if (!key) return;
    setOpenDayKeys((cur) => {
      const currentlyOpen = cur.has(key);
      const shouldOpen = typeof nextOpen === "boolean" ? nextOpen : !currentlyOpen;
      if (currentlyOpen === shouldOpen) return cur;
      const next = new Set(cur);
      if (shouldOpen) next.add(key); else next.delete(key);
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

      <div className="v3-workspace">
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
              {plans.length === 0 && <p style={{ padding: "8px 12px", color: "var(--v3-text-3)", margin: 0 }}>暂无计划，请生成或新建一个</p>}
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
              <InfiniteScrollSentinel
                hasMore={plansState.hasMore}
                loading={plansState.loading}
                error={plansState.loadError}
                onLoadMore={() => bootstrap({ append: true })}
              />
              <div className="plan-divider" />
              <button className="plan-action" onClick={() => { onOpenPlanner ? onOpenPlanner() : handleCreatePlan(); setPlanMenuOpen(false); }}>
                <span><Plus size={14} /> 新建计划</span>
              </button>
            </div>
          )}
        </div>
        <div className="v3-header-right">
          <button className="v3-btn primary" onClick={() => (onOpenPlanner ? onOpenPlanner() : handleCreatePlan())} disabled={creatingPlan}>
            <Wand2 size={14} /> 从 Interview 生成计划
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
        {selectedTask ? (
          <ReviewTaskDetailPage
            selection={selectedTask}
            onClose={() => setSelectedTask(null)}
            onStartTask={startTask}
          />
        ) : loading && !days.length ? (
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
            <p>根据目标岗位、可用时间和薄弱项生成你的专属复习节奏。</p>
            <div>
              <button className="v3-btn primary" onClick={() => (onOpenPlanner ? onOpenPlanner() : handleCreatePlan())}>
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
            onOpenTask={openTaskDetail}
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
            <PhaseRoadmap
              phases={phases}
              days={days}
              progresses={progresses}
              activePhaseKey={phaseFilter || todayDay?.phase_key || ""}
              onSelectPhase={(key) => {
                setPhaseFilter(key);
                setCollapsedAll(false);
                const first = days.find((day) => day.phase_key === key);
                if (first) scrollToDay(first, { clearPhase: false });
              }}
            />
            <DayCompletionStrip
              days={days}
              progresses={progresses}
              todayIdx={todayIdx}
              activeDayKey={todayDay?.day_key || todayDay?.id || ""}
              onSelectDay={(day) => {
                setPhaseFilter("");
                scrollToDay(day);
              }}
            />
            <div className="v3-filter-bar v3-plan-tools">
              <div className="v3-filter-chips">
                <button className={`v3-chip toggle ${phaseFilter === "" ? "on" : ""}`} onClick={() => setPhaseFilter("")}>
                  <Target size={12} /> 全部阶段
                </button>
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
                <p>当前阶段下还没有安排任务，可切换阶段或前往计划生成器添加安排。</p>
                <div>
                  <button className="v3-btn primary" onClick={() => (onOpenPlanner ? onOpenPlanner() : handleCreatePlan())}>
                    <Wand2 size={14} /> 调整计划
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
                onOpenTask={openTaskDetail}
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
              onRefresh={() => loadPractice({ reset: true })}
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
            <InfiniteScrollSentinel
              hasMore={practiceState.hasMore}
              loading={practiceState.loading}
              error={practiceState.loadError}
              onLoadMore={() => loadPractice()}
            />
          </>
        ) : tab === "intro" ? (
          <>
            <MaterialManager kind="intro_scripts" planId={planId} items={planDetail.intro_scripts} onSaved={() => loadPlanDetail(planId)} addToast={addToast} />
            <IntroPlayer scripts={planDetail.intro_scripts} addToast={addToast} />
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
