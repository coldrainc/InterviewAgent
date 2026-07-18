import { CheckCircle2, Settings, UserRound } from "lucide-react";
import { interviewModes } from "../../constants/interview";

export function SettingsCenter({ account, profile, settingsState, onModeChange, onBack }) {
  return (
    <section className="settings-center">
      <div className="settings-hero">
        <div className="account-avatar">
          <Settings size={28} />
        </div>
        <div>
          <span className="eyebrow">Settings</span>
          <h3>偏好设置</h3>
          <p>{account ? account.display_name || account.user_id : "登录后同步到服务端"}</p>
        </div>
        <button type="button" className="secondary-action inline" onClick={onBack}>返回面试</button>
      </div>

      <div className="settings-grid">
        <section className="settings-block">
          <div className="panel-heading">
            <span>默认工作模式</span>
          </div>
          <div className="settings-mode-grid">
            {interviewModes.map((mode) => (
              <button
                key={mode.value}
                type="button"
                className={profile.mode === mode.value ? "active" : ""}
                onClick={() => onModeChange(mode.value)}
              >
                <span className="settings-mode-icon">
                  {profile.mode === mode.value ? <CheckCircle2 size={18} /> : <UserRound size={18} />}
                </span>
                <strong>{mode.label}</strong>
                <small>{mode.value === "interviewer" ? "Agent 提问，你来回答" : "你提问，Agent 作为候选人回答"}</small>
              </button>
            ))}
          </div>
          {settingsState?.status === "saving" && <p className="resume-hint active">正在保存设置...</p>}
          {settingsState?.status === "saved" && <p className="resume-hint success">设置已保存。</p>}
          {settingsState?.status === "error" && <p className="resume-hint error">{settingsState.error}</p>}
        </section>
      </div>
    </section>
  );
}
