import { Activity, Bot, ClipboardCheck, GitBranch, RefreshCw, Square, Zap } from "lucide-react";
import { LearningReliabilityPanel } from "../../features/operations/LearningReliabilityPanel";
import { redactSensitiveText } from "../../utils/productSafety";
import { InfiniteScrollSentinel } from "../common/InfiniteScrollSentinel";

const statusLabels = {
  pending: "等待中",
  running: "执行中",
  succeeded: "已完成",
  failed: "失败",
  canceled: "已取消"
};

const jobTypeLabels = {
  workflow: "复杂任务编排",
  evaluation: "质量评估",
  multi_agent: "多 Agent 协作"
};

export function OperationsCenter({
  opsState,
  onReload,
  onRunWorkflow,
  onRunStudyPlan,
  onRunEvaluation,
  onRunMultiAgent,
  onCancelJob,
  onLoadMore,
  onBack
}) {
  const jobs = opsState.jobs || [];
  const traces = opsState.traces || [];
  const evalRuns = opsState.evalRuns || [];
  const metrics = opsState.metrics || {};
  return (
    <section className="ops-center">
      <div className="ops-hero">
        <div>
          <span className="eyebrow">训练中心</span>
          <h3>训练与评估工作台</h3>
          <p>集中完成面试复盘、刷题计划、协作审核与训练质量检查。</p>
        </div>
        <div className="setup-hero-actions">
          <button type="button" className="secondary-action inline" onClick={onBack}>返回工作台</button>
          <button type="button" className="icon-button" onClick={onReload} aria-label="刷新任务与评测">
            <RefreshCw size={15} />
          </button>
        </div>
      </div>

      {opsState.error && <p className="resume-hint error">{opsState.error}</p>}
      {opsState.message && <p className="resume-hint success">{opsState.message}</p>}

      <div className="ops-actions">
        <button type="button" className="primary-action inline" onClick={onRunWorkflow} disabled={opsState.status === "loading"}>
          <GitBranch size={16} />
          生成面试复盘
        </button>
        <button type="button" className="secondary-action inline" onClick={onRunStudyPlan} disabled={opsState.status === "loading"}>
          <Zap size={16} />
          生成刷题计划
        </button>
        <button type="button" className="secondary-action inline" onClick={onRunEvaluation} disabled={opsState.status === "loading"}>
          <ClipboardCheck size={16} />
          质量评估
        </button>
        <button type="button" className="secondary-action inline" onClick={onRunMultiAgent} disabled={opsState.status === "loading"}>
          <Bot size={16} />
          多 Agent 审核
        </button>
      </div>

      <div className="ops-metrics">
        <MetricCard icon={<Activity size={17} />} label="任务总数" value={sumCounts(metrics.job_counts)} />
        <MetricCard icon={<Zap size={17} />} label="运行中" value={metrics.job_counts?.running || 0} />
        <MetricCard icon={<ClipboardCheck size={17} />} label="已完成" value={metrics.job_counts?.succeeded || 0} />
        <MetricCard icon={<Bot size={17} />} label="处理记录" value={traces.length} />
      </div>

      <div className="ops-grid">
        <LearningReliabilityPanel metrics={metrics.learning} />

        <section className="ops-block wide">
          <div className="panel-heading">
            <span><GitBranch size={15} /> 后台任务</span>
            <small>{jobs.length} 条</small>
          </div>
          <div className="ops-list">
            {jobs.length ? jobs.map((job) => (
              <JobRow key={job.id} job={job} onCancel={onCancelJob} />
            )) : (
              <p className="resume-hint">暂无任务。可以先生成一次面试复盘或刷题计划。</p>
            )}
            <InfiniteScrollSentinel
              hasMore={Boolean(opsState.pages?.jobs)}
              loading={opsState.loadingKinds?.includes("jobs")}
              error=""
              onLoadMore={() => onLoadMore?.("jobs")}
            />
          </div>
        </section>

        <section className="ops-block">
          <div className="panel-heading">
            <span><Activity size={15} /> 最近处理记录</span>
            <small>{traces.length} 条</small>
          </div>
          <div className="ops-list compact">
            {traces.length ? traces.map((trace) => (
              <TraceRow key={trace.id} trace={trace} />
            )) : (
              <p className="resume-hint">完成复盘、评估或协作审核后，这里会显示处理结果。</p>
            )}
            <InfiniteScrollSentinel
              hasMore={Boolean(opsState.pages?.traces)}
              loading={opsState.loadingKinds?.includes("traces")}
              error=""
              onLoadMore={() => onLoadMore?.("traces")}
            />
          </div>
        </section>

        <section className="ops-block">
          <div className="panel-heading">
            <span><ClipboardCheck size={15} /> 质量评估</span>
          </div>
          <p className="resume-hint">
            质量评估会结合最近会话和题库检查回答质量，给出得分、风险项和改进建议。
          </p>
          <div className="ops-capability-list">
            <span>RAG 评测</span>
            <span>Agent 评测</span>
            <span>回归基线</span>
            <span>风险复核</span>
          </div>
          <div className="ops-list compact">
            {evalRuns.map((run) => <EvalRunRow key={run.id} run={run} />)}
            <InfiniteScrollSentinel
              hasMore={Boolean(opsState.pages?.evalRuns)}
              loading={opsState.loadingKinds?.includes("evalRuns")}
              error=""
              onLoadMore={() => onLoadMore?.("evalRuns")}
            />
          </div>
        </section>
      </div>
    </section>
  );
}

