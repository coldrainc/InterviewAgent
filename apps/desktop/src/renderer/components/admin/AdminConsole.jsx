import { useMemo, useState } from "react";
import { Activity, Bot, CreditCard, RefreshCw, ShieldCheck, Users } from "lucide-react";
import { AdminOverview } from "./AdminOverview";
import { AdminUsersPanel } from "./AdminUsersPanel";
import { AdminModelsPanel } from "./AdminModelsPanel";
import { AdminBillingPanel } from "./AdminBillingPanel";
import { AdminAuditPanel } from "./AdminAuditPanel";
import { AdminSkeleton } from "./AdminPrimitives";

const TABS = [
  ["overview", "运营概览", Activity],
  ["users", "用户", Users],
  ["models", "模型", Bot],
  ["billing", "商业化", CreditCard],
  ["audit", "审计", ShieldCheck]
];

export function AdminConsole({ account, state, actions }) {
  const [tab, setTab] = useState("overview");
  const tabCounts = useMemo(() => ({
    users: state.users.length,
    models: state.models.filter((item) => item.enabled).length,
    billing: state.orders.filter((item) => item.status === "pending" || item.status === "created").length,
    audit: state.audit.length
  }), [state.users, state.models, state.orders, state.audit]);

  if (account?.role !== "admin" && account?.role !== "server") return null;

  return <section className="admin-console">
    <header className="admin-console-header">
      <div className="admin-console-heading">
        <span className="admin-eyebrow"><ShieldCheck size={14} /> 管理员工作区</span>
        <h2>运营控制台</h2>
        <p>从用户状态到模型供给，在一个工作台内完成日常运营。</p>
      </div>
      <div className="admin-header-actions">
        <span className="admin-live-status"><i />服务运行中</span>
        <button className="admin-icon-button" type="button" onClick={actions.load} title="刷新后台数据" aria-label="刷新后台数据">
          <RefreshCw size={17} className={state.status === "loading" ? "spin" : ""} />
        </button>
      </div>
    </header>

    <nav className="admin-tabs" aria-label="管理后台导航">
      {TABS.map(([value, label, Icon]) => <button key={value} type="button" className={tab === value ? "active" : ""} onClick={() => setTab(value)}>
        <Icon size={16} /><span>{label}</span>{tabCounts[value] > 0 && <em>{tabCounts[value]}</em>}
      </button>)}
    </nav>

    <div className="admin-feedback" aria-live="polite">
      {state.error && <div className="admin-alert error">{state.error}</div>}
      {state.message && <div className="admin-alert success">{state.message}</div>}
    </div>

    {state.status === "loading" && !state.users.length ? <AdminSkeleton /> : <div className="admin-console-body">
      {tab === "overview" && <AdminOverview state={state} onNavigate={setTab} />}
      {tab === "users" && <AdminUsersPanel account={account} users={state.users} actions={actions} busy={state.status === "saving"} hasMore={state.pages?.users} loadingMore={state.status === "loading-more"} />}
      {tab === "models" && <AdminModelsPanel models={state.models} actions={actions} busy={state.status === "saving"} />}
      {tab === "billing" && <AdminBillingPanel plans={state.plans} orders={state.orders} actions={actions} busy={state.status === "saving"} hasMore={state.pages?.orders} loadingMore={state.status === "loading-more"} />}
      {tab === "audit" && <AdminAuditPanel audit={state.audit} actions={actions} hasMore={state.pages?.audit} loadingMore={state.status === "loading-more"} />}
    </div>}
  </section>;
}
