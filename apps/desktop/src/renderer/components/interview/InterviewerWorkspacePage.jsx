import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ClipboardList, Loader2, MessageSquarePlus, Plus, RefreshCw, Save, Trash2 } from "lucide-react";
import { getInterviewAgentClient } from "../../apiClient";
import { InfiniteScrollSentinel } from "../common/InfiniteScrollSentinel";
import { mergeUniqueById } from "../../hooks/useInfiniteScroll";

const api = getInterviewAgentClient();

export function InterviewerWorkspacePage({ account, profile, onRequireAuth, onStartInterview }) {
  const [kits, setKits] = useState([]);
  const [active, setActive] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ target_role: profile?.targetRole || "", seniority: profile?.seniority || "", duration_minutes: 45 });
  const [evidence, setEvidence] = useState({ dimension: "", signal: "positive", note: "" });
  const [error, setError] = useState("");
  const [hasMore, setHasMore] = useState(true);
  const kitsRef = useRef([]);
  const loadingRef = useRef(false);

  const load = useCallback(async ({ append = false } = {}) => {
    if (!account || loadingRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    try {
      const items = await api.interviewer.listKits({ limit: 20, offset: append ? kitsRef.current.length : 0 });
      const incoming = Array.isArray(items) ? items : [];
      const merged = append ? mergeUniqueById(kitsRef.current, incoming) : incoming;
      kitsRef.current = merged;
      setKits(merged);
      setHasMore(incoming.length === 20);
      if (!active && items?.[0]) setActive(await api.interviewer.getKit(items[0].id));
      setError("");
    } catch (err) {
      setError(err?.message || "面试题纲加载失败");
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, [account, active]);

  useEffect(() => { load(); }, [account]); // eslint-disable-line react-hooks/exhaustive-deps

  async function createKit() {
    if (!account) return onRequireAuth?.();
    if (!form.target_role.trim()) return setError("请先填写目标岗位。");
    setSaving(true);
    try {
      const kit = await api.interviewer.createKit(form);
      setActive(kit);
      kitsRef.current = mergeUniqueById([kit], kitsRef.current);
      setKits(kitsRef.current);
      setEvidence((item) => ({ ...item, dimension: kit.dimensions[0] || "" }));
      setError("");
    } catch (err) {
      setError(err?.message || "题纲创建失败");
    } finally {
      setSaving(false);
    }
  }

  function patchQuestion(index, patch) {
    setActive((kit) => ({ ...kit, questions: kit.questions.map((item, idx) => idx === index ? { ...item, ...patch } : item) }));
  }

  async function saveQuestions() {
    setSaving(true);
    try {
      const updated = await api.interviewer.updateQuestions(active.id, { expected_version: active.version, questions: active.questions });
      setActive(updated);
      setError("");
    } catch (err) {
      setError(err?.message || "题纲保存失败，请刷新后重试");
    } finally {
      setSaving(false);
    }
  }

  async function addEvidence() {
    if (!evidence.note.trim()) return;
    setSaving(true);
    try {
      const item = await api.interviewer.addEvidence(active.id, evidence);
      setActive((kit) => ({ ...kit, evidence: [...(kit.evidence || []), item] }));
      setEvidence((value) => ({ ...value, note: "" }));
    } catch (err) {
      setError(err?.message || "证据记录失败");
    } finally {
      setSaving(false);
    }
  }

  if (!account) return <div className="interviewer-page"><div className="home-guest card-v3"><ClipboardList size={26} /><h3>登录后使用面试官工作台</h3><p>题纲、人工证据和评价维度会安全地保存在你的账号下。</p><button type="button" className="btn-primary-v3" onClick={onRequireAuth}>登录 / 注册</button></div></div>;

  return <div className="interviewer-page">
    <div className="reports-head"><div><h2>面试官工作台</h2><p>结构化题纲 · 追问 · 证据记录</p></div><button type="button" className="btn-ghost-v3" onClick={load}><RefreshCw size={14} /> 刷新</button></div>
    {error && <p className="resume-hint error">{error}</p>}
    <section className="interviewer-create card-v3">
      <input className="v3-input" placeholder="目标岗位" value={form.target_role} onChange={(event) => setForm({ ...form, target_role: event.target.value })} />
      <input className="v3-input" placeholder="级别" value={form.seniority} onChange={(event) => setForm({ ...form, seniority: event.target.value })} />
      <input className="v3-input" type="number" min="15" max="240" value={form.duration_minutes} onChange={(event) => setForm({ ...form, duration_minutes: Number(event.target.value) })} />
      <button type="button" className="btn-primary-v3" onClick={createKit} disabled={saving}>{saving ? <Loader2 className="spin" size={14} /> : <Plus size={14} />} 新建题纲</button>
    </section>
    <div className="interviewer-layout">
      <aside className="interviewer-kits card-v3">{loading && !kits.length && <Loader2 className="spin" size={18} />}{kits.map((kit) => <button key={kit.id} type="button" className={active?.id === kit.id ? "active" : ""} onClick={async () => setActive(await api.interviewer.getKit(kit.id))}><strong>{kit.title}</strong><small>{kit.duration_minutes} 分钟 · {kit.questions.length} 题</small></button>)}<InfiniteScrollSentinel hasMore={hasMore} loading={loading} error={error} onLoadMore={() => load({ append: true })} /></aside>
      {!active ? <div className="reports-empty card-v3"><ClipboardList size={24} /><h3>先创建一份题纲</h3><p>系统会生成可编辑的核心问题和追问。</p></div> : <main className="interviewer-board">
        <section className="card-v3 interviewer-outline">
          <div className="interviewer-section-head"><div><h3>{active.title}</h3><span>{active.target_role} · v{active.version}</span></div><button type="button" className="btn-ghost-v3" onClick={saveQuestions} disabled={saving}><Save size={14} /> 保存</button></div>
          {active.questions.map((question, index) => <div className="interviewer-question" key={question.id}>
            <span>{index + 1}</span><textarea value={question.text} onChange={(event) => patchQuestion(index, { text: event.target.value })} />
            <select value={question.dimension} onChange={(event) => patchQuestion(index, { dimension: event.target.value })}>{active.dimensions.map((item) => <option key={item}>{item}</option>)}</select>
            <button type="button" className="icon-button" aria-label="删除问题" onClick={() => setActive({ ...active, questions: active.questions.filter((_, idx) => idx !== index) })}><Trash2 size={14} /></button>
          </div>)}
          <button type="button" className="btn-ghost-v3" onClick={() => setActive({ ...active, questions: [...active.questions, { id: crypto.randomUUID(), text: "", dimension: active.dimensions[0], followups: [] }] })}><Plus size={14} /> 添加问题</button>
        </section>
        <section className="card-v3 interviewer-evidence-panel">
          <div className="interviewer-section-head"><h3>评价证据</h3><button type="button" className="btn-primary-v3" onClick={() => onStartInterview?.(`按题纲「${active.title}」开始面试`, { mode: "interviewer", interviewer_kit_id: active.id })}><MessageSquarePlus size={14} /> 开始面试</button></div>
          <div className="evidence-form"><select value={evidence.dimension || active.dimensions[0]} onChange={(event) => setEvidence({ ...evidence, dimension: event.target.value })}>{active.dimensions.map((item) => <option key={item}>{item}</option>)}</select><select value={evidence.signal} onChange={(event) => setEvidence({ ...evidence, signal: event.target.value })}><option value="positive">正向</option><option value="neutral">中性</option><option value="negative">风险</option><option value="unknown">待确认</option></select><input className="v3-input" placeholder="记录可引用的行为证据" value={evidence.note} onChange={(event) => setEvidence({ ...evidence, dimension: evidence.dimension || active.dimensions[0], note: event.target.value })} /><button type="button" className="btn-ghost-v3" onClick={addEvidence}><Check size={14} /> 记录</button></div>
          <ul>{(active.evidence || []).map((item) => <li key={item.id}><i className={item.signal}>{item.signal}</i><strong>{item.dimension}</strong><span>{item.note}</span></li>)}</ul>
        </section>
      </main>}
    </div>
  </div>;
}
