import { Activity, ArrowRight, Bot, CircleDollarSign, CreditCard, ShieldAlert, ShieldCheck, UserMinus, Users, WalletCards } from "lucide-react";
import { Avatar, EmptyState, StatusBadge } from "./AdminPrimitives";
import { actionLabel, compactNumber, formatDate } from "./adminUtils";

export function AdminOverview({ state, onNavigate }) {
  const { dashboard, users, models, plans, orders, audit } = state;
  const suspendedUsers = users.filter((item) => item.status === "suspended");
  const missingModels = models.filter((item) => item.enabled && item.credential_status !== "configured");
  const pendingOrders = orders.filter((item) => item.status === "pending" || item.status === "created");
  const attention = [
    { count: dashboard.critical_events_30d || 0, label: "严重安全事件", detail: "近 30 天需要复核", icon: ShieldAlert, tab: "audit", tone: "danger" },
    { count: missingModels.length, label: "模型配置不完整", detail: "已启用但服务端凭据不可用", icon: Bot, tab: "models", tone: "warning" },
    { count: suspendedUsers.length, label: "已停用用户", detail: "复核状态或恢复访问", icon: UserMinus, tab: "users", tone: "neutral" },
    { count: pendingOrders.length, label: "待完成订单", detail: "检查支付结果和入账状态", icon: CreditCard, tab: "billing", tone: "neutral" }
  ];
  const metrics = [
    { label: "用户总数", value: dashboard.users_total || 0, detail: `${dashboard.users_active || 0} 个正常`, icon: Users, tab: "users", tone: "blue" },
    { label: "30 天调用", value: compactNumber(dashboard.generations_30d), detail: `${compactNumber(dashboard.tokens_30d)} Tokens`, icon: Activity, tab: "models", tone: "teal" },
    { label: "30 天收入", value: dashboard.revenue_credits_30d || "0", detail: `${dashboard.paid_orders_30d || 0} 笔已支付`, icon: CircleDollarSign, tab: "billing", tone: "amber" },
    { label: "安全告警", value: dashboard.critical_events_30d || 0, detail: "近 30 天严重事件", icon: ShieldCheck, tab: "audit", tone: "red" }
  ];
  const enabledModels = models.filter((item) => item.enabled);
  const configuredModels = enabledModels.filter((item) => item.credential_status === "configured");
  const activePlans = plans.filter((item) => item.enabled);

  return <div className="admin-overview">
    <div className="admin-metric-grid">{metrics.map(({ label, value, detail, icon: Icon, tab, tone }) => <button type="button" className={`admin-metric ${tone}`} key={label} onClick={() => onNavigate(tab)}>
      <span><Icon size={18} /></span><small>{label}</small><strong>{value}</strong><p>{detail}</p><ArrowRight size={15} className="admin-metric-arrow" />
    </button>)}</div>

    <section className="admin-command-band">
      <div className="admin-command-copy"><span>运营待办</span><h3>{attention.reduce((sum, item) => sum + Number(item.count), 0)} 项需要关注</h3><p>优先处理影响登录、模型调用和支付交付的问题。</p></div>
      <div className="admin-attention-list">{attention.map(({ count, label, detail, icon: Icon, tab, tone }) => <button type="button" key={label} className={tone} onClick={() => onNavigate(tab)} disabled={!count}>
        <span><Icon size={17} /></span><div><strong>{label}</strong><small>{count ? detail : "当前无异常"}</small></div><em>{count}</em><ArrowRight size={15} />
      </button>)}</div>
    </section>

    <div className="admin-overview-grid">
      <section className="admin-plain-section"><header><div><span>服务供给</span><h3>关键链路状态</h3></div><button type="button" onClick={() => onNavigate("models")}>查看模型 <ArrowRight size={14} /></button></header>
        <div className="admin-health-grid"><HealthItem icon={Users} label="用户服务" value={`${dashboard.users_active || 0} 个活跃账号`} ok={(dashboard.users_active || 0) > 0} /><HealthItem icon={Bot} label="模型供给" value={`${configuredModels.length}/${enabledModels.length} 个可调用`} ok={enabledModels.length > 0 && configuredModels.length === enabledModels.length} /><HealthItem icon={WalletCards} label="在售套餐" value={`${activePlans.length} 个已上架`} ok={activePlans.length > 0} /><HealthItem icon={CircleDollarSign} label="付费链路" value={`${dashboard.paid_orders_30d || 0} 笔近 30 天订单`} ok /></div>
      </section>
      <section className="admin-plain-section"><header><div><span>新用户</span><h3>最近注册</h3></div><button type="button" onClick={() => onNavigate("users")}>全部用户 <ArrowRight size={14} /></button></header>
        <div className="admin-compact-list">{users.slice(0, 4).map((user) => <div key={user.user_id}><Avatar name={user.display_name || user.user_id} /><span><strong>{user.display_name || "未设置昵称"}</strong><small>{user.email || user.user_id}</small></span><StatusBadge status={user.status} /></div>)}{!users.length && <EmptyState title="暂无用户数据" />}</div>
      </section>
      <section className="admin-plain-section admin-recent-audit"><header><div><span>管理记录</span><h3>最近操作</h3></div><button type="button" onClick={() => onNavigate("audit")}>完整审计 <ArrowRight size={14} /></button></header>
        <div className="admin-compact-list">{audit.slice(0, 4).map((item) => <div key={item.id}><span className="admin-audit-icon"><ShieldCheck size={15} /></span><span><strong>{actionLabel(item.action)}</strong><small>{item.target || "全局"}</small></span><time>{formatDate(item.created_at)}</time></div>)}{!audit.length && <EmptyState title="暂无管理员操作" />}</div>
      </section>
    </div>
  </div>;
}

function HealthItem({ icon: Icon, label, value, ok }) { return <div className={ok ? "ok" : "warning"}><span><Icon size={17} /></span><div><small>{label}</small><strong>{value}</strong></div><i>{ok ? "正常" : "需处理"}</i></div>; }
