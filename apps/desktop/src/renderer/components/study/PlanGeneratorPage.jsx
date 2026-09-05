import { useEffect, useMemo, useState } from "react";
import {
  BrainCircuit, Building2, Check, ChevronLeft, Clock, Compass, FileText, Gauge,
  Loader2, Mic, Sparkles, Star as StarIcon, Target, Wand2, Zap
} from "lucide-react";
import { getInterviewAgentClient } from "../../apiClient";

const api = getInterviewAgentClient();

const SENIORITY_OPTIONS = [
  { value: "junior", label: "1-3 年 / 初级", multiplier: 0.8 },
  { value: "mid", label: "3-5 年 / 中级", multiplier: 1 },
  { value: "senior", label: "6 年经验 / 高级", multiplier: 1.15 },
  { value: "staff", label: "8+ 年 / 专家", multiplier: 1.3 }
];

const FOCUS_AREA_OPTIONS = [
  { value: "基础", label: "基础夯实", desc: "语言 / 框架 / 计算机基础", icon: <Compass size={13} /> },
  { value: "跨端", label: "跨端工程", desc: "Web / 桌面 / 小程序统一架构", icon: <Building2 size={13} /> },
  { value: "AI", label: "AI / 大模型", desc: "RAG / Agent / 评测 / 护栏", icon: <Sparkles size={13} /> },
  { value: "算法", label: "算法与数据", desc: "常见题型 · 复杂度 · 模板", icon: <Target size={13} /> },
  { value: "项目深挖", label: "项目深挖", desc: "技术选型 · 难点 · 指标", icon: <Gauge size={13} /> },
  { value: "公司定制", label: "公司定制", desc: "目标公司 JD / 文化 / 轮次", icon: <Building2 size={13} /> },
  { value: "模拟", label: "高压模拟", desc: "3 轮全真模拟 + 复盘", icon: <Zap size={13} /> }
];

const TEMPLATE_OPTIONS = [
  { value: "14d-four-phase", label: "14 天四阶段（基础 → 深挖 → 项目 → 模拟）", recommended: true, days: 14 },
  { value: "7d-sprint", label: "7 天冲刺版（快速查漏补缺）", days: 7 },
  { value: "30d-comprehensive", label: "30 天全面进阶版", days: 30 },
  { value: "custom", label: "完全自定义（按 Slider 节奏）", days: -1 }
];

const PHASE_DEFS = [
  { key: "foundation", title: "基础夯实", color: "#2f63e8" },
  { key: "deepening", title: "专题深挖", color: "#0f8f8f" },
  { key: "project", title: "项目打磨", color: "#16a673" },
  { key: "simulation", title: "模拟冲刺", color: "#c77918" }
];

