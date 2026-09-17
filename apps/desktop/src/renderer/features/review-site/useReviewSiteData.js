import { useEffect, useRef, useState } from "react";
import { normalizePlanDetail } from "./ReviewSiteComponents";
import { productErrorMessage } from "../../utils/productSafety";
import { mergeUniqueById } from "../../hooks/useInfiniteScroll";

const INITIAL_PRACTICE_STATE = {
  items: [],
  total: 0,
  limit: 20,
  offset: 0,
  loading: false,
  loadError: "",
  hasMore: true,
  onlyWrong: false,
  onlyUnmastered: false
};

const INITIAL_FILTERS = { category: "", subject: "", difficulty: "", keyword: "" };

export function useReviewSiteData({ api, addToast, initialPlanId = "", activeTab = "today" }) {
  const [plans, setPlans] = useState([]);
  const [plansState, setPlansState] = useState({ loading: false, hasMore: true, loadError: "" });
  const [planId, setPlanId] = useState(initialPlanId);
  const [loading, setLoading] = useState(true);
  const [planDetail, setPlanDetail] = useState(() => normalizePlanDetail());
  const [practiceState, setPracticeState] = useState(INITIAL_PRACTICE_STATE);
  const [practiceFilters, setPracticeFilters] = useState(INITIAL_FILTERS);
  const [wrongBook, setWrongBook] = useState([]);
  const [studyData, setStudyData] = useState(null);
  const [awardsData, setAwardsData] = useState(null);
  const [awardsLoading, setAwardsLoading] = useState(false);
  const planRequestRef = useRef(0);
  const plansRef = useRef([]);
  const plansLoadingRef = useRef(false);
  const practiceRequestRef = useRef(0);
  const practiceLoadingRef = useRef(false);
  const loadedRef = useRef({
    today: false,
    planDetail: false,
    practice: false,
    wrongBook: false,
    awards: false
  });

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem("v3:practice-filters");
      if (saved) {
        const payload = JSON.parse(saved);
        setPracticeFilters(payload.filters || INITIAL_FILTERS);
        setPracticeState((current) => ({
          ...current,
          onlyWrong: Boolean(payload.onlyWrong),
          onlyUnmastered: Boolean(payload.onlyUnmastered)
        }));
      }
    } catch {
      // Corrupt browser state should not prevent the review site from loading.
    }
  }, []);

  useEffect(() => {
    try {
      sessionStorage.setItem("v3:practice-filters", JSON.stringify({
        filters: practiceFilters,
        onlyWrong: practiceState.onlyWrong,
        onlyUnmastered: practiceState.onlyUnmastered
      }));
    } catch {
      // Filters remain in memory when browser storage is unavailable.
    }
  }, [practiceFilters, practiceState.onlyWrong, practiceState.onlyUnmastered]);

  useEffect(() => {
    loadTodayData();
  }, []);

  useEffect(() => {
    if (!planId) return;
    loadedRef.current.planDetail = false;
    loadedRef.current.practice = false;
    loadedRef.current.wrongBook = false;
  }, [planId]);

  useEffect(() => {
    ensureTabData(activeTab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, planId]);

  useEffect(() => {
    if (activeTab !== "practice") return;
    loadPractice({ reset: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [practiceFilters, practiceState.onlyWrong, practiceState.onlyUnmastered]);

  async function bootstrap({ append = false } = {}) {
    if (plansLoadingRef.current || (append && !plansState.hasMore)) return plansRef.current;
    plansLoadingRef.current = true;
    if (!append) setLoading(true);
    setPlansState((current) => ({ ...current, loading: true, loadError: "" }));
    try {
      const list = await api.reviewSite.listPlans({ limit: 20, offset: append ? plansRef.current.length : 0 });
      const incoming = Array.isArray(list) ? list : [];
      const nextPlans = append ? mergeUniqueById(plansRef.current, incoming) : incoming;
      plansRef.current = nextPlans;
      setPlans(nextPlans);
      setPlansState({ loading: false, hasMore: incoming.length === 20, loadError: "" });
      if (nextPlans.length) setPlanId((current) => (
        current && nextPlans.some((plan) => plan.id === current) ? current : nextPlans[0].id || ""
      ));
      else setLoading(false);
      return nextPlans;
    } catch (error) {
      const message = productErrorMessage(error, "请稍后重试。");
      setPlansState((current) => ({ ...current, loading: false, loadError: message }));
      if (!append) {
        setLoading(false);
        addToast(`复习计划加载失败：${message}`, "error", 2600);
      }
      return plansRef.current;
    } finally {
      plansLoadingRef.current = false;
    }
  }

  async function loadPlanDetail(id) {
    if (!id) return;
    const requestId = ++planRequestRef.current;
    setLoading(true);
    try {
      const detail = await api.reviewSite.getPlan(id);
      if (requestId !== planRequestRef.current) return;
      setPlanDetail(normalizePlanDetail(detail));
      loadedRef.current.planDetail = true;
    } catch (error) {
      if (requestId !== planRequestRef.current) return;
      addToast(`计划详情加载失败：${productErrorMessage(error, "请稍后重试。")}`, "error", 2600);
    } finally {
      if (requestId === planRequestRef.current) setLoading(false);
    }
  }

  async function loadPractice({ reset = false } = {}) {
    if (practiceLoadingRef.current && !reset) return;
    const requestId = reset ? ++practiceRequestRef.current : practiceRequestRef.current;
    const current = practiceState;
    const nextOffset = reset ? 0 : current.items.length;
    if (!reset && !current.hasMore) return;
    practiceLoadingRef.current = true;
    setPracticeState((state) => ({ ...state, loading: true, loadError: "", ...(reset ? { offset: 0 } : {}) }));
    try {
      const result = await api.reviewSite.listPracticeQuestions({
        ...practiceFilters,
        limit: current.limit,
        offset: nextOffset
      });
      if (requestId !== practiceRequestRef.current) return;
      const incoming = Array.isArray(result?.items) ? result.items : [];
      setPracticeState((state) => ({
        ...state,
        items: reset ? incoming : mergeUniqueById(state.items, incoming),
        total: Number(result?.total || 0),
        offset: nextOffset,
        hasMore: result?.has_more ?? (nextOffset + incoming.length < Number(result?.total || 0)),
        loadError: "",
        loading: false
      }));
      loadedRef.current.practice = true;
    } catch (error) {
      if (requestId !== practiceRequestRef.current) return;
      setPracticeState((state) => ({
        ...state,
        ...(reset ? { items: [], total: 0 } : {}),
        loadError: productErrorMessage(error, "请稍后重试。"),
        loading: false
      }));
      if (reset) addToast(`题库加载失败：${productErrorMessage(error, "请稍后重试。")}`, "error", 2200);
    } finally {
      if (requestId === practiceRequestRef.current) practiceLoadingRef.current = false;
    }
  }

  async function loadWrongBook() {
    try {
      const list = await api.reviewSite.listWrongBook();
      setWrongBook(Array.isArray(list) ? list.slice(0, 5) : []);
      loadedRef.current.wrongBook = true;
    } catch {
      setWrongBook([]);
    }
  }

  async function loadTodayData({ force = false } = {}) {
    if (loadedRef.current.today && !force) return studyData;
    setLoading(true);
    try {
      const today = await api.learning.today();
      setStudyData(today);
      loadedRef.current.today = true;
      const lightPlan = planDetailFromToday(today);
      if (lightPlan) {
        setPlanDetail((current) => mergeLightPlanDetail(current, lightPlan));
        setPlanId((current) => current || lightPlan.plan.id || "");
        if (lightPlan.plan.id && plansRef.current.length === 0) {
          const activePlan = {
            id: lightPlan.plan.id,
            title: lightPlan.plan.title,
            status: "active",
            plan_key: lightPlan.plan.plan_key || ""
          };
          plansRef.current = [activePlan];
          setPlans([activePlan]);
          setPlansState((current) => ({ ...current, hasMore: true }));
        }
      }
      return today;
    } catch (error) {
      addToast(`今日任务加载失败：${productErrorMessage(error, "请稍后重试。")}`, "error", 2600);
      return null;
    } finally {
      setLoading(false);
    }
  }

  async function loadStudyData() {
    try {
      const dashboard = await api.study.dashboard().catch(() => null);
      setStudyData(dashboard);
      loadedRef.current.today = true;
    } finally {
      setAwardsLoading(false);
    }
  }

  async function loadAwards() {
    if (loadedRef.current.awards) return awardsData;
    setAwardsLoading(true);
    try {
      const achievements = await api.study.achievements().catch(() => null);
      setAwardsData(achievements);
      loadedRef.current.awards = true;
      return achievements;
    } finally {
      setAwardsLoading(false);
    }
  }

  async function ensureTabData(nextTab) {
    if (nextTab === "today") {
      await loadTodayData();
      return;
    }
    if (nextTab === "practice") {
      if (!loadedRef.current.practice) await loadPractice({ reset: true });
      if (!loadedRef.current.wrongBook) await loadWrongBook();
      return;
    }
    if (nextTab === "awards") {
      await loadAwards();
      return;
    }
    if (["plan", "intro", "star", "a4"].includes(nextTab) && planId && !loadedRef.current.planDetail) {
      await loadPlanDetail(planId);
    }
  }

  return {
    awardsData,
    awardsLoading,
    bootstrap,
    ensureTabData,
    loadAwards,
    loadPlanDetail,
    loadPractice,
    loadStudyData,
    loadTodayData,
    loadWrongBook,
    loadedRef,
    loading,
    planDetail,
    planId,
    plans,
    plansState,
    practiceFilters,
    practiceState,
    setPlanDetail,
    setPlanId,
    setPracticeFilters,
    setPracticeState,
    setStudyData,
    studyData,
    wrongBook
  };
}

function planDetailFromToday(payload) {
  const today = payload?.today;
  if (!today?.plan_id) return null;
  const day = today.day ? { ...today.day } : null;
  const tasks = Array.isArray(today.tasks) ? today.tasks : [];
  const phaseKey = day?.phase_key || tasks.find((task) => Array.isArray(task.tags))?.tags?.find((tag) => /^p\d+$/i.test(String(tag))) || "today";
  const normalizedDay = day ? {
    ...day,
    phase_key: phaseKey,
    tasks
  } : null;
  return normalizePlanDetail({
    plan: {
      id: today.plan_id,
      title: today.plan_title,
      status: "active"
    },
    phases: [{ phase_key: phaseKey, title: "今日重点", goal: payload?.next_best_action?.reason || "完成今天的复习任务" }],
    days: normalizedDay ? [normalizedDay] : [],
    progresses: tasks.map((task) => ({
      task_id: task.id,
      done: Boolean(task.done),
      note: task.note || "",
      elapsed_minutes: Number(task.elapsed_minutes || 0),
      mastery_score: task.mastery_score ?? null
    }))
  });
}

function mergeLightPlanDetail(current, lightPlan) {
  if (!current?.days?.length) return lightPlan;
  const currentPlanId = current.plan?.id || current.id;
  const lightPlanId = lightPlan.plan?.id || lightPlan.id;
  if (currentPlanId && lightPlanId && currentPlanId !== lightPlanId) return lightPlan;
  return {
    ...current,
    plan: {
      ...lightPlan.plan,
      ...current.plan
    },
    phases: current.phases?.length ? current.phases : lightPlan.phases,
    days: current.days?.length ? current.days : lightPlan.days,
    progresses: current.progresses?.length ? current.progresses : lightPlan.progresses
  };
}
