import { Activity, CheckCircle2, RefreshCw } from "lucide-react";

function percent(value) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

export function LearningReliabilityPanel({ metrics }) {
  const commands = metrics?.commands || {};
  const successRate = Number(commands.success_rate || 0);
  return (
    <section className="ops-block wide learning-reliability-panel">
      <div className="panel-heading">
        <span><Activity size={15} /> 学习服务状态</span>
        <small>{successRate >= 0.95 ? "运行良好" : "持续观察"}</small>
      </div>
      <div className="learning-reliability-grid">
        <ReliabilityMetric icon={<Activity size={16} />} label="处理次数" value={commands.total || 0} />
        <ReliabilityMetric icon={<CheckCircle2 size={16} />} label="完成率" value={percent(commands.success_rate)} />
        <ReliabilityMetric icon={<RefreshCw size={16} />} label="需要重试" value={percent(commands.conflict_rate)} />
      </div>
      <p className="resume-hint">这里只展示学习任务的整体运行情况，不展示你的回答或账户敏感信息。</p>
    </section>
  );
}

function ReliabilityMetric({ icon, label, value }) {
  return (
    <div className="learning-reliability-metric">
      <span>{icon}</span>
      <small>{label}</small>
      <strong>{value}</strong>
    </div>
  );
}
