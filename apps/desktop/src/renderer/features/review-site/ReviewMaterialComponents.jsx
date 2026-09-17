import { useEffect, useMemo, useRef, useState } from "react";
import {
  Check, Clock, FileText, Loader2, NotebookPen, Pause, Play, Plus, RefreshCw,
  X
} from "lucide-react";
import { getInterviewAgentClient } from "../../apiClient";

const api = getInterviewAgentClient();

export function V3StarCard({ card }) {
  const [flipped, setFlipped] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [dragX, setDragX] = useState(0);
  const drawerRef = useRef(null);
  const startX = useRef(0);
  const title = card.title || card.project_title || "未命名项目";
  const tags = Array.isArray(card.tags) ? card.tags : (card.tag ? String(card.tag).split(/[,，、]/).filter(Boolean) : []);
  const s = card.situation || card.background || card.s || "无";
  const t = card.task || card.challenge || card.t || "无";
  const a = card.action || card.solution || card.a || "无";
  const r = card.result || card.r || "无";
  const rPct = Math.min(100, Number(card.result_pct || card.result_score || 82));

  function onHandlePointerDown(e) {
    startX.current = e.clientX;
    const onMove = (ev) => {
      const dx = ev.clientX - startX.current;
      if (dx > 0) setDragX(dx);
    };
    const onUp = (ev) => {
      const dx = ev.clientX - startX.current;
      const w = drawerRef.current?.clientWidth || 440;
      if (dx >= w * 0.35) setDrawerOpen(false);
      setDragX(0);
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
    };
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
  }

  useEffect(() => {
    const h = () => setDrawerOpen(false);
    window.addEventListener("v3-close-all-drawers", h);
    return () => window.removeEventListener("v3-close-all-drawers", h);
  }, []);

  return (
    <>
      <div className="v3-star-card" onClick={() => setDrawerOpen(true)}>
        <button
          className="v3-btn ghost icon-only v3-star-flip-btn"
          onClick={(e) => { e.stopPropagation(); setFlipped((v) => !v); }}
          title="翻面"
        >
          <RefreshCw size={14} />
        </button>
        {!flipped ? (
          <>
            <div className="v3-star-tags">
              {tags.slice(0, 3).map((tg, i) => <span key={i} className="v3-chip">{tg}</span>)}
            </div>
            <div className="v3-star-title">{title}</div>
            <div className="v3-star-section">
              <span>S · 背景</span>
              <strong>{s}</strong>
            </div>
            <div className="v3-star-section">
              <span>T · 挑战</span>
              <strong>{t}</strong>
            </div>
          </>
        ) : (
          <>
            <div className="v3-star-tags">
              {tags.slice(0, 3).map((tg, i) => <span key={i} className="v3-chip">{tg}</span>)}
            </div>
            <div className="v3-star-title">{title}</div>
            <div className="v3-star-detail-block">
              <span>Action / 行动</span>
              <p>{a}</p>
            </div>
            <div className="v3-star-detail-block">
              <span>Result / 结果</span>
              <p>{r}</p>
            </div>
            <div className="v3-result-bar">
              <div className="fill" style={{ width: `${rPct}%` }} />
            </div>
          </>
        )}
      </div>
      {drawerOpen && (
        <div
          className="v3-drawer open"
          onClick={(e) => { if (e.target === e.currentTarget) setDrawerOpen(false); }}
        >
          <div
            ref={drawerRef}
            className="v3-drawer-inner"
            style={{ transform: dragX > 0 ? `translateX(${dragX}px)` : undefined }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="v3-drawer-handle"
              onPointerDown={onHandlePointerDown}
            />
            <div className="v3-drawer-head">
              <h4>{title}</h4>
              <button className="v3-btn ghost icon-only" onClick={() => setDrawerOpen(false)} aria-label="关闭">
                <X size={16} />
              </button>
            </div>
            <div className="v3-drawer-section">
              <h4>S · 背景</h4>
              <p>{s}</p>
            </div>
            <div className="v3-drawer-section">
              <h4>T · 挑战</h4>
              <p>{t}</p>
            </div>
            <div className="v3-drawer-section">
              <h4>A · 行动</h4>
              <p>{a}</p>
            </div>
            <div className="v3-drawer-section">
              <h4>R · 结果</h4>
              <p>{r}</p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export function A4FaceCard({ items, side, title }) {
  return (
    <div className="v3-a4-card">
      <h5><FileText size={16} /> A4 速记 · {title || side}</h5>
      {(items || []).map((item, i) => {
        const text = item.content || item.text || item.point || item.title || "要点";
        return (
          <div key={item.id || item.key || i} className="point">
            <div className="num">{i + 1}</div>
            <p>{text}</p>
          </div>
        );
      })}
      {(!items || !items.length) && (
        <p style={{ color: "var(--v3-text-3)", marginTop: 20, fontSize: 13 }}>
          暂无要点。点击右上角「导入」按钮导入默认 A4 速记，或在计划生成器中开启 A4 选项。
        </p>
      )}
    </div>
  );
}

const MATERIAL_META = {
  intro_scripts: { title: "自我介绍话术", add: "新增话术" },
  star_cards: { title: "STAR 项目卡", add: "新增项目卡" },
  a4_memory: { title: "A4 速记要点", add: "新增速记" }
};

function materialEmptyForm(kind) {
  if (kind === "intro_scripts") return { label: "", duration_seconds: 90, scenario: "", text: "" };
  if (kind === "star_cards") return { title: "", tag: "", background: "", challenge: "", solution: "", result: "" };
  return { side: "ALL", content: "" };
}

function materialItemToForm(kind, item) {
  if (kind === "intro_scripts") {
    return {
      label: item.label || item.title || "",
      duration_seconds: Number(item.duration_seconds || item.duration || 90),
      scenario: item.scenario || "",
      text: item.text || item.content || ""
    };
  }
  if (kind === "star_cards") {
    const tags = Array.isArray(item.tags) ? item.tags.join(", ") : (item.tag || "");
    return {
      title: item.title || item.project_title || "",
      tag: tags,
      background: item.background || item.situation || item.s || "",
      challenge: item.challenge || item.task || item.t || "",
      solution: item.solution || item.action || item.a || "",
      result: item.result || item.r || ""
    };
  }
  return { side: item.side || "ALL", content: item.content || item.text || "" };
}

function materialItemTitle(kind, item) {
  if (kind === "intro_scripts") return item.label || item.title || item.script_key || "未命名话术";
  if (kind === "star_cards") return item.title || item.project_title || item.card_key || "未命名项目卡";
  return (item.content || "").slice(0, 24) || "未命名速记";
}

export function MaterialManager({ kind, planId, items, onSaved, addToast }) {
  const meta = MATERIAL_META[kind];
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(() => materialEmptyForm(kind));

  function openNew() {
    setEditingId(null);
    setForm(materialEmptyForm(kind));
    setOpen(true);
  }

  function openEdit(item) {
    setEditingId(item.id);
    setForm(materialItemToForm(kind, item));
    setOpen(true);
  }

  function setField(key, value) {
    setForm((cur) => ({ ...cur, [key]: value }));
  }

  async function save() {
    if (!planId) {
      addToast("请先生成或导入一份计划", "warn");
      return;
    }
    setBusy(true);
    try {
      const payload = { ...form };
      if (kind === "intro_scripts") payload.duration_seconds = Number(payload.duration_seconds) || 90;
      if (editingId) {
        await api.reviewSite.updateMaterial(kind, editingId, payload);
      } else {
        await api.reviewSite.upsertMaterial(planId, kind, payload);
      }
      addToast(editingId ? "已保存修改" : "已新增", "success");
      setOpen(false);
      await onSaved?.();
    } catch (err) {
      addToast(`保存失败：${err?.message || "请稍后重试"}`, "error");
    } finally {
      setBusy(false);
    }
  }

  async function remove(item) {
    if (!window.confirm(`确定删除「${materialItemTitle(kind, item)}」？`)) return;
    setBusy(true);
    try {
      await api.reviewSite.deleteMaterial(kind, item.id);
      addToast("已删除", "success");
      if (editingId === item.id) setEditingId(null);
      await onSaved?.();
    } catch (err) {
      addToast(`删除失败：${err?.message || "请稍后重试"}`, "error");
    } finally {
      setBusy(false);
    }
  }

  const fields = kind === "intro_scripts" ? (
    <>
      <div className="v3-field"><label>版本名称</label>
        <input className="v3-input" value={form.label} onChange={(e) => setField("label", e.target.value)} placeholder="如 90 秒标准版" />
      </div>
      <div className="v3-field"><label>时长（秒）</label>
        <input className="v3-input" type="number" min={20} max={600} value={form.duration_seconds} onChange={(e) => setField("duration_seconds", e.target.value)} />
      </div>
      <div className="v3-field"><label>使用场景（可选）</label>
        <input className="v3-input" value={form.scenario} onChange={(e) => setField("scenario", e.target.value)} placeholder="如 一面开场 / HR 面" />
      </div>
      <div className="v3-field"><label>逐字稿（**关键词** 可高亮）</label>
        <textarea className="v3-input" rows={7} value={form.text} onChange={(e) => setField("text", e.target.value)} />
      </div>
    </>
  ) : kind === "star_cards" ? (
    <>
      <div className="v3-field"><label>项目标题</label>
        <input className="v3-input" value={form.title} onChange={(e) => setField("title", e.target.value)} placeholder="如 企业级 RAG 问答平台" />
      </div>
      <div className="v3-field"><label>标签（逗号分隔）</label>
        <input className="v3-input" value={form.tag} onChange={(e) => setField("tag", e.target.value)} placeholder="如 RAG, Go, 多租户" />
      </div>
      <div className="v3-field"><label>S · 背景 / 情境</label>
        <textarea className="v3-input" rows={3} value={form.background} onChange={(e) => setField("background", e.target.value)} />
      </div>
      <div className="v3-field"><label>T · 任务 / 挑战</label>
        <textarea className="v3-input" rows={3} value={form.challenge} onChange={(e) => setField("challenge", e.target.value)} />
      </div>
      <div className="v3-field"><label>A · 行动</label>
        <textarea className="v3-input" rows={4} value={form.solution} onChange={(e) => setField("solution", e.target.value)} />
      </div>
      <div className="v3-field"><label>R · 结果（含量化指标）</label>
        <textarea className="v3-input" rows={3} value={form.result} onChange={(e) => setField("result", e.target.value)} />
      </div>
    </>
  ) : (
    <>
      <div className="v3-field"><label>归属面</label>
        <select className="v3-input" value={form.side} onChange={(e) => setField("side", e.target.value)}>
          <option value="ALL">通用（A/B 自动分配）</option>
          <option value="A">A 面 · 知识主干</option>
          <option value="B">B 面 · 实战要点</option>
        </select>
      </div>
      <div className="v3-field"><label>速记要点（**关键词** 可高亮）</label>
        <textarea className="v3-input" rows={6} value={form.content} onChange={(e) => setField("content", e.target.value)} placeholder="一条速记一个知识点，打印后一页纸复习" />
      </div>
    </>
  );

  return (
    <>
      <div className="v3-material-bar">
        <button className="v3-btn primary small" onClick={openNew} disabled={!planId}>
          <Plus size={13} /> {meta.add}
        </button>
        <button className="v3-btn ghost small" onClick={() => setOpen(true)}>
          <NotebookPen size={13} /> 管理已有（{items?.length || 0}）
        </button>
      </div>
      {open && (
        <div className="modal-mask" onClick={(e) => { if (e.target === e.currentTarget) setOpen(false); }}>
          <div className="modal-card v3-material-modal">
            <div className="modal-head">
              <h3>{meta.title}</h3>
              <button className="icon-button" onClick={() => setOpen(false)} aria-label="关闭"><X size={16} /></button>
            </div>
            <div className="v3-material-list">
              {(items || []).length === 0 && <p style={{ color: "var(--v3-text-3)", fontSize: 13, margin: "4px 0 10px" }}>还没有内容，新增一条吧。</p>}
              {(items || []).map((item) => (
                <div key={item.id} className={`v3-material-row ${editingId === item.id ? "editing" : ""}`}>
                  <span>{materialItemTitle(kind, item)}</span>
                  <div>
                    <button className="v3-btn ghost icon-only" title="编辑" onClick={() => openEdit(item)}><NotebookPen size={13} /></button>
                    <button className="v3-btn ghost icon-only" title="删除" disabled={busy} onClick={() => remove(item)}><X size={13} /></button>
                  </div>
                </div>
              ))}
            </div>
            <div className="v3-material-form">
              <strong>{editingId ? "编辑" : "新增"}</strong>
              {fields}
              <div className="v3-material-form-actions">
                <button className="v3-btn ghost small" onClick={() => { setEditingId(null); setForm(materialEmptyForm(kind)); }}>
                  清空
                </button>
                <button className="v3-btn primary small" disabled={busy} onClick={save}>
                  {busy ? <Loader2 size={13} className="v3-spin" /> : <Check size={13} />} 保存
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export function IntroPlayer({ scripts, addToast }) {
  const [tab, setTab] = useState(0);
  const list = scripts?.length ? scripts : [
    { key: "30s", title: "30 秒电梯", duration: 30, text: "面试官您好，我是**候选人**，\n在过去 6 年专注 **AI Native 全栈**工程，\n主导过 **RAG / Agent / 多模态** 产品落地。" },
    { key: "90s", title: "90 秒标准版", duration: 90, text: "您好，我是**候选人**。\n我是 **6 年 AI Native 全栈工程师**，\n熟悉 **前后端 + 大模型 + 数据 + 评测**。\n核心亮点：\n1) 设计并落地 **企业级 RAG 平台**，支撑 10+ 业务线；\n2) 主导 **多 Agent 协作框架**，任务成功率提升至 92%；\n3) 深耕 **质量评测与护栏**，线上事故率下降 65%。" },
    { key: "role", title: "岗位定制", duration: 120, text: "您好，我对 **AI Native 全栈** 岗位理解如下：\n- **产品思维**：从业务价值倒推技术方案；\n- **工程能力**：端到端交付，关注 **性能 / 成本 / 上线**；\n- **AI 深度**：RAG、Agent、Harness、**评测闭环**；\n- **跨端广度**：Web / 小程序 / 桌面端 / 服务端统一架构。\n\n我非常期待把我的经验带到贵团队，谢谢。" }
  ];
  const current = list[Math.min(tab, list.length - 1)];
  const currentKey = current?.id || current?.script_key || current?.key || "default";
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timerRef = useRef(null);
  const duration = Number(current?.duration_seconds || current?.duration || 90);
  const remaining = Math.max(0, duration - elapsed);
  const min = String(Math.floor(remaining / 60)).padStart(1, "0");
  const sec = String(remaining % 60).padStart(2, "0");
  const warning = remaining <= 30 && remaining > 0;

  const stats = useMemo(() => {
    try {
      const key = `v3:intro:${currentKey}`;
      const raw = JSON.parse(localStorage.getItem(key) || '{"count":0,"sumS":0,"timeout":0}');
      return { count: raw.count, avgS: raw.count ? Math.round(raw.sumS / raw.count) : 0, timeout: raw.timeout };
    } catch { return { count:0, avgS:0, timeout:0 }; }
  }, [tab, currentKey]);

  useEffect(() => {
    window.clearInterval(timerRef.current);
    setElapsed(0);
    setPlaying(false);
  }, [tab]);

  useEffect(() => {
    if (!playing) return;
    timerRef.current = window.setInterval(() => {
      setElapsed((cur) => {
        const next = cur + 1;
        if (next >= duration) {
          setPlaying(false);
          return duration;
        }
        return next;
      });
    }, 1000);
    return () => window.clearInterval(timerRef.current);
  }, [playing, duration]);

  const recordedRef = useRef(false);
  useEffect(() => {
    if (playing) {
      recordedRef.current = false;
      return;
    }
    if (recordedRef.current || elapsed < 10 || !duration) return;
    recordedRef.current = true;
    try {
      const key = `v3:intro:${currentKey}`;
      const raw = JSON.parse(localStorage.getItem(key) || '{"count":0,"sumS":0,"timeout":0}');
      raw.count += 1;
      raw.sumS += elapsed;
      if (elapsed >= duration) raw.timeout += 1;
      localStorage.setItem(key, JSON.stringify(raw));
    } catch {}
  }, [playing, elapsed, duration, currentKey]);

  function renderHighlighted(text) {
    const parts = String(text || "").split(/(\*\*[^*]+\*\*)/g);
    return parts.map((p, i) => p.startsWith("**") && p.endsWith("**")
      ? <b key={i}>{p.slice(2, -2)}</b>
      : <span key={i}>{p}</span>
    );
  }

  return (
    <div className="v3-intro">
      <div className="intro-chips">
        {list.map((s, i) => (
          <button key={s.id || s.script_key || s.key || i} className={`v3-chip toggle ${tab === i ? "on" : ""}`} onClick={() => setTab(i)}>
            <Clock size={12} /> {s.label || s.title || `${s.duration_seconds || s.duration || 30}s 版本`}
          </button>
        ))}
      </div>
      <div className="intro-player">
        <div className="script-box">
          <div className="panel-title">
            <h4><FileText size={15} /> 逐字稿 · {current?.label || current?.title || "标准版本"}</h4>
            <span className="hint">预计 {duration}s{stats.count > 0 ? ` · 已练习 ${stats.count} 次` : " · 尚未练习"}</span>
          </div>
          <div className="content">{renderHighlighted(current?.text || current?.content || "")}</div>
        </div>
        <div className="timer-panel">
          <div className={`timer-display ${playing ? "playing" : ""} ${warning ? "warning" : ""}`}>
            <div className="time">{min}:{sec}</div>
            <div>
              {playing ? "正在练习中..." : warning ? "倒计时 30 秒内" : "准备就绪"}
            </div>
          </div>
          <div className="timer-actions">
            {!playing ? (
              <button className="play" onClick={() => setPlaying(true)}>
                <Play size={14} /> 开始
              </button>
            ) : (
              <button className="pause" onClick={() => setPlaying(false)}>
                <Pause size={14} /> 暂停
              </button>
            )}
            <button className="reset" onClick={() => { setPlaying(false); setElapsed(0); }}>
              <RefreshCw size={13} /> 重置
            </button>
          </div>
          <div className="intro-tips">
            <strong>练习要点</strong>
            90s 版本按「背景 → 亮点 1/2/3 → 期待」结构。
            关键词保持 <b style={{ color: "var(--v3-primary)" }}>高亮</b>，注意时间把控。
          </div>
          <div className="v3-intro-stats">
            <div><small>练习次数</small><b>{stats.count}</b></div>
            <div><small>平均用时</small><b>{stats.avgS || 0}s</b></div>
            <div><small>练满次数</small><b>{stats.timeout}</b></div>
          </div>
        </div>
      </div>
    </div>
  );
}
