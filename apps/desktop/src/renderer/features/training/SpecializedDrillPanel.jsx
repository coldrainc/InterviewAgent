import { useState } from "react";
import { CheckCircle2, Loader2, Target } from "lucide-react";
import { getInterviewAgentClient } from "../../apiClient";

const api = getInterviewAgentClient();

export function SpecializedDrillPanel({ onPractice }) {
  const [focus, setFocus] = useState("");
  const [count, setCount] = useState(10);
  const [drill, setDrill] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function create() {
    setLoading(true);
    try {
      setDrill(await api.training.createDrill({ focus, count }));
      setError("");
    } catch (err) {
      setError(err?.message || "专项训练创建失败");
    } finally {
      setLoading(false);
    }
  }

  return <section className="training-mode-panel">
    <div className="training-filters card-v3">
      <input className="v3-input" placeholder="主题或分类，例如 系统设计" value={focus} onChange={(event) => setFocus(event.target.value)} />
      <input className="v3-input" type="number" min="1" max="50" value={count} onChange={(event) => setCount(Number(event.target.value))} />
      <button type="button" className="btn-primary-v3" onClick={create} disabled={loading}>{loading ? <Loader2 size={14} className="spin" /> : <Target size={14} />} 生成专项</button>
    </div>
    {error && <p className="resume-hint error">{error}</p>}
    {drill && <div className="drill-list">{drill.questions.map((question, index) => <button type="button" className="card-v3 drill-item" key={question.id} onClick={() => onPractice(question)}><span>{index + 1}</span><strong>{question.prompt}</strong><small>{question.subject || question.practice_category}</small></button>)}<button type="button" className="btn-ghost-v3" onClick={async () => setDrill(await api.training.completeDrill(drill.id))}><CheckCircle2 size={14} /> {drill.status === "completed" ? "已完成" : "结束专项"}</button></div>}
  </section>;
}
