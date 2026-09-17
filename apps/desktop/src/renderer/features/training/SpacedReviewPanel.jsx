import { useEffect, useState } from "react";
import { Brain, Loader2 } from "lucide-react";
import { getInterviewAgentClient } from "../../apiClient";
import { productErrorMessage } from "../../utils/productSafety";

const api = getInterviewAgentClient();

export function SpacedReviewPanel({ onPractice }) {
  const [state, setState] = useState({ loading: true, items: [], error: "" });
  async function load() {
    setState((value) => ({ ...value, loading: true }));
    try {
      const data = await api.training.dueReviews();
      setState({ loading: false, items: data.items || [], error: "" });
    } catch (error) {
      setState({ loading: false, items: [], error: productErrorMessage(error, "复习队列加载失败，请稍后重试。") });
    }
  }
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  async function grade(item, quality) {
    await api.training.gradeReview(item.id, quality);
    await load();
  }
  if (state.loading) return <div className="home-loading"><Loader2 size={20} className="spin" /> 正在计算到期复习…</div>;
  if (state.error) return <p className="resume-hint error">{state.error}</p>;
  if (!state.items.length) return <div className="reports-empty card-v3"><Brain size={24} /><h3>今天没有到期内容</h3><p>错题会自动进入间隔复习队列。</p></div>;
  return <div className="spaced-review-list">{state.items.map((item) => <article className="card-v3 spaced-review-item" key={item.id}><div><strong>{item.question.prompt}</strong><span>已复习 {item.repetitions} 次 · 间隔 {item.interval_days} 天</span></div><button type="button" className="btn-primary-v3 small" onClick={() => onPractice(item.question)}>开始复习</button><div className="review-grade"><span>回忆质量</span>{[1, 2, 3, 4, 5].map((quality) => <button type="button" key={quality} onClick={() => grade(item, quality)}>{quality}</button>)}</div></article>)}</div>;
}
