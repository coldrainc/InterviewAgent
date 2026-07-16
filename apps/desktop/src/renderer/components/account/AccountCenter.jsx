import { CheckCircle2, Coins, Database, Settings, ShieldCheck, UserRound, X } from "lucide-react";
import { ModelSelector } from "../common/ModelSelector";
import { formatCredits } from "../../utils/interview";

export function AccountEntry({ account, active, onOpen }) {
  return (
    <button type="button" className={`account-entry ${active ? "active" : ""}`} onClick={onOpen}>
      <span className="account-entry-icon">
        <UserRound size={17} />
      </span>
      <span className="account-entry-main">
        <strong>{account ? account.display_name || account.user_id : "登录 / 注册"}</strong>
        <small>
          {account
            ? `${formatCredits(account.credit_balance)} 积分 · ${account.trial_uses_remaining} 次试用`
            : "账户、充值和个人信息"}
        </small>
      </span>
      <Settings size={15} />
    </button>
  );
}

export function AccountCenter({
  account,
  authState,
  modelOptions,
  selectedModelId,
  onAuthChange,
  onAuthSubmit,
  onDevLogin,
  onLogout,
  onSelectModel,
  onBack
}) {
  if (account) {
    return (
      <section className="account-center">
        <div className="account-hero">
          <div className="account-avatar">
            <UserRound size={28} />
          </div>
          <div>
            <span className="eyebrow">Account</span>
            <h3>{account.display_name || account.user_id}</h3>
            <p>{account.email || account.user_id}</p>
          </div>
          <div className="account-hero-actions">
            <button type="button" className="secondary-action inline" onClick={onBack}>返回面试</button>
            <button type="button" className="danger-inline large" onClick={onLogout}>退出登录</button>
          </div>
        </div>

        <div className="account-grid">
          <section className="account-block">
            <div className="panel-heading">
              <span>额度</span>
            </div>
            <div className="credit-grid large">
              <div>
                <small>剩余试用</small>
                <b>{account.trial_uses_remaining}</b>
              </div>
              <div>
                <small>积分余额</small>
                <b>{formatCredits(account.credit_balance)}</b>
              </div>
            </div>
            <p className="resume-hint">生产环境充值会由支付平台创建订单，支付成功后通过服务端签名回调入账。</p>
          </section>

          <section className="account-block">
            <div className="panel-heading">
              <span>模型计费</span>
            </div>
            <ModelSelector
              models={modelOptions}
              selectedModelId={selectedModelId}
              onSelectModel={onSelectModel}
            />
            <div className="billing-note">
              <Coins size={15} />
              <span>试用额度优先消耗；试用用完后按模型 token 用量扣除积分。</span>
            </div>
          </section>

          <section className="account-block">
            <div className="panel-heading">
              <span>个人信息</span>
            </div>
            <div className="profile-list">
              <ProfileItem label="租户" value={account.tenant_id} />
              <ProfileItem label="用户 ID" value={account.user_id} />
              <ProfileItem label="平台" value={account.platform} />
              <ProfileItem label="邮箱" value={account.email || "-"} />
            </div>
          </section>

          <section className="account-block">
            <div className="panel-heading">
              <span>安全</span>
            </div>
            <div className="security-list">
              <div>
                <ShieldCheck size={16} />
                <span>桌面端 token 仅保存在当前 Electron 主进程内存中。</span>
              </div>
              <div>
                <Database size={16} />
                <span>简历、会话和用量记录按当前后端存储策略保存。</span>
              </div>
            </div>
          </section>
        </div>
      </section>
    );
  }

  return (
    <section className="account-center">
      <div className="account-auth-layout">
        <div className="account-auth-copy">
          <span className="eyebrow">Account</span>
          <h3>登录后继续使用 Interview Agent</h3>
          <p>账户用于保存简历、历史会话、试用额度、积分余额和模型用量。</p>
          <div className="auth-benefits">
            <div><CheckCircle2 size={16} />默认领取 2 次试用</div>
            <div><CheckCircle2 size={16} />多端共享简历和历史记录</div>
            <div><CheckCircle2 size={16} />按模型 token 用量扣除积分</div>
          </div>
        </div>
        <div className="auth-card standalone">
          <AuthForm
            authState={authState}
            onAuthChange={onAuthChange}
            onAuthSubmit={onAuthSubmit}
            onDevLogin={onDevLogin}
          />
        </div>
      </div>
    </section>
  );
}

export function AuthDialog({ reason, authState, onAuthChange, onAuthSubmit, onDevLogin, onClose }) {
  return (
    <div className="auth-dialog-backdrop" role="presentation">
      <section className="auth-dialog" role="dialog" aria-modal="true" aria-label="登录">
        <div className="auth-dialog-head">
          <div>
            <span className="eyebrow">Sign in</span>
            <h3>需要先登录</h3>
            {reason && <p>{reason}</p>}
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="关闭登录弹窗">
            <X size={14} />
          </button>
        </div>
        <AuthForm
          authState={authState}
          onAuthChange={onAuthChange}
          onAuthSubmit={onAuthSubmit}
          onDevLogin={onDevLogin}
        />
      </section>
    </div>
  );
}

function AuthForm({ authState, onAuthChange, onAuthSubmit, onDevLogin }) {
  const update = (key, value) => onAuthChange((current) => ({ ...current, [key]: value }));
  return (
    <>
      <div className="panel-heading">
        <span>账户</span>
        <button
          type="button"
          className="text-button"
          onClick={() => update("mode", authState.mode === "login" ? "register" : "login")}
        >
          {authState.mode === "login" ? "注册" : "登录"}
        </button>
      </div>
      <form className="auth-form" onSubmit={onAuthSubmit}>
        {authState.mode === "register" && (
          <input
            value={authState.displayName}
            placeholder="昵称"
            onChange={(event) => update("displayName", event.target.value)}
          />
        )}
        <input
          value={authState.email}
          placeholder="邮箱"
          onChange={(event) => update("email", event.target.value)}
        />
        <input
          type="password"
          value={authState.password}
          placeholder="密码"
          onChange={(event) => update("password", event.target.value)}
        />
        <button type="submit" disabled={authState.status === "loading"}>
          {authState.status === "loading" ? "处理中..." : authState.mode === "login" ? "登录" : "注册并领取试用"}
        </button>
        <button type="button" className="secondary-auth" onClick={onDevLogin}>
          开发账号试用
        </button>
        {authState.status === "error" && <p>{authState.error}</p>}
      </form>
    </>
  );
}

function ProfileItem({ label, value }) {
  return (
    <div className="profile-item">
      <span>{label}</span>
      <strong>{value || "-"}</strong>
    </div>
  );
}
