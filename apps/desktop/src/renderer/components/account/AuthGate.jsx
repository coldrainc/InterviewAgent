import { Loader2, Moon, ShieldCheck, Sun } from "lucide-react";
import { AuthForm } from "./AccountCenter";

export function AuthGate({ authReady, authState, theme, onAuthChange, onAuthSubmit, onToggleTheme }) {
  return (
    <main className="auth-gate">
      <header className="auth-gate-header">
        <div className="auth-gate-brand">
          <span className="brand-mark"><img src="./favicon.svg" alt="" aria-hidden="true" /></span>
          <span>
            <strong>Interview Agent</strong>
            <small>AI 面试备考工作台</small>
          </span>
        </div>
        <button
          type="button"
          className="auth-theme-button"
          onClick={onToggleTheme}
          aria-label={theme === "dark" ? "切换到白天模式" : "切换到夜间模式"}
          title={theme === "dark" ? "切换到白天模式" : "切换到夜间模式"}
        >
          {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
        </button>
      </header>

      <section className="auth-gate-content" aria-live="polite">
        <div className="auth-gate-copy">
          <span className="auth-gate-mark"><ShieldCheck size={22} /></span>
          <p className="eyebrow">PRIVATE AI WORKSPACE</p>
          <h1>你的面试准备，<br />从登录后开始。</h1>
          <p>简历、面试记录、错题和复习计划仅在你的账户空间内使用。</p>
        </div>

        <section className="auth-gate-card" aria-label="账户登录">
          {!authReady ? (
            <div className="auth-gate-loading">
              <Loader2 size={20} />
              <span>正在恢复登录状态...</span>
            </div>
          ) : (
            <>
              <div className="auth-gate-card-head">
                <h2>{authState.mode === "register" ? "创建账户" : "欢迎回来"}</h2>
                <p>{authState.mode === "register" ? "注册后开始建立你的专属训练记录。" : "登录后继续上次的面试与复习进度。"}</p>
              </div>
              <AuthForm
                authState={authState}
                onAuthChange={onAuthChange}
                onAuthSubmit={onAuthSubmit}
              />
            </>
          )}
        </section>
      </section>
    </main>
  );
}
