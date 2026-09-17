import { useEffect, useMemo, useState } from "react";
import { Coins, MoreHorizontal, ShieldCheck, UserCheck, UserMinus, X } from "lucide-react";
import { Avatar, EmptyState, Field, RoleBadge, SearchField, SectionHeader, StatusBadge } from "./AdminPrimitives";
import { formatDate, roleLabel } from "./adminUtils";
import { InfiniteScrollSentinel } from "../common/InfiniteScrollSentinel";

const STATUS_FILTERS = [["all", "全部"], ["active", "正常"], ["suspended", "已停用"]];

export function AdminUsersPanel({ account, users, actions, busy, hasMore, loadingMore }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [selected, setSelected] = useState(null);
  const filtered = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return users.filter((user) => (status === "all" || user.status === status)
      && (!keyword || [user.display_name, user.email, user.user_id].some((value) => String(value || "").toLowerCase().includes(keyword))));
  }, [users, query, status]);

  const summary = {
    active: users.filter((item) => item.status === "active").length,
    suspended: users.filter((item) => item.status === "suspended").length,
    admins: users.filter((item) => item.roles?.includes("admin")).length
  };

  return <section className="admin-workspace">
    <SectionHeader eyebrow="身份与额度" title="用户工作台" description="查询账户、处理访问状态、角色和积分。" actions={<SearchField value={query} onChange={setQuery} placeholder="搜索昵称、邮箱或用户 ID" />} />
    <div className="admin-inline-summary"><span><UserCheck size={15} />正常 <strong>{summary.active}</strong></span><span><UserMinus size={15} />停用 <strong>{summary.suspended}</strong></span><span><ShieldCheck size={15} />管理员 <strong>{summary.admins}</strong></span></div>
    <div className="admin-filter-bar" role="group" aria-label="筛选用户状态">{STATUS_FILTERS.map(([value, label]) => <button type="button" key={value} className={status === value ? "active" : ""} onClick={() => setStatus(value)}>{label}<em>{value === "all" ? users.length : users.filter((item) => item.status === value).length}</em></button>)}</div>
    <div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>用户</th><th>状态</th><th>角色</th><th>积分余额</th><th>试用</th><th>注册时间</th><th aria-label="操作" /></tr></thead><tbody>{filtered.map((user) => <tr key={user.user_id}>
      <td><div className="admin-user-cell"><Avatar name={user.display_name || user.user_id} /><span><strong>{user.display_name || "未设置昵称"}{user.user_id === account.user_id && <em>当前账号</em>}</strong><small>{user.email || user.user_id}</small></span></div></td>
      <td><StatusBadge status={user.status} /></td><td><div className="admin-role-cell">{user.roles?.length ? user.roles.map((role) => <RoleBadge role={role} key={role} />) : <RoleBadge role="user" />}</div></td>
      <td><strong className="admin-balance">{user.credit_balance}</strong></td><td>{user.trial_uses_remaining}</td><td>{formatDate(user.created_at)}</td>
      <td><button className="admin-row-action" type="button" onClick={() => setSelected(user)} aria-label={`管理 ${user.display_name || user.user_id}`} title="管理用户"><MoreHorizontal size={18} /></button></td>
    </tr>)}</tbody></table></div>
    {!filtered.length && <EmptyState title="没有匹配的用户" description="调整搜索词或筛选条件后再试。" />}
    <InfiniteScrollSentinel hasMore={Boolean(hasMore)} loading={loadingMore} error="" onLoadMore={() => actions.loadMore("users")} />
    {selected && <UserActionDrawer user={users.find((item) => item.user_id === selected.user_id) || selected} isSelf={selected.user_id === account.user_id} busy={busy} actions={actions} onClose={() => setSelected(null)} />}
  </section>;
}

function UserActionDrawer({ user, isSelf, busy, actions, onClose }) {
  const [mode, setMode] = useState("status");
  const [reason, setReason] = useState("");
  const [amount, setAmount] = useState("10");
  const [role, setRole] = useState("support");
  useEffect(() => {
    const close = (event) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);

  async function submit(event) {
    event.preventDefault();
    if (reason.trim().length < 2) return;
    let ok = false;
    if (mode === "balance") ok = await actions.adjustBalance(user.user_id, amount, reason);
    else if (mode === "role") ok = await actions.grantRole(user.user_id, role, reason);
    else ok = await actions.updateUserStatus(user.user_id, user.status === "active" ? "suspended" : "active", reason);
    if (ok) onClose();
  }

  return <div className="admin-drawer-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}><aside className="admin-drawer" role="dialog" aria-modal="true" aria-label="用户管理">
    <header><div className="admin-drawer-user"><Avatar name={user.display_name || user.user_id} /><div><h3>{user.display_name || "未设置昵称"}</h3><p>{user.email || user.user_id}</p></div></div><button type="button" className="admin-icon-button" onClick={onClose} aria-label="关闭"><X size={18} /></button></header>
    <div className="admin-user-facts"><div><span>状态</span><StatusBadge status={user.status} /></div><div><span>积分余额</span><strong>{user.credit_balance}</strong></div><div><span>剩余试用</span><strong>{user.trial_uses_remaining}</strong></div><div><span>注册时间</span><strong>{formatDate(user.created_at)}</strong></div></div>
    <nav className="admin-action-tabs">{[["status", "访问状态", UserCheck], ["balance", "积分", Coins], ["role", "角色", ShieldCheck]].map(([value, label, Icon]) => <button type="button" key={value} className={mode === value ? "active" : ""} onClick={() => setMode(value)}><Icon size={15} />{label}</button>)}</nav>
    <form onSubmit={submit}>
      {mode === "status" && <div className={`admin-operation-note ${user.status === "active" ? "danger" : "success"}`}><strong>{user.status === "active" ? "停用这个账户" : "恢复这个账户"}</strong><p>{user.status === "active" ? "停用后，现有登录会话会失效，用户需要管理员恢复后才能重新登录。" : "恢复后，用户可以重新登录并继续使用原有数据。"}</p>{isSelf && user.status === "active" && <small>不能停用当前登录的管理员账户。</small>}</div>}
      {mode === "balance" && <Field label="积分变更" hint="填写负数表示扣减"><input type="number" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} /></Field>}
      {mode === "role" && <><Field label="授予角色"><select value={role} onChange={(event) => setRole(event.target.value)}><option value="support">客服支持</option><option value="admin">管理员</option></select></Field><div className="admin-current-roles"><span>当前角色</span><div>{user.roles?.length ? user.roles.map((currentRole) => <span key={currentRole}><RoleBadge role={currentRole} /><button type="button" disabled={busy || reason.trim().length < 2 || (isSelf && currentRole === "admin")} onClick={async () => { const ok = await actions.revokeRole(user.user_id, currentRole, reason); if (ok) onClose(); }} aria-label={`移除 ${roleLabel(currentRole)} 角色`}><X size={13} /></button></span>) : <RoleBadge role="user" />}</div></div></>}
      <Field label="操作原因" hint={`${reason.trim().length}/240 · 将写入审计记录`}><textarea value={reason} onChange={(event) => setReason(event.target.value)} maxLength={240} placeholder="说明为什么需要执行本次操作" /></Field>
      <footer><button type="button" className="admin-button ghost" onClick={onClose}>取消</button><button type="submit" className={`admin-button ${mode === "status" && user.status === "active" ? "danger" : "primary"}`} disabled={busy || reason.trim().length < 2 || (mode === "status" && isSelf && user.status === "active")}>{busy ? "处理中..." : "确认操作"}</button></footer>
    </form>
  </aside></div>;
}
