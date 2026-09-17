import { ClipboardList, PenLine, Target, Trophy } from "lucide-react";

function formatMinutes(minutes) {
  const value = Number(minutes || 0);
  if (value < 60) return `${value}分`;
  const hours = Math.floor(value / 60);
  const rest = value % 60;
  return rest ? `${hours}小时${rest}分` : `${hours}小时`;
}

export function TodayOverview({ minutes, interviews, practice, plan, onNavigate }) {
  const planRate = Math.round(Number(plan?.completion_rate || 0) * 100);
  return (
    <div className="home-stat-grid">
      <Stat icon={<Target size={16} />} label="今日学习" value={formatMinutes(minutes?.today_minutes)} sub={`本周 ${formatMinutes(minutes?.week_minutes)}`} />
      <Stat icon={<ClipboardList size={16} />} label="面试报告" value={`${interviews?.total_reports || 0} 份`} sub={interviews?.latest_score != null ? `最新 ${interviews.latest_score} 分` : "暂无评分"} onClick={() => onNavigate?.("reports")} />
      <Stat icon={<PenLine size={16} />} label="今日刷题" value={`${practice?.today_attempts || 0} 题`} sub={practice?.total_attempts ? `正确率 ${Math.round(Number(practice.correct_rate || 0) * 100)}%` : "暂无作答"} onClick={() => onNavigate?.("practice")} />
      <Stat icon={<Trophy size={16} />} label="计划进度" value={`${planRate}%`} sub={`${plan?.tasks_done || 0}/${plan?.total_tasks || 0} 任务`} onClick={() => onNavigate?.("review-site")} />
    </div>
  );
}

function Stat({ icon, label, value, sub, onClick }) {
  const Component = onClick ? "button" : "div";
  return (
    <Component type={onClick ? "button" : undefined} className="home-stat card-v3" onClick={onClick}>
      <span className="home-stat-icon">{icon}</span><small>{label}</small><strong>{value}</strong><em>{sub}</em>
    </Component>
  );
}
