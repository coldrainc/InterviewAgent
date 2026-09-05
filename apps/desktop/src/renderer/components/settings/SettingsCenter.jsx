import { useEffect, useState } from "react";
import { BellRing, CheckCircle2, Clock, Loader2, Settings, UserRound } from "lucide-react";
import { interviewModes } from "../../constants/interview";
import { getInterviewAgentClient } from "../../apiClient";

const api = getInterviewAgentClient();

function NotifySettingsBlock() {
  const bridge = typeof window !== "undefined" ? window.interviewAgent : null;
  const supported = Boolean(bridge?.notifySchedule && bridge?.notifyTest && bridge?.notifyCancel);
  const [enabled, setEnabled] = useState(false);
  const [time, setTime] = useState("20:00");
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState("");
  const [hasPlan, setHasPlan] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const plans = await api.reviewSite.listPlans();
        setHasPlan(Array.isArray(plans) && plans.length > 0);
      } catch {
        // 未登录时不阻断提醒开关，仅不做计划判断
        setHasPlan(true);
      }
    })();
  }, []);

  if (!supported) {
    return (
      <section className="settings-block">
        <div className="panel-heading"><span>每日学习提醒</span></div>
        <p className="resume-hint">当前环境不支持系统通知（需桌面端运行）。</p>
      </section>
    );
  }

  async function schedule(nextEnabled) {
    setBusy(true);
    setHint("");
    try {
      if (nextEnabled) {
        await bridge.notifySchedule({
          enabled: true,
          time,
          title: "面试复习提醒",
          body: "今天的复习任务还没完成，打卡 streak 别断啦，打开 App 继续吧。"
        });
        setEnabled(true);
        setHint(`已开启，每天 ${time} 提醒你学习。`);
      } else {
        await bridge.notifyCancel();
        setEnabled(false);
        setHint("已关闭每日提醒。");
      }
    } catch (err) {
      setHint(`设置失败：${err?.message || "请稍后重试"}`);
    } finally {
      setBusy(false);
    }
  }

  async function testNow() {
    setBusy(true);
    setHint("");
    try {
      await bridge.notifyTest();
      setHint("测试通知已发送，若系统已授权应能看到通知弹窗。");
    } catch (err) {
      setHint(`测试失败：${err?.message || "请检查系统通知权限"}`);
    } finally {
      setBusy(false);
    }
  }

  const blocked = !hasPlan;

  return (
    <section className="settings-block">
      <div className="panel-heading"><span>每日学习提醒</span></div>
      <div className="notify-row">
        <div className="notify-icon">
          <BellRing size={18} />
        </div>
        <div className="notify-body">
          <strong>到点提醒打卡</strong>
          <small>
            {blocked
              ? "生成一份复习计划后才能开启提醒（提醒内容与今日任务挂钩）。"
              : enabled
                ? `每天 ${time} 本地通知提醒，点击通知直接回到今日页。`
                : "关闭 App 也能收到本地系统通知，点击唤出应用。"}
          </small>
          <div className="notify-controls">
            <label className="notify-time">
              <Clock size={13} />
              <input
                type="time"
                className="v3-input"
                value={time}
                disabled={!enabled || blocked}
                onChange={(e) => setTime(e.target.value)}
              />
            </label>
            <button
              type="button"
              className="btn-ghost-v3 small"
              disabled={busy || blocked}
              onClick={testNow}
            >
              <BellRing size={13} /> 发送测试
            </button>
            <button
              type="button"
              className={enabled ? "btn-ghost-v3 small checked" : "btn-primary-v3 small"}
              disabled={busy || blocked}
              onClick={() => schedule(!enabled)}
            >
              {busy ? <Loader2 size={13} className="spin" /> : enabled ? <CheckCircle2 size={13} /> : <BellRing size={13} />}
              {enabled ? "已开启 · 点击关闭" : "开启提醒"}
            </button>
          </div>
          {hint && <p className="resume-hint active">{hint}</p>}
        </div>
      </div>
    </section>
  );
}

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

        <NotifySettingsBlock />
      </div>
    </section>
  );
}
