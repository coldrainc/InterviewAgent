import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check, RotateCcw, Save } from "lucide-react";
import { EmptyState, SearchField, SectionHeader } from "./AdminPrimitives";
import { modelDraftChanged } from "./adminUtils";

export function AdminModelsPanel({ models, actions, busy }) {
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState("all");
  const [availability, setAvailability] = useState("enabled");
  const providers = useMemo(() => [...new Set(models.map((model) => model.provider))].sort(), [models]);
  const filtered = models.filter((model) => {
    const keyword = query.trim().toLowerCase();
    const matchesAvailability = availability === "all" || (availability === "enabled" ? model.enabled : model.credential_status !== "configured");
    return (!keyword || `${model.display_name} ${model.id}`.toLowerCase().includes(keyword)) && (provider === "all" || model.provider === provider) && matchesAvailability;
  });
  const configured = models.filter((item) => item.credential_status === "configured").length;
  const enabled = models.filter((item) => item.enabled).length;
  const defaultModel = models.find((item) => item.is_default);

  return <section className="admin-workspace">
    <SectionHeader eyebrow="模型路由与成本" title="模型供给" description="管理可用模型、默认路由与服务端计费策略。" actions={<SearchField value={query} onChange={setQuery} placeholder="搜索模型" />} />
    <div className="admin-inline-summary"><span>已启用 <strong>{enabled}</strong></span><span>服务可用 <strong>{configured}</strong></span><span>默认路由 <strong>{defaultModel?.display_name || "未设置"}</strong></span></div>
    <div className="admin-model-toolbar"><select value={provider} onChange={(event) => setProvider(event.target.value)} aria-label="供应商筛选"><option value="all">全部供应商</option>{providers.map((item) => <option key={item} value={item}>{item}</option>)}</select><div className="admin-filter-bar">{[["all", "全部"], ["enabled", "已启用"], ["attention", "需配置"]].map(([value, label]) => <button type="button" key={value} className={availability === value ? "active" : ""} onClick={() => setAvailability(value)}>{label}</button>)}</div></div>
    <div className="admin-model-list">{filtered.map((model) => <ModelCard key={model.id} model={model} actions={actions} busy={busy} />)}</div>
    {!filtered.length && <EmptyState title="没有匹配的模型" description="调整供应商或可用状态筛选。" />}
  </section>;
}

function ModelCard({ model, actions, busy }) {
  const [draft, setDraft] = useState(model);
  useEffect(() => setDraft(model), [model]);
  const changed = modelDraftChanged(model, draft);
  const update = (key, value) => setDraft((current) => ({ ...current, [key]: value }));
  async function save() {
    const ok = await actions.updateModel(model.id, { enabled: draft.enabled, is_default: draft.is_default, input_usd_per_1m: draft.input_usd_per_1m, output_usd_per_1m: draft.output_usd_per_1m });
    if (ok) setDraft((current) => ({ ...current }));
  }
  return <article className={`admin-model-card ${draft.is_default ? "is-default" : ""}`}>
    <header><div className="admin-model-identity"><span className="admin-provider-mark">{model.provider.slice(0, 1).toUpperCase()}</span><span><strong>{model.display_name}</strong><small>{model.provider} · {model.category}</small></span></div>{draft.is_default && <em><Check size={13} />默认路由</em>}</header>
    <div className={`admin-credential ${model.credential_status}`}><span>{model.credential_status === "configured" ? <Check size={14} /> : <AlertTriangle size={14} />}</span><div><strong>{model.credential_status === "configured" ? "服务端已配置" : "服务端未配置"}</strong><small>{model.credential_status === "configured" ? "可由后端安全调用" : "启用前需在服务器完成配置"}</small></div></div>
    <div className="admin-model-controls"><label className="admin-switch"><input type="checkbox" checked={draft.enabled} onChange={(event) => update("enabled", event.target.checked)} /><span /><div><strong>提供给用户</strong><small>{draft.enabled ? "已加入模型选择" : "当前不可选择"}</small></div></label><label className="admin-switch"><input type="checkbox" checked={draft.is_default} disabled={!draft.enabled} onChange={(event) => update("is_default", event.target.checked)} /><span /><div><strong>默认模型</strong><small>新会话优先使用</small></div></label></div>
    <div className="admin-price-grid"><label><span>输入价格</span><div><input type="number" min="0" step="0.01" value={draft.input_usd_per_1m} onChange={(event) => update("input_usd_per_1m", event.target.value)} /><em>$/1M</em></div></label><label><span>输出价格</span><div><input type="number" min="0" step="0.01" value={draft.output_usd_per_1m} onChange={(event) => update("output_usd_per_1m", event.target.value)} /><em>$/1M</em></div></label></div>
    <footer><span className={changed ? "changed" : ""}>{changed ? "有未保存修改" : `上下文 ${new Intl.NumberFormat("zh-CN", { notation: "compact" }).format(model.context_window || 0)}`}</span><div><button type="button" className="admin-icon-button" disabled={!changed || busy} onClick={() => setDraft(model)} title="撤销修改" aria-label="撤销修改"><RotateCcw size={15} /></button><button type="button" className="admin-button primary compact" disabled={!changed || busy} onClick={save}><Save size={15} />保存</button></div></footer>
  </article>;
}
