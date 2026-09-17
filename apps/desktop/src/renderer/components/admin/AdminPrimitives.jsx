import { CheckCircle2, Search, XCircle } from "lucide-react";
import { roleLabel, statusLabel } from "./adminUtils";

export function SectionHeader({ eyebrow, title, description, actions }) {
  return <div className="admin-section-header"><div>{eyebrow && <span>{eyebrow}</span>}<h3>{title}</h3><p>{description}</p></div>{actions && <div className="admin-section-actions">{actions}</div>}</div>;
}

export function SearchField({ value, onChange, placeholder = "搜索" }) {
  return <label className="admin-search"><Search size={16} /><input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} /></label>;
}

export function Field({ label, hint, children }) {
  return <label className="admin-field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>;
}

export function Avatar({ name }) { return <span className="admin-avatar">{String(name || "U").slice(0, 1).toUpperCase()}</span>; }

export function StatusBadge({ status }) {
  const ok = ["active", "paid", "ready"].includes(status);
  const pending = ["pending", "created"].includes(status);
  return <span className={`admin-status ${ok ? "ok" : pending ? "pending" : "muted"}`}>{ok ? <CheckCircle2 size={13} /> : <XCircle size={13} />}{statusLabel(status)}</span>;
}

export function RoleBadge({ role }) { return <span className={`admin-role admin-role-${role}`}>{roleLabel(role)}</span>; }

export function EmptyState({ title, description }) { return <div className="admin-empty"><strong>{title}</strong>{description && <span>{description}</span>}</div>; }

export function AdminSkeleton() { return <div className="admin-skeleton" aria-label="正在载入管理后台"><i /><i /><i /><i /><span /><span /></div>; }
