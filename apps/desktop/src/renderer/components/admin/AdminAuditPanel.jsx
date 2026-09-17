import { useMemo, useState } from "react";
import { Bot, CircleDollarSign, CreditCard, ShieldCheck, UserCog } from "lucide-react";
import { EmptyState, SearchField, SectionHeader } from "./AdminPrimitives";
import { actionLabel, formatDate } from "./adminUtils";
import { InfiniteScrollSentinel } from "../common/InfiniteScrollSentinel";

const ACTION_TYPES = [
  ["all", "全部操作"], ["user", "用户与角色"], ["model", "模型策略"], ["billing", "套餐计费"]
];

export function AdminAuditPanel({ audit, actions, hasMore, loadingMore }) {
  const [query, setQuery] = useState("");
  const [type, setType] = useState("all");
  const filtered = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return audit.filter((item) => (type === "all" || auditType(item.action) === type)
      && (!keyword || [actionLabel(item.action), item.actor_id, item.target, JSON.stringify(item.details || {})].some((value) => String(value || "").toLowerCase().includes(keyword))));
  }, [audit, query, type]);

  return <section className="admin-workspace admin-audit-workspace">
    <SectionHeader eyebrow="安全与问责" title="管理员审计" description="追踪关键写操作、操作者、目标与原因。" actions={<SearchField value={query} onChange={setQuery} placeholder="搜索操作者、目标或动作" />} />
    <div className="admin-filter-bar">{ACTION_TYPES.map(([value, label]) => <button type="button" key={value} className={type === value ? "active" : ""} onClick={() => setType(value)}>{label}</button>)}</div>
    <div className="admin-audit-timeline">{filtered.map((item) => <AuditEntry key={item.id} item={item} />)}</div>
    {!filtered.length && <EmptyState title="没有匹配的审计记录" description="关键后台写操作会在这里持续留痕。" />}
    <InfiniteScrollSentinel hasMore={Boolean(hasMore)} loading={loadingMore} error="" onLoadMore={() => actions.loadMore("audit")} />
  </section>;
}

function AuditEntry({ item }) {
  const type = auditType(item.action);
  const Icon = type === "model" ? Bot : type === "billing" ? CreditCard : type === "user" ? UserCog : ShieldCheck;
  const reason = item.details?.reason;
  return <article className={`admin-audit-entry ${type}`}><span className="admin-audit-icon"><Icon size={16} /></span><div className="admin-audit-main"><header><strong>{actionLabel(item.action)}</strong><time>{formatDate(item.created_at)}</time></header><p><span>{item.actor_id || "系统"}</span> 操作了 <span>{item.target || "全局配置"}</span></p>{reason && <small>原因：{reason}</small>}</div></article>;
}

function auditType(action = "") {
  if (action.includes("model")) return "model";
  if (action.includes("plan") || action.includes("billing") || action.includes("balance")) return "billing";
  if (action.includes("user") || action.includes("role")) return "user";
  return "security";
}