function MetricCard({ icon, label, value }) {
  return (
    <article className="ops-metric">
      <span>{icon}</span>
      <small>{label}</small>
      <strong>{value}</strong>
    </article>
  );
}

function JobRow({ job, onCancel }) {
  const canCancel = job.status === "pending" || job.status === "running";
  return (
    <article className="ops-row">
      <div>
        <strong>{job.title}</strong>
        <span>{jobTypeLabels[job.job_type] || job.job_type} · {formatDate(job.updated_at)}</span>
        {job.result?.summary && <p>{redactSensitiveText(job.result.summary)}</p>}
        {Number.isFinite(job.result?.readiness_score) && (
          <p>准备度 {job.result.readiness_score} 分</p>
        )}
        {job.result?.metrics && (
          <p>平均分 {job.result.metrics.average_score} · 通过率 {Math.round((job.result.metrics.pass_rate || 0) * 100)}%</p>
        )}
        {Array.isArray(job.result?.next_actions) && job.result.next_actions.length > 0 && (
          <ul className="ops-next-actions">
            {job.result.next_actions.slice(0, 3).map((item) => <li key={item}>{redactSensitiveText(item)}</li>)}
          </ul>
        )}
        {Array.isArray(job.result?.recommendations) && job.result.recommendations.length > 0 && (
          <ul className="ops-next-actions">
            {job.result.recommendations.slice(0, 3).map((item) => <li key={item}>{redactSensitiveText(item)}</li>)}
          </ul>
        )}
        {job.error_message && <p className="error-text">任务未能完成，请稍后重试。</p>}
      </div>
      <div className="ops-row-actions">
        <span className={`status-pill ${job.status}`}>{statusLabels[job.status] || job.status}</span>
        {canCancel && (
          <button type="button" className="icon-button" onClick={() => onCancel(job.id)} aria-label="取消任务">
            <Square size={13} />
          </button>
        )}
      </div>
    </article>
  );
}

function TraceRow({ trace }) {
  return (
    <article className="ops-row compact">
      <div>
        <strong>{redactSensitiveText(trace.title)}</strong>
        <span>{formatDate(trace.created_at)}</span>
      </div>
      <span className={`status-pill ${trace.status}`}>{statusLabels[trace.status] || trace.status}</span>
    </article>
  );
}

function EvalRunRow({ run }) {
  return (
    <article className="ops-row compact">
      <div>
        <strong>{redactSensitiveText(run.name || "质量评估")}</strong>
        <span>{formatDate(run.created_at)}</span>
      </div>
      <span className={`status-pill ${run.status}`}>{statusLabels[run.status] || run.status}</span>
    </article>
  );
}

function sumCounts(counts = {}) {
  return Object.values(counts || {}).reduce((sum, value) => sum + Number(value || 0), 0);
}

function formatDate(value) {
  if (!value) return "";
  try {
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    }).format(new Date(value));
  } catch (_error) {
    return value;
  }
}
