import { useState } from "react";
import {
  Check, Loader2, RefreshCw, Search, Shuffle, Target, X
} from "lucide-react";

export function V3FilterToolbar({ filters, setFilters, onRefresh, onShuffle, onlyWrong, setOnlyWrong, onlyUnmastered, setOnlyUnmastered, loading, todayCount, todayCorrect }) {
  const pct = todayCount ? Math.min(100, (todayCount / 10) * 100) : 0;
  const correctPct = todayCount ? Math.round((todayCorrect / todayCount) * 100) : 0;
  return (
    <>
      <div className="v3-practice-progress">
        <span>
          今日已刷 {todayCount} 题 · 正确率 {correctPct}%
        </span>
        <div className="v3-practice-progress-bar">
          <div className="v3-practice-progress-fill" style={{ width: `${pct}%` }} />
        </div>
      </div>
      <div className="v3-filter-bar" style={{ padding: 0 }}>
        <div className="v3-filter-row">
          <div className="v3-field">
            <label>训练类型</label>
            <select className="v3-input" value={filters.category || ""} onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))}>
              <option value="">全部</option>
              <option value="ai_application">AI 应用</option>
              <option value="internet">互联网</option>
              <option value="leetcode">算法</option>
              <option value="behavioral">行为面试</option>
              <option value="system_design">系统设计</option>
            </select>
          </div>
          <div className="v3-field">
            <label>科目</label>
            <select className="v3-input" value={filters.subject || ""} onChange={(e) => setFilters((f) => ({ ...f, subject: e.target.value }))}>
              <option value="">全部</option>
              <option value="rag">RAG</option>
              <option value="agent_harness">Agent</option>
              <option value="algorithm">算法</option>
              <option value="project">项目深挖</option>
              <option value="frontend">前端</option>
              <option value="backend">后端</option>
            </select>
          </div>
          <div className="v3-field">
            <label>难度</label>
            <select className="v3-input" value={filters.difficulty || ""} onChange={(e) => setFilters((f) => ({ ...f, difficulty: e.target.value }))}>
              <option value="">全部</option>
              <option value="easy">简单</option>
              <option value="medium">中等</option>
              <option value="hard">困难</option>
            </select>
          </div>
          <div className="v3-field grow">
            <label>关键词</label>
            <div className="v3-search">
              <Search size={14} className="search-icon" />
              <input
                className="v3-input"
                placeholder="搜索题目..."
                value={filters.keyword || ""}
                onChange={(e) => setFilters((f) => ({ ...f, keyword: e.target.value }))}
              />
              {filters.keyword && (
                <button className="clear-btn" onClick={() => setFilters((f) => ({ ...f, keyword: "" }))}>
                  <X size={14} />
                </button>
              )}
            </div>
          </div>
        </div>
        <div className="v3-filter-chips">
          <button className={`v3-chip toggle ${onlyWrong ? "on" : ""}`} onClick={() => setOnlyWrong((v) => !v)}>
            <Target size={12} /> 只看错题
          </button>
          <button className={`v3-chip toggle ${onlyUnmastered ? "on" : ""}`} onClick={() => setOnlyUnmastered((v) => !v)}>
            <X size={12} /> 只看未掌握
          </button>
          <button className="v3-chip toggle" onClick={onShuffle} disabled={loading}>
            <Shuffle size={12} /> 随机 10 题
          </button>
          <div style={{ flex: 1 }} />
          <button className="v3-btn ghost small" onClick={onRefresh} disabled={loading}>
            {loading ? <Loader2 size={13} className="v3-spin" /> : <RefreshCw size={13} />} 刷新
          </button>
        </div>
      </div>
    </>
  );
}

export function V3QaCard({ q, onMark }) {
  const [open, setOpen] = useState(false);
  const meta = [q.category, q.subject, q.difficulty, q.question_type].filter(Boolean);
  return (
    <article className={`v3-qa-card ${open ? "open" : ""}`}>
      {meta.length > 0 && (
        <div className="v3-qa-meta">
          {meta.map((m, i) => <span key={i} className="v3-chip">{m}</span>)}
          {q.mastery_level != null && (
            <span className={`v3-chip toggle ${(q.mastery_level || 0) >= 4 ? "on" : ""}`}>掌握 {q.mastery_level}/5</span>
          )}
        </div>
      )}
      <div className="v3-qa-q" onClick={() => setOpen((v) => !v)}>
        {q.prompt || q.title || "未命名题目"}
      </div>
      {open && (
        <>
          <div className="v3-qa-body">
            {q.answer && <p>{q.answer}</p>}
            {q.answer_detail && <div>{q.answer_detail}</div>}
            {q.code && (
              <pre><code>{typeof q.code === "string" ? q.code : JSON.stringify(q.code, null, 2)}</code></pre>
            )}
          </div>
          <div className="v3-qa-actions">
            <button className="v3-btn ghost icon-only" title="已掌握" onClick={() => onMark(q, { mastery_level: 5, mark_type: "mastered" })}>
              <Check size={15} />
            </button>
            <button className="v3-btn ghost icon-only" title="加入错题" onClick={() => onMark(q, { mark_type: "wrong" })}>
              <Target size={15} />
            </button>
            <button className="v3-btn ghost icon-only" title="不太懂" onClick={() => onMark(q, { mastery_level: 1, mark_type: "confused", note: "不太懂" })}>
              <X size={15} />
            </button>
          </div>
        </>
      )}
    </article>
  );
}
