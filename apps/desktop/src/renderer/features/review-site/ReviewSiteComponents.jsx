import { useState } from "react";
import {
  BookOpen, Check, FileText, Mic, NotebookPen, Sparkles, Star as StarIcon, Trophy, X, Zap
} from "lucide-react";

export const TAB_DEFS = [
  { key: "today", label: "今日", icon: <Sparkles size={15} /> },
  { key: "plan", label: "每日打卡", icon: <NotebookPen size={15} /> },
  { key: "practice", label: "题库", icon: <BookOpen size={15} /> },
  { key: "intro", label: "自我介绍", icon: <Mic size={15} /> },
  { key: "star", label: "STAR 卡", icon: <StarIcon size={15} /> },
  { key: "a4", label: "A4 速记", icon: <FileText size={15} /> },
  { key: "awards", label: "成就", icon: <Trophy size={15} /> }
];

export const PHASE_PRESETS = [
  { key: "foundation", title: "基础夯实", range: "Day 1-4", goal: "构建知识体系骨架", accent: "#2f63e8" },
  { key: "deepening", title: "专题深挖", range: "Day 5-8", goal: "高频重难点突破", accent: "#0f8f8f" },
  { key: "project", title: "项目打磨", range: "Day 9-11", goal: "STAR 表达与亮点包装", accent: "#16a673" },
  { key: "simulation", title: "模拟冲刺", range: "Day 12-14", goal: "全流程高压模拟", accent: "#c77918" }
];

export function normalizePlanDetail(payload) {
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

export function useToast() {
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

export function Toast({ toasts }) {
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

export function V3Stat({ icon, label, value }) {
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

export {
  AwardsWall,
  DayCompletionStrip,
  PhaseRoadmap,
  TodayView,
  V3PhaseDayCard
} from "./ReviewTodayComponents";
export { ReviewTaskDetailPage } from "./ReviewTaskDetailDrawer";
export {
  V3FilterToolbar,
  V3QaCard
} from "./ReviewPracticeComponents";
export {
  A4FaceCard,
  IntroPlayer,
  MaterialManager,
  V3StarCard
} from "./ReviewMaterialComponents";
