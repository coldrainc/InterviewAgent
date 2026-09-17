import { CheckCircle2, Coins, CreditCard, Database, QrCode, Settings, ShieldCheck, UserRound, X } from "lucide-react";
import { ModelSelector } from "../common/ModelSelector";
import { QRCodeImage } from "../common/QRCodeImage";
import { PrivacyDataPanel } from "../../features/privacy/PrivacyDataPanel";
import { formatCredits } from "../../utils/interview";

export function AccountEntry({ account, active, onOpen }) {
  return (
    <button type="button" className={`account-entry ${active ? "active" : ""}`} onClick={onOpen}>
      <span className="account-entry-icon">
        <UserRound size={17} />
      </span>
      <span className="account-entry-main">
        <strong>{account ? account.display_name || account.email || "我的账户" : "登录 / 注册"}</strong>
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
  paymentState,
  billingPlans,
  adminState,
  onPaymentStateChange,
  onCreatePayment,
  onReloadAdmin,
  onAdminFieldChange,
  onGrantRole,
  onRevokeRole,
  onCreateReviewSiteTestData,
  client,
  onBack
}) {
  const rechargeOptions = Array.isArray(billingPlans) && billingPlans.length
    ? billingPlans
    : [
        { code: "", name: "10 积分", price_credits: "10", included_credits: "10" },
        { code: "", name: "50 积分", price_credits: "50", included_credits: "50" },
        { code: "", name: "100 积分", price_credits: "100", included_credits: "100" }
      ];
  if (account) {
    return (
      <section className="account-center">
        <div className="account-hero">
          <div className="account-avatar">
            <UserRound size={28} />
          </div>
          <div>
            <span className="eyebrow">个人中心</span>
            <h3>{account.display_name || "我的账户"}</h3>
            <p>{account.email || "已登录"}</p>
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
            <p className="resume-hint">选择充值金额并完成支付，积分会自动到账。</p>
            <div className="payment-panel">
              <div className="payment-options" role="group" aria-label="充值金额">
                {rechargeOptions.map((plan) => (
                  <button
                    key={`${plan.code}-${plan.price_credits}`}
                    type="button"
                    className={paymentState?.planCode === plan.code ? "active" : ""}
                    onClick={() => onPaymentStateChange?.((current) => ({
                      ...current,
                      planCode: plan.code,
                      amount: plan.price_credits,
                      creditedAmount: plan.included_credits
                    }))}
                  >
                    <strong>{plan.name}</strong>
                    <small>到账 {plan.included_credits} 积分 · {plan.duration_days || 30} 天</small>
                  </button>
                ))}
              </div>
              <div className="payment-actions">
                <button
                  type="button"
                  className="secondary-action inline"
                  disabled={paymentState?.status === "loading"}
                  onClick={() => onCreatePayment?.("alipay", paymentState?.amount || rechargeOptions[0].price_credits, paymentState?.planCode || rechargeOptions[0].code)}
                >
                  <CreditCard size={15} />
                  支付宝
                </button>
                <button
                  type="button"
                  className="secondary-action inline"
                  disabled={paymentState?.status === "loading"}
                  onClick={() => onCreatePayment?.("wechat", paymentState?.amount || rechargeOptions[0].price_credits, paymentState?.planCode || rechargeOptions[0].code)}
                >
                  <QrCode size={15} />
                  微信
                </button>
              </div>
              <PaymentStatus state={paymentState} />
            </div>
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
              <span>优先使用免费次数，之后按所选模型的实际用量扣除积分。</span>
            </div>
          </section>

          <section className="account-block">
            <div className="panel-heading">
              <span>个人信息</span>
            </div>
            <div className="profile-list">
              <ProfileItem label="昵称" value={account.display_name || "未设置"} />
              <ProfileItem label="邮箱" value={account.email || "-"} />
              <ProfileItem label="账户类型" value={account.role === "admin" ? "管理员" : "个人账户"} />
            </div>
          </section>

          <section className="account-block">
            <div className="panel-heading">
              <span>安全</span>
            </div>
            <div className="security-list">
              <div>
                <ShieldCheck size={16} />
                <span>登录信息会被安全保存，异常登录会自动失效。</span>
              </div>
              <div>
                <Database size={16} />
                <span>上传的简历、题库和回答会经过安全检查，降低恶意内容风险。</span>
              </div>
            </div>
          </section>

          <PrivacyDataPanel client={client} accountKey={`${account.tenant_id}:${account.user_id}`} />

          {account.role === "admin" && (
            <AdminSecurityPanel
              state={adminState}
              onReload={onReloadAdmin}
              onFieldChange={onAdminFieldChange}
              onGrantRole={onGrantRole}
              onRevokeRole={onRevokeRole}
              onCreateReviewSiteTestData={onCreateReviewSiteTestData}
            />
          )}
        </div>
      </section>
    );
  }

  return (
    <section className="account-center">
      <div className="account-auth-layout">
        <div className="account-auth-copy">
          <span className="eyebrow">个人中心</span>
          <h3>登录后继续使用 Interview Agent</h3>
          <p>账户用于保存简历、历史会话、试用额度、积分余额和模型用量。</p>
          <div className="auth-benefits">
            <div><CheckCircle2 size={16} />默认领取 2 次试用</div>
            <div><CheckCircle2 size={16} />多端共享简历和历史记录</div>
            <div><CheckCircle2 size={16} />用量透明，完成后展示积分明细</div>
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

function AdminSecurityPanel({ state, onReload, onFieldChange, onGrantRole, onRevokeRole, onCreateReviewSiteTestData }) {
  const roles = Array.isArray(state?.roles) ? state.roles : [];
  const events = Array.isArray(state?.events) ? state.events : [];
  return (
    <section className="account-block wide">
      <div className="panel-heading">
        <span>管理后台</span>
        <button type="button" className="secondary-action inline compact" onClick={onReload}>
          刷新
        </button>
      </div>
      <div className="admin-test-data-row">
        <div>
          <strong>复习站测试数据</strong>
          <p>创建一份匿名通用计划，仅供非生产环境验证交互。</p>
        </div>
        <button
          type="button"
          className="secondary-action inline compact"
          disabled={state?.testDataStatus === "loading"}
          onClick={onCreateReviewSiteTestData}
        >
          {state?.testDataStatus === "loading" ? "创建中" : "创建测试计划"}
        </button>
      </div>
      {state?.testDataMessage && (
        <p className={`resume-hint ${state.testDataStatus === "error" ? "error" : ""}`}>
          {state.testDataMessage}
        </p>
      )}
      <div className="admin-role-form">
        <input
          value={state?.userId || ""}
          placeholder="用户邮箱"
          onChange={(event) => onFieldChange?.("userId", event.target.value)}
        />
        <select value={state?.role || "support"} onChange={(event) => onFieldChange?.("role", event.target.value)}>
          <option value="support">客服人员</option>
          <option value="admin">管理员</option>
        </select>
        <button
          type="button"
          className="primary-action inline compact"
          disabled={state?.status === "saving" || !state?.userId?.trim()}
          onClick={onGrantRole}
        >
          授权
        </button>
      </div>
      {state?.error && <p className="resume-hint error">{state.error}</p>}
      <div className="admin-grid">
        <div className="admin-list">
          <strong>角色</strong>
          {roles.length ? roles.slice(0, 8).map((role) => (
            <div className="admin-row" key={`${role.user_id}-${role.role}`}>
              <span>
                <b>{roleLabel(role.role)}</b>
                <small>{formatAccountIdentifier(role.user_id)}</small>
              </span>
              {role.role !== "user" && (
                <button type="button" className="danger-inline" onClick={() => onRevokeRole?.(role)}>
                  撤销
                </button>
              )}
            </div>
          )) : <p className="resume-hint">暂无额外角色。</p>}
        </div>
        <div className="admin-list">
          <strong>安全事件</strong>
          {events.length ? events.slice(0, 8).map((event) => (
            <div className="admin-row event" key={event.id}>
              <span>
                <b>{securityEventLabel(event.event_type)}</b>
                <small>{severityLabel(event.severity)} · {formatDate(event.created_at)}</small>
              </span>
            </div>
          )) : <p className="resume-hint">暂无安全事件。</p>}
        </div>
      </div>
    </section>
  );
}

function formatAccountIdentifier(value) {
  const text = String(value || "");
  return text.startsWith("email:") ? text.slice(6) : text || "未知账户";
}

function roleLabel(value) {
  return { admin: "管理员", support: "客服人员", user: "普通用户" }[value] || "自定义角色";
}

function severityLabel(value) {
  return { critical: "紧急", high: "高风险", medium: "需关注", low: "一般", info: "提示" }[value] || "需关注";
}

function securityEventLabel(value) {
  const labels = {
    login_failed: "登录失败",
    login_succeeded: "登录成功",
    token_reuse: "异常登录已拦截",
    role_granted: "账户权限已更新",
    role_revoked: "账户权限已撤销"
  };
  return labels[value] || "账户安全提醒";
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString();
}

function PaymentStatus({ state }) {
  if (!state || state.status === "idle") {
    return <p className="resume-hint">选择金额后使用支付宝或微信完成充值。</p>;
  }
  if (state.status === "loading") {
    return <p className="resume-hint active">正在创建支付订单...</p>;
  }
  if (state.status === "error") {
    return <p className="resume-hint error">{state.error}</p>;
  }
  if (state.status === "paid") {
    return <p className="resume-hint success">支付成功，积分已入账。</p>;
  }
  const order = state.order || {};
  if (state.provider === "wechat" && order.code_url) {
    return (
      <div className="payment-result">
        <QRCodeImage value={order.code_url} alt="微信支付二维码" />
        <p className="resume-hint active">请使用微信扫码支付，支付成功后会自动刷新积分。</p>
      </div>
    );
  }
  if (state.provider === "alipay" && order.pay_url) {
    return (
      <p className="resume-hint active">
        已打开支付宝收银台。支付完成后本页会自动刷新积分。
      </p>
    );
  }
  return <p className="resume-hint active">订单已创建，等待支付回调。</p>;
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

export function AuthForm({ authState, onAuthChange, onAuthSubmit }) {
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
