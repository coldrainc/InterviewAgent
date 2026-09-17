import { useEffect, useMemo, useState } from "react";
import { Check, Clock3, CreditCard, Save, Sparkles } from "lucide-react";
import { EmptyState, Field, SearchField, SectionHeader, StatusBadge } from "./AdminPrimitives";
import { formatDate, planDraftChanged, shortId } from "./adminUtils";
import { InfiniteScrollSentinel } from "../common/InfiniteScrollSentinel";

export function AdminBillingPanel({ plans, orders, actions, busy, hasMore, loadingMore }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const filteredOrders = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return orders.filter((order) => (status === "all" || order.status === status)
      && (!keyword || [order.external_order_id, order.id, order.user_id, order.payment_provider].some((value) => String(value || "").toLowerCase().includes(keyword))));
  }, [orders, query, status]);
  const paidOrders = orders.filter((item) => item.status === "paid");
  const revenue = paidOrders.reduce((sum, item) => sum + Number(item.amount_credits || 0), 0);

  return <div className="admin-billing-layout">
    <section className="admin-workspace">
      <SectionHeader eyebrow="商品配置" title="付费套餐" description="控制用户看到的售价、到账积分和有效期。" />
      <div className="admin-plan-grid">{plans.map((plan, index) => <PlanEditor key={plan.code} plan={plan} featured={index === 1} actions={actions} busy={busy} />)}</div>
    </section>
    <section className="admin-workspace">
      <SectionHeader eyebrow="支付交付" title="订单流水" description="检查支付状态、渠道和实际入账额度。" actions={<SearchField value={query} onChange={setQuery} placeholder="搜索订单或用户" />} />
      <div className="admin-inline-summary"><span><CreditCard size={15} />已支付 <strong>{paidOrders.length}</strong></span><span><Clock3 size={15} />待完成 <strong>{orders.length - paidOrders.length}</strong></span><span>累计支付 <strong>{revenue.toFixed(2)}</strong></span></div>
      <div className="admin-filter-bar">{[["all", "全部"], ["paid", "已支付"], ["pending", "待支付"], ["created", "已创建"]].map(([value, label]) => <button type="button" key={value} className={status === value ? "active" : ""} onClick={() => setStatus(value)}>{label}</button>)}</div>
      <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>订单号</th><th>用户</th><th>渠道</th><th>支付金额</th><th>到账积分</th><th>状态</th><th>创建时间</th></tr></thead><tbody>{filteredOrders.map((order) => <tr key={order.id}><td><code title={order.external_order_id || order.id}>{shortId(order.external_order_id || order.id)}</code></td><td className="admin-truncate-cell" title={order.user_id}>{order.user_id}</td><td>{paymentLabel(order.payment_provider)}</td><td><strong>{order.amount_credits}</strong></td><td>{order.credited_amount}</td><td><StatusBadge status={order.status} /></td><td>{formatDate(order.created_at)}</td></tr>)}</tbody></table></div>
      {!filteredOrders.length && <EmptyState title="没有匹配的订单" description="这里会展示服务端创建的真实支付订单。" />}
      <InfiniteScrollSentinel hasMore={Boolean(hasMore)} loading={loadingMore} error="" onLoadMore={() => actions.loadMore("orders")} />
    </section>
  </div>;
}

function PlanEditor({ plan, featured, actions, busy }) {
  const [draft, setDraft] = useState(plan);
  useEffect(() => setDraft(plan), [plan]);
  const changed = planDraftChanged(plan, draft);
  const update = (key, value) => setDraft((current) => ({ ...current, [key]: value }));
  return <article className={`admin-plan ${featured ? "featured" : ""}`}>
    <header><div><span>{featured && <em><Sparkles size={12} />推荐</em>}<small>{draft.code}</small></span><input className="admin-plan-name" value={draft.name} onChange={(event) => update("name", event.target.value)} aria-label="套餐名称" /></div><label className="admin-switch icon-only"><input type="checkbox" checked={draft.enabled} onChange={(event) => update("enabled", event.target.checked)} /><span /></label></header>
    <div className="admin-plan-price"><strong>{draft.price_credits}</strong><span>积分售价</span></div>
    <div className="admin-plan-fields"><Field label="售价"><input type="number" min="0" value={draft.price_credits} onChange={(event) => update("price_credits", event.target.value)} /></Field><Field label="到账积分"><input type="number" min="0" value={draft.included_credits} onChange={(event) => update("included_credits", event.target.value)} /></Field><Field label="有效期（天）"><input type="number" min="1" value={draft.duration_days} onChange={(event) => update("duration_days", Number(event.target.value))} /></Field></div>
    <div className="admin-plan-features">{(draft.features || []).map((feature) => <span key={feature}><Check size={13} />{feature}</span>)}</div>
    <footer><small className={changed ? "changed" : ""}>{changed ? "有未保存修改" : draft.enabled ? "正在售卖" : "已下架"}</small><button className="admin-button primary compact" type="button" disabled={busy || !changed || !draft.name.trim()} onClick={() => actions.updatePlan(plan.code, { ...draft, features: draft.features || [] })}><Save size={15} />保存</button></footer>
  </article>;
}

function paymentLabel(provider) { return ({ alipay: "支付宝", wechat: "微信支付", mock: "测试支付" })[provider] || provider || "-"; }
