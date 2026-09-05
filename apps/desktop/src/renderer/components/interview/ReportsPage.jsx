import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Loader2,
  MessageSquarePlus,
  Plus,
  RefreshCw,
  Sparkles,
  Target,
  TrendingUp,
  X
} from "lucide-react";
import { getInterviewAgentClient } from "../../apiClient";
import { formatDateTime } from "../../utils/interview";

const api = getInterviewAgentClient();

const DIMENSION_LABELS = {
  project_depth: "项目深度",
  fundamentals: "基础功底",
  problem_solving: "问题解决",
  system_design: "系统设计",
  communication: "沟通表达",
  engineering: "工程实践",
  ai_engineering: "AI 工程"
};

function scoreTone(score) {
  if (score == null) return "";
  if (score >= 85) return "good";
  if (score >= 70) return "mid";
  return "low";
}

export function ReportsPage({ account, onRequireAuth, onOpenSession, onNavigate }) {
  const [state, setState] = useState({ status: "idle", reports: [], trend: null, error: "" });
  const [sessions, setSessions] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [planPicker, setPlanPicker] = useState({ open: false, report: null, plans: [], adding: false });

  const load = useCallback(async () => {
    if (!account) return;
    setState((current) => ({ ...current, status: "loading", error: "" }));
    try {
      const [result, sessionList] = await Promise.all([
        api.study.listReports(50),
        api.listSessions().catch(() => [])
      ]);
      setState({
        status: "ready",
        reports: Array.isArray(result?.reports) ? result.reports : [],
        trend: result?.trend || null,
        error: ""
      });
      setSessions(Array.isArray(sessionList) ? sessionList : []);
    } catch (error) {
      setState({ status: "error", reports: [], trend: null, error: error?.message || "报告加载失败" });
    }
  }, [account]);

  useEffect(() => {
    if (account) load();
  }, [account, load]);

  const sessionMap = useMemo(() => {
    const map = {};
    for (const session of sessions) map[session.id] = session;
    return map;
  }, [sessions]);

  async function openDetail(report) {
    setSelectedId(report.session_id);
    setDetail(null);
    setDetailLoading(true);
    try {
      const data = await api.study.getReport(report.session_id);
      setDetail(data);
    } catch (error) {
      window.alert(`报告详情加载失败：${error?.message || "未知错误"}`);
      setSelectedId("");
    } finally {
      setDetailLoading(false);
    }
  }

  async function openAddToPlan(report) {
    try {
      const plans = await api.reviewSite.listPlans();
      setPlanPicker({ open: true, report, plans: Array.isArray(plans) ? plans : [], adding: false });
    } catch (error) {
      window.alert(`计划加载失败：${error?.message || "未知错误"}`);
    }
  }

  async function addToPlan(planId) {
    setPlanPicker((current) => ({ ...current, adding: true }));
    try {
      const result = await api.study.addReportTasks(planId, planPicker.report.session_id);
      const count = result?.data?.created?.length ?? result?.created?.length ?? 0;
      window.alert(`已把 ${count || ""} 条改进建议加入复习计划，可在复习站对应日期查看。`);
      setPlanPicker({ open: false, report: null, plans: [], adding: false });
      onNavigate?.("review-site");
    } catch (error) {
      window.alert(`加入计划失败：${error?.message || "未知错误"}`);
      setPlanPicker((current) => ({ ...current, adding: false }));
    }
  }

  if (!account) {
    return (
      <div className="reports-page">
        <div className="home-guest card-v3">
          <div className="home-guest-icon"><ClipboardList size={26} /></div>
          <h3>登录后查看面试报告</h3>
          <p>每场模拟面试结束后，AI 会生成结构化评分、薄弱项和改进建议。</p>
          <button type="button" className="btn-primary-v3" onClick={() => onRequireAuth?.()}>
            登录 / 注册 <ArrowRight size={15} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="reports-page">
      <div className="reports-head">
        <div>
          <h2>面试报告</h2>
          <p>结构化评分、薄弱项回流与改进建议追踪</p>
        </div>
        <button type="button" className="btn-ghost-v3" onClick={load} disabled={state.status === "loading"}>
          <RefreshCw size={14} className={state.status === "loading" ? "spin" : ""} /> 刷新
        </button>
      </div>

      {state.trend && (
        <div className="reports-trend">
          <TrendCard icon={<ClipboardList size={15} />} label="报告总数" value={`${state.trend.total_reports}`} sub={`已评分 ${state.trend.scored_reports}`} />
          <TrendCard icon={<TrendingUp size={15} />} label="最新得分" value={state.trend.latest_score != null ? `${state.trend.latest_score}` : "—"} sub="最近一场" />
          <TrendCard icon={<Target size={15} />} label="近 5 场均分" value={state.trend.recent_average != null ? `${state.trend.recent_average}` : "—"} sub={`历史均分 ${state.trend.average_score ?? "—"}`} />
        </div>
      )}

      {state.status === "loading" && state.reports.length === 0 && (
        <div className="home-loading"><Loader2 size={22} className="spin" /> 正在加载报告…</div>
      )}
      {state.status === "error" && (
        <div className="home-error card-v3">
          <h3>报告加载失败</h3>
          <p>{state.error}</p>
          <button type="button" className="btn-ghost-v3" onClick={load}><RefreshCw size={14} /> 重试</button>
        </div>
      )}
      {state.status === "ready" && state.reports.length === 0 && (
        <div className="reports-empty card-v3">
          <Sparkles size={24} />
          <h3>还没有面试报告</h3>
          <p>完成一场模拟面试后，这里会出现评分报告与改进建议。</p>
          <button type="button" className="btn-primary-v3" onClick={() => onNavigate?.("chat")}>
            <MessageSquarePlus size={14} /> 去模拟面试
          </button>
        </div>
      )}

      <div className="reports-list">
        {state.reports.map((report) => {
          const session = sessionMap[report.session_id];
          return (
            <article key={report.id} className="report-card card-v3">
              <button type="button" className="report-card-main" onClick={() => openDetail(report)}>
                <div className={`report-score ${scoreTone(report.total_score)}`}>
                  <strong>{report.total_score ?? "—"}</strong>
                  <small>总分</small>
                </div>
                <div className="report-card-body">
                  <strong>{session?.target_role || "模拟面试"}</strong>
                  <span>
                    {report.mode === "candidate" ? "候选人答题模式" : "模拟面试模式"} · {formatDateTime(report.created_at)}
                  </span>
                  <div className="report-card-tags">
                    {(report.weakness_tags || []).slice(0, 3).map((tag) => (
                      <i key={tag} className="v3-chip weak">{tag}</i>
                    ))}
                    {(report.strength_tags || []).slice(0, 2).map((tag) => (
                      <i key={tag} className="v3-chip good">{tag}</i>
                    ))}
                  </div>
                </div>
                <ArrowRight size={16} className="report-card-arrow" />
              </button>
              <div className="report-card-actions">
                <button type="button" className="btn-ghost-v3 small" onClick={() => onOpenSession(report.session_id)}>
                  <MessageSquarePlus size={13} /> 回看会话
                </button>
                <button type="button" className="btn-ghost-v3 small" onClick={() => openAddToPlan(report)}>
                  <Plus size={13} /> 加入复习计划
                </button>
              </div>
            </article>
          );
        })}
      </div>

      {selectedId && (
        <ReportDetail
          loading={detailLoading}
          report={detail}
          onClose={() => { setSelectedId(""); setDetail(null); }}
          onOpenSession={() => { onOpenSession(selectedId); setSelectedId(""); }}
        />
      )}

      {planPicker.open && (
        <div className="modal-mask" onClick={() => setPlanPicker({ open: false, report: null, plans: [], adding: false })}>
          <div className="modal-card card-v3" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>加入复习计划</h3>
              <button type="button" className="icon-button" onClick={() => setPlanPicker({ open: false, report: null, plans: [], adding: false })} aria-label="关闭">
                <X size={16} />
              </button>
            </div>
            <p className="modal-sub">选择一个计划，报告中的改进建议会生成「重点」任务写入最近的未完成日。</p>
            {planPicker.plans.length === 0 ? (
              <div className="modal-empty">
                <p>还没有可用的复习计划。</p>
                <button type="button" className="btn-primary-v3" onClick={() => { setPlanPicker({ open: false, report: null, plans: [], adding: false }); onNavigate?.("planner"); }}>
                  <Plus size={14} /> 去生成计划
                </button>
              </div>
            ) : (
              <ul className="plan-pick-list">
                {planPicker.plans.map((plan) => (
                  <li key={plan.id}>
                    <button type="button" disabled={planPicker.adding} onClick={() => addToPlan(plan.id)}>
                      <strong>{plan.title}</strong>
                      <span>{plan.status === "active" ? "进行中" : plan.status === "archived" ? "已归档" : "草稿"}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function TrendCard({ icon, label, value, sub }) {
  return (
    <div className="report-trend-card card-v3">
      <span className="home-stat-icon">{icon}</span>
      <small>{label}</small>
      <strong>{value}</strong>
      <em>{sub}</em>
    </div>
  );
}

function ReportDetail({ loading, report, onClose, onOpenSession }) {
  const dimensions = useMemo(() => {
    const entries = Object.entries(report?.dimension_scores || {});
    return entries
      .map(([key, value]) => ({ key, label: DIMENSION_LABELS[key] || key, score: typeof value === "object" ? value?.score : value }))
      .filter((item) => typeof item.score === "number");
  }, [report]);

  const suggestions = useMemo(() => {
    return (report?.suggestions || []).map((item) =>
      typeof item === "string" ? { title: item, detail: "" } : item
    );
  }, [report]);

  return (
    <div className="modal-mask" onClick={onClose}>
      <div className="modal-card report-detail card-v3" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>面试报告详情</h3>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭"><X size={16} /></button>
        </div>
        {loading || !report ? (
          <div className="home-loading"><Loader2 size={20} className="spin" /> 加载中…</div>
        ) : (
          <div className="report-detail-body">
            <div className="report-detail-hero">
              <div className={`report-score large ${scoreTone(report.total_score)}`}>
                <strong>{report.total_score ?? "—"}</strong>
                <small>综合评分</small>
              </div>
              <div className="report-detail-meta">
                {report.summary && <p>{report.summary}</p>}
                <div className="report-card-tags">
                  {(report.strength_tags || []).map((tag) => <i key={tag} className="v3-chip good"><CheckCircle2 size={12} /> {tag}</i>)}
                  {(report.weakness_tags || []).map((tag) => <i key={tag} className="v3-chip weak">{tag}</i>)}
                </div>
              </div>
            </div>

            {dimensions.length > 0 && (
              <section>
                <h4>维度评分</h4>
                <div className="report-dim-list">
                  {dimensions.map((dim) => (
                    <div key={dim.key} className="report-dim-row">
                      <span>{dim.label}</span>
                      <div className="report-dim-bar">
                        <div className={scoreTone(dim.score)} style={{ width: `${Math.min(100, Math.max(0, dim.score))}%` }} />
                      </div>
                      <strong>{dim.score}</strong>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {suggestions.length > 0 && (
              <section>
                <h4>改进建议</h4>
                <ul className="report-suggestion-list">
                  {suggestions.map((item, index) => (
                    <li key={index}>
                      <strong>{item.title || `建议 ${index + 1}`}</strong>
                      {item.detail && <p>{item.detail}</p>}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <div className="report-detail-actions">
              <button type="button" className="btn-ghost-v3" onClick={onOpenSession}>
                <ArrowLeft size={14} /> 回看面试会话
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