export function PlanGeneratorPage({ onBack, onGenerated, planId, existingPlan }) {
  const [targetRole, setTargetRole] = useState(existingPlan?.target_role || "AI Native 全栈");
  const [seniority, setSeniority] = useState(existingPlan?.seniority || "senior");
  const [targetCompany, setTargetCompany] = useState(existingPlan?.target_company || "");
  const [totalDays, setTotalDays] = useState(Number(existingPlan?.total_days || 14));
  const [hoursPerDay, setHoursPerDay] = useState(Number(existingPlan?.hours_per_day || 4));
  const [focusAreas, setFocusAreas] = useState(
    Array.isArray(existingPlan?.focus_areas) && existingPlan.focus_areas.length
      ? existingPlan.focus_areas
      : ["基础", "AI", "项目深挖", "模拟"]
  );
  const [template, setTemplate] = useState(existingPlan?.template || "14d-four-phase");
  const [includeA4, setIncludeA4] = useState(true);
  const [includeIntro, setIncludeIntro] = useState(true);
  const [includeStar, setIncludeStar] = useState(true);
  const [useHistory, setUseHistory] = useState(true);
  const [resumeId, setResumeId] = useState("");
  const [resumes, setResumes] = useState([]);
  const [generating, setGenerating] = useState(false);
  const [resultInfo, setResultInfo] = useState(null);
  const [toast, setToast] = useState(null);

  const isEdit = Boolean(planId);

  useEffect(() => {
    (async () => {
      try {
        const list = await api.listResumes?.();
        if (Array.isArray(list)) setResumes(list);
      } catch {
        // 未登录或无简历时静默
      }
    })();
  }, []);

  useEffect(() => {
    const tpl = TEMPLATE_OPTIONS.find((t) => t.value === template);
    if (tpl && tpl.days > 0) {
      setTotalDays(tpl.days);
    }
  }, [template]);

  const preview = useMemo(() => {
    const total = Math.max(3, Math.min(60, totalDays));
    const weights = [0.32, 0.3, 0.2, 0.18];
    const phases = PHASE_DEFS.map((p, i) => {
      const days = Math.max(1, Math.round(total * weights[i]));
      const tasks = Math.round(days * (seniorityMult(seniority) * 1.4) * (focusAreas.includes("基础") && i === 0 ? 1.3 : 1));
      const hours = Math.round(days * hoursPerDay * 0.9);
      let offset = 0;
      for (let j = 0; j < i; j++) {
        offset += Math.max(1, Math.round(total * weights[j]));
      }
      return {
        ...p,
        days,
        tasks,
        hours,
        startPct: Math.round((offset / total) * 100),
        widthPct: Math.max(6, Math.round((days / total) * 100) - 1)
      };
    });
    const sumHours = phases.reduce((s, p) => s + p.hours, 0);
    const sumTasks = phases.reduce((s, p) => s + p.tasks, 0);
    return { phases, total, sumHours, sumTasks };
  }, [totalDays, hoursPerDay, seniority, focusAreas]);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), toast.timeoutMs || 2400);
    return () => window.clearTimeout(id);
  }, [toast]);

  function seniorityMult(s) {
    return SENIORITY_OPTIONS.find((o) => o.value === s)?.multiplier || 1;
  }

  function toggleFocus(value) {
    setFocusAreas((cur) => cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value]);
  }

  async function handleGenerate() {
    if (generating) return;
    setGenerating(true);
    setToast({ msg: isEdit ? "正在保存计划..." : "正在为你生成专属复习计划...", variant: "info", timeoutMs: 4000 });
    const payload = {
      target_role: targetRole || "AI Native 全栈",
      seniority,
      target_company: targetCompany || undefined,
      total_days: preview.total,
      hours_per_day: hoursPerDay,
      focus_areas: focusAreas.length ? focusAreas : undefined,
      template,
      use_history: useHistory,
      resume_id: resumeId || undefined
    };
    let result = {};
    if (isEdit) {
      result = await api.reviewSite.patchPlan(planId, { ...payload, includeA4, includeIntro, includeStar });
    } else {
      result = await api.reviewSite.generatePlan(payload);
    }
    const newPlanId = result?.plan_id || result?.id;
    const ok = result && (newPlanId || (typeof result === "object" && Object.keys(result).length > 0));
    setGenerating(false);
    if (ok) {
      setResultInfo({
        generatedBy: result?.generated_by || "rule",
        planId: newPlanId,
        phases: result?.breakdown_phases || null,
        hours: result?.estimated_daily_hours || hoursPerDay
      });
      setToast({ msg: isEdit ? "计划已保存，返回复习站查看" : "计划已生成，快去执行吧", variant: "success", timeoutMs: 3200 });
      window.setTimeout(() => onGenerated?.(newPlanId || planId, result), 1200);
    } else {
      setToast({ msg: "服务端暂未返回结果，已使用预览数据创建示例计划（本地演示，刷新会丢失）", variant: "warn", timeoutMs: 3600 });
      window.setTimeout(() => onGenerated?.(undefined), 1200);
    }
  }

  return (
    <section className="planner-page v3">
      {toast && (
        <div className="v3-toast-layer">
          <div className={`v3-toast ${toast.variant || "info"}`}>
            <span className="v3-toast-icon">
              {toast.variant === "success" ? <Check size={16} /> : <Wand2 size={16} />}
            </span>
            <span>{toast.msg}</span>
          </div>
        </div>
      )}

      <div className="v3-header" style={{ marginBottom: 20 }}>
        <div className="v3-header-left">
          {onBack && (
            <button className="v3-btn ghost icon-only" onClick={onBack}>
              <ChevronLeft size={16} />
            </button>
          )}
          <h2>{isEdit ? "编辑复习计划" : "生成专属复习计划"}</h2>
        </div>
        <div className="v3-header-right">
          <button className="v3-btn primary" disabled={generating} onClick={handleGenerate}>
            {generating ? <Loader2 size={14} className="v3-spin" /> : <Wand2 size={14} />}
            {isEdit ? "保存计划" : "生成计划"}
          </button>
        </div>
      </div>

      <div className="v3-wizard">
        {/* 左 60% 表单 */}
        <div className="v3-wizard-left">
          {/* Block 1: 目标岗位 */}
          <div className="v3-step-card">
            <div className="v3-step-num">1</div>
            <h4>目标岗位</h4>
            <div className="v3-field">
              <label>目标岗位</label>
              <input className="v3-input" value={targetRole} onChange={(e) => setTargetRole(e.target.value)} placeholder="如 AI Native 全栈" />
            </div>
            <div className="v3-field">
              <label>经验 / 职级</label>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
                {SENIORITY_OPTIONS.map((o) => (
                  <button
                    key={o.value}
                    className={`v3-radio-card ${seniority === o.value ? "checked" : ""}`}
                    onClick={() => setSeniority(o.value)}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="v3-field">
              <label>目标公司（可选）</label>
              <input className="v3-input" value={targetCompany} onChange={(e) => setTargetCompany(e.target.value)} placeholder="如 字节 / 腾讯" />
            </div>
          </div>

          {/* Block 2: 复习节奏 */}
          <div className="v3-step-card">
            <div className="v3-step-num">2</div>
            <h4>复习节奏</h4>
            {/* 总天数 Slider + Quick Chips */}
            <div className="v3-slider-wrap">
              <div className="slider-value"><span>总天数</span><b>{preview.total} 天</b></div>
              <input
                type="range"
                className="v3-slider"
                min={3}
                max={60}
                value={preview.total}
                onChange={(e) => { setTemplate("custom"); setTotalDays(Number(e.target.value)); }}
              />
              <div style={{ display: "flex", gap: 6 }}>
                {[3, 7, 14, 30].map((d) => (
                  <button
                    key={d}
                    className={`v3-chip toggle ${preview.total === d ? "on" : ""}`}
                    onClick={() => { setTemplate("custom"); setTotalDays(d); }}
                  >
                    {d} 天
                  </button>
                ))}
              </div>
            </div>
            {/* 每日小时 Slider + Quick Chips */}
            <div className="v3-slider-wrap">
              <div className="slider-value"><span>每日投入</span><b>{hoursPerDay} 小时 / 天</b></div>
              <input
                type="range"
                className="v3-slider"
                min={1}
                max={12}
                value={hoursPerDay}
                onChange={(e) => setHoursPerDay(Number(e.target.value))}
              />
              <div style={{ display: "flex", gap: 6 }}>
                {[2, 4, 6, 8].map((h) => (
                  <button
                    key={h}
                    className={`v3-chip toggle ${hoursPerDay === h ? "on" : ""}`}
                    onClick={() => setHoursPerDay(h)}
                  >
                    {h}h
                  </button>
                ))}
              </div>
            </div>
            {/* 重点领域 Toggle Chips */}
            <div className="v3-field">
              <label>重点领域（至少选 1 个）</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {FOCUS_AREA_OPTIONS.map((f) => {
                  const on = focusAreas.includes(f.value);
                  return (
                    <button
                      key={f.value}
                      className={`v3-chip toggle ${on ? "on" : ""}`}
                      onClick={() => toggleFocus(f.value)}
                    >
                      {f.icon} {f.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Block 3: 模板选择 */}
          <div className="v3-step-card">
            <div className="v3-step-num">3</div>
            <h4>模板选择</h4>
            <div style={{ display: "grid", gap: 8 }}>
              {TEMPLATE_OPTIONS.map((t) => (
                <label
                  key={t.value}
                  className={`v3-radio-card ${template === t.value ? "checked" : ""}`}
                  onClick={() => setTemplate(t.value)}
                  style={{ cursor: "pointer" }}
                >
                  <input
                    type="radio"
                    checked={template === t.value}
                    onChange={() => setTemplate(t.value)}
                    style={{ display: "none" }}
                  />
                  <span style={{ fontWeight: 600, fontSize: 14 }}>{t.label}</span>
                  <div style={{ display: "flex", gap: 6 }}>
                    {t.recommended && (
                      <span className="v3-chip primary">
                        <Sparkles size={10} /> 推荐
                      </span>
                    )}
                    {t.days > 0 && (
                      <span className="v3-chip">
                        <Clock size={10} /> {t.days} 天
                      </span>
                    )}
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Block 4: 个性化依据 */}
          <div className="v3-step-card">
            <div className="v3-step-num">4</div>
            <h4>个性化依据</h4>
            <button
              className={`v3-radio-card ${useHistory ? "checked" : ""}`}
              onClick={() => setUseHistory((v) => !v)}
              style={{ flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 10 }}
            >
              <BrainCircuit size={16} />
              <div style={{ textAlign: "left" }}>
                <div style={{ fontWeight: 600 }}>结合历史表现生成</div>
                <span style={{ fontSize: 12, color: "var(--v3-text-3)" }}>
                  自动读取面试报告弱项与错题分布，为薄弱项多排任务、已掌握项少排
                </span>
              </div>
              <div
                style={{
                  marginLeft: "auto",
                  width: 20,
                  height: 20,
                  borderRadius: 6,
                  border: useHistory ? "none" : "1.5px solid var(--v3-border-str)",
                  background: useHistory ? "var(--v3-primary)" : "transparent",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center"
                }}
              >
                {useHistory && <Check size={12} color="#fff" />}
              </div>
            </button>
            <div className="v3-field">
              <label>关联简历（可选，出题与项目任务会参考）</label>
              <select className="v3-input" value={resumeId} onChange={(e) => setResumeId(e.target.value)}>
                <option value="">不关联简历</option>
                {resumes.map((r) => (
                  <option key={r.id} value={r.id}>{r.file_name || r.title || r.filename || `简历 ${String(r.id).slice(0, 8)}`}</option>
                ))}
              </select>
              {resumes.length === 0 && (
                <span style={{ fontSize: 12, color: "var(--v3-text-3)" }}>暂无已上传简历，可在面试设置中上传后再回来选择。</span>
              )}
            </div>
          </div>

          {/* Block 5: 高级选项 */}
          <div className="v3-step-card">
            <div className="v3-step-num">5</div>
            <h4>辅助素材</h4>
            <div style={{ display: "grid", gap: 10 }}>
              {[
                { k: "includeA4", v: includeA4, set: setIncludeA4, label: "生成 A4 速记卡片", desc: "知识要点 A/B 面", icon: <FileText size={14} /> },
                { k: "includeIntro", v: includeIntro, set: setIncludeIntro, label: "生成自我介绍脚本", desc: "30s / 90s / 定制", icon: <Mic size={14} /> },
                { k: "includeStar", v: includeStar, set: setIncludeStar, label: "生成 STAR 项目卡模板", desc: "扁平项目表达卡", icon: <StarIcon size={14} /> }
              ].map((it) => (
                <button
                  key={it.k}
                  className={`v3-radio-card ${it.v ? "checked" : ""}`}
                  onClick={() => it.set((v) => !v)}
                  style={{ flexDirection: "row", alignItems: "center", gap: 10 }}
                >
                  {it.icon}
                  <div style={{ textAlign: "left" }}>
                    <div style={{ fontWeight: 600 }}>{it.label}</div>
                    <span style={{ fontSize: 12, color: "var(--v3-text-3)" }}>{it.desc}</span>
                  </div>
                  <div
                    style={{
                      marginLeft: "auto",
                      width: 20,
                      height: 20,
                      borderRadius: 6,
                      border: it.v ? "none" : "1.5px solid var(--v3-border-str)",
                      background: it.v ? "var(--v3-primary)" : "transparent",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center"
                    }}
                  >
                    {it.v && <Check size={12} color="#fff" />}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 右 40% 预览 */}
        <div className="v3-wizard-right">
          <div className="v3-step-card">
            <h4><Gauge size={15} /> 实时预览</h4>
            <div className="v3-stat-grid">
              <div className="v3-stat">
                <div className="v3-stat-icon"><Clock size={16} /></div>
                <div>
                  <small className="v3-stat-label">总天数</small>
                  <strong className="v3-stat-value">{preview.total}</strong>
                </div>
              </div>
              <div className="v3-stat">
                <div className="v3-stat-icon"><Zap size={16} /></div>
                <div>
                  <small className="v3-stat-label">每日小时</small>
                  <strong className="v3-stat-value">{hoursPerDay}h</strong>
                </div>
              </div>
              <div className="v3-stat">
                <div className="v3-stat-icon"><Target size={16} /></div>
                <div>
                  <small className="v3-stat-label">任务估算</small>
                  <strong className="v3-stat-value">~{preview.sumTasks}</strong>
                </div>
              </div>
              <div className="v3-stat">
                <div className="v3-stat-icon"><Gauge size={16} /></div>
                <div>
                  <small className="v3-stat-label">总投入</small>
                  <strong className="v3-stat-value">~{preview.sumHours}h</strong>
                </div>
              </div>
            </div>

            {/* Gantt */}
            <div style={{ marginBottom: 12, fontSize: 12, color: "var(--v3-text-3)" }}>4 阶段 Gantt 预览</div>
            <div className="v3-gantt">
              {preview.phases.map((ph) => (
                <div key={ph.key} className="v3-gantt-seg" style={{ width: `${ph.widthPct}%` }}>
                  {ph.title} · {ph.days}天
                </div>
              ))}
            </div>

            {/* AI 摘要 */}
            <div className="v3-summary-card">
              <strong><Sparkles size={13} /> AI 将自动生成</strong>
              <p>· 按 <b>{targetRole || "目标岗位"}</b> 定制 {preview.total} 天 × {hoursPerDay}h 节奏</p>
              <p>· 重点领域：<b>{focusAreas.join("、") || "通用"}</b>，职级系数 ×{seniorityMult(seniority).toFixed(2)}</p>
              <p>· 辅助素材：{[includeIntro && "自我介绍稿", includeStar && "STAR 项目卡", includeA4 && "A4 速记"].filter(Boolean).join(" / ") || "（无）"}</p>
              {useHistory ? (
                <p className="v3-history-on"><BrainCircuit size={12} /> 已开启个性化：参考历史报告弱项与错题分布</p>
              ) : (
                <p style={{ color: "var(--v3-text-3)" }}>· 未结合历史数据，将生成通用计划</p>
              )}
            </div>

            {resultInfo && (
              <div className="v3-result-banner">
                <Check size={15} />
                <div>
                  <strong>计划已生成</strong>
                  <span>
                    {resultInfo.generatedBy === "llm" ? "AI 个性化编排" : "规则模板生成"} ·
                    建议每日 {resultInfo.hours}h{resultInfo.phases ? ` · ${resultInfo.phases.length} 个阶段` : ""}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="v3-action-bar">
        <button className="v3-btn ghost" onClick={onBack}>
          <ChevronLeft size={14} /> 返回复习站
        </button>
        <button
          className="v3-btn primary"
          disabled={generating}
          onClick={handleGenerate}
          style={{ minWidth: 200 }}
        >
          {generating ? <Loader2 size={14} className="v3-spin" /> : <Wand2 size={14} />}
          {isEdit ? "保存计划" : "生成我的复习计划"}
        </button>
      </div>
    </section>
  );
}
