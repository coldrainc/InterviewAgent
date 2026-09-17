import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Loader2,
  PenLine,
  RefreshCw,
  Shuffle,
  Star,
  Target,
  TrendingUp,
  Undo2,
  XCircle,
  Brain,
  Crosshair
} from "lucide-react";
import { getInterviewAgentClient } from "../../apiClient";
import { SpecializedDrillPanel } from "../../features/training/SpecializedDrillPanel";
import { SpacedReviewPanel } from "../../features/training/SpacedReviewPanel";
import { InfiniteScrollSentinel } from "../common/InfiniteScrollSentinel";
import { mergeUniqueById } from "../../hooks/useInfiniteScroll";

const api = getInterviewAgentClient();

const CATEGORY_OPTIONS = [
  { value: "", label: "全部分类" },
  { value: "ai_application", label: "AI 应用工程" },
  { value: "internet", label: "互联网通用" },
  { value: "leetcode", label: "力扣算法" },
  { value: "civil_service", label: "公考面试" },
  { value: "behavioral", label: "行为面试" }
];

const DIFFICULTY_OPTIONS = [
  { value: "", label: "全部难度" },
  { value: "easy", label: "简单" },
  { value: "medium", label: "中等" },
  { value: "hard", label: "困难" }
];

const TYPE_OPTIONS = [
  { value: "", label: "全部题型" },
  { value: "choice", label: "选择题" },
  { value: "subjective", label: "主观题" },
  { value: "自我介绍", label: "自我介绍" }
];

function isChoice(question) {
  return Array.isArray(question?.choices) && question.choices.length > 0;
}

function choiceLabel(choice, index) {
  if (choice && typeof choice === "object") {
    return choice.label || choice.key || String.fromCharCode(65 + index);
  }
  const text = String(choice || "");
  const match = text.match(/^([A-D])[.、:：]/);
  return match ? match[1] : String.fromCharCode(65 + index);
}

function choiceText(choice) {
  if (choice && typeof choice === "object") return choice.text || choice.content || "";
  return String(choice || "");
}

export function TrainingPage({ account, navigationTarget, onRequireAuth }) {
  const [view, setView] = useState("practice"); // practice | drill | spaced | wrong
  const [filters, setFilters] = useState({ category: "", difficulty: "", question_type: "", keyword: "" });
  const [questions, setQuestions] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [offset, setOffset] = useState(0);
  const [wrongBook, setWrongBook] = useState([]);
  const [wrongBookState, setWrongBookState] = useState({ loading: false, hasMore: true, error: "" });
  const [stats, setStats] = useState(null);
  const [activeId, setActiveId] = useState("");
  const [answerDraft, setAnswerDraft] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const startedAtRef = useRef(0);
  const requestRef = useRef(0);
  const loadingRef = useRef(false);
  const wrongBookRef = useRef([]);
  const wrongBookLoadingRef = useRef(false);

  const pageSize = 20;

  useEffect(() => {
    if (!navigationTarget?.nonce) return;
    const category = String(navigationTarget.category || "");
    const questionId = String(navigationTarget.question_id || "");
    setView("practice");
    if (category) setFilters((current) => ({ ...current, category }));
    if (questionId) setActiveId(questionId);
  }, [navigationTarget?.nonce]);

  const loadQuestions = useCallback(async ({ reset = false, random = false } = {}) => {
    if (!account || (loadingRef.current && !reset)) return;
    const requestId = reset ? ++requestRef.current : requestRef.current;
    const nextOffset = reset ? 0 : questions.length;
    if (!reset && nextOffset >= total) return;
    loadingRef.current = true;
    setLoading(true);
    setLoadError("");
    try {
      const params = {
        category: filters.category || undefined,
        difficulty: filters.difficulty || undefined,
        question_type: filters.question_type || undefined,
        keyword: filters.keyword.trim() || undefined,
        limit: pageSize,
        offset: random ? Math.floor(Math.random() * Math.max(0, total - pageSize)) : nextOffset
      };
      const data = await api.reviewSite.listPracticeQuestions(params);
      let items = Array.isArray(data?.items) ? data.items : [];
      if (random) items = [...items].sort(() => Math.random() - 0.5);
      if (requestId !== requestRef.current) return;
      setQuestions((current) => reset ? items : mergeUniqueById(current, items));
      setTotal(Number(data?.total || 0));
      setOffset(nextOffset);
      if (reset) setActiveId(items[0]?.id || "");
      setResult(null);
      setAnswerDraft("");
      startedAtRef.current = Date.now();
    } catch (err) {
      if (requestId !== requestRef.current) return;
      setLoadError(err?.message || "题目加载失败");
      if (reset) setError(err?.message || "题目加载失败");
    } finally {
      if (requestId === requestRef.current) {
        loadingRef.current = false;
        setLoading(false);
      }
    }
  }, [account, filters, questions.length, total]);

  const loadWrongBook = useCallback(async ({ append = false } = {}) => {
    if (!account || wrongBookLoadingRef.current || (append && !wrongBookState.hasMore)) return;
    wrongBookLoadingRef.current = true;
    setWrongBookState((current) => ({ ...current, loading: true, error: "" }));
    setError("");
    try {
      const items = await api.reviewSite.listWrongBook({ limit: pageSize, offset: append ? wrongBookRef.current.length : 0 });
      const incoming = Array.isArray(items) ? items : [];
      const next = append ? mergeUniqueById(wrongBookRef.current, incoming) : incoming;
      wrongBookRef.current = next;
      setWrongBook(next);
      setWrongBookState({ loading: false, hasMore: incoming.length === pageSize, error: "" });
    } catch (err) {
      const message = err?.message || "错题本加载失败";
      setWrongBookState((current) => ({ ...current, loading: false, error: message }));
      if (!append) setError(message);
    } finally {
      wrongBookLoadingRef.current = false;
    }
  }, [account, wrongBookState.hasMore]);

  const loadStats = useCallback(async () => {
    try {
      const data = await api.study.dashboard();
      setStats(data?.practice || null);
    } catch (_error) {
      setStats(null);
    }
  }, []);

  useEffect(() => {
    if (!account) return;
    loadStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [account]);

  useEffect(() => {
    if (!account) return;
    if (view === "practice") loadQuestions({ reset: true });
    else if (view === "wrong") loadWrongBook();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [account, view, filters.category, filters.difficulty, filters.question_type]);

  const activeQuestion = useMemo(
    () => questions.find((q) => q.id === activeId) || questions[0] || null,
    [questions, activeId]
  );

  useEffect(() => {
    if (activeQuestion) startedAtRef.current = Date.now();
    setResult(null);
    setAnswerDraft("");
  }, [activeQuestion?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const questionId = String(navigationTarget?.question_id || "");
    if (questionId && questions.some((question) => question.id === questionId)) {
      setActiveId(questionId);
    }
  }, [navigationTarget?.nonce, navigationTarget?.question_id, questions]);

  async function submitAnswer(answerText) {
    if (!account) return onRequireAuth?.();
    if (!activeQuestion || submitting) return;
    if (!String(answerText || "").trim()) {
      setError("请先作答再提交。");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const elapsed = Math.round((Date.now() - startedAtRef.current) / 1000);
      const data = await api.reviewSite.submitAttempt(activeQuestion.id, {
        answer: String(answerText).trim(),
        elapsed_seconds: elapsed
      });
      setResult(data);
      loadStats();
      if (view === "wrong") loadWrongBook();
    } catch (err) {
      setError(err?.message || "作答提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function markWrong(entry, markType) {
    try {
      await api.reviewSite.markQuestion(entry.question?.id || entry.question_id || entry.id, {
        mark_type: markType,
        mastery_level: markType === "mastered" ? 5 : 0
      });
      await loadWrongBook();
      loadStats();
    } catch (err) {
      window.alert(`操作失败：${err?.message || "未知错误"}`);
    }
  }

  function practiceWrongEntry(entry) {
    const question = entry.question || entry;
    setView("practice");
    setQuestions([{
      id: question.id,
      prompt: question.prompt,
      choices: question.choices,
      answer: question.answer,
      answer_detail: question.answer_detail,
      question_type: question.question_type,
      practice_category: question.practice_category,
      subject: question.subject,
      difficulty: question.difficulty,
      tags: question.tags
    }]);
    setActiveId(question.id);
    setTotal(1);
  }

  function practiceQuestion(question) {
    practiceWrongEntry({ question });
  }

  if (!account) {
    return (
      <div className="training-page">
        <div className="home-guest card-v3">
          <div className="home-guest-icon"><PenLine size={26} /></div>
          <h3>登录后开始刷题训练</h3>
          <p>作答记录、正确率统计和错题本都会自动保存，弱项还会回流到复习计划。</p>
          <button type="button" className="btn-primary-v3" onClick={() => onRequireAuth?.()}>
            登录 / 注册 <ArrowRight size={15} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="training-page">
      <div className="reports-head">
        <div>
          <h2>刷题训练</h2>
          <p>题卡作答 · AI 讲评 · 错题自动收录</p>
        </div>
        <div className="training-tabs">
          <button type="button" className={view === "practice" ? "active" : ""} onClick={() => setView("practice")}>
            <Target size={14} /> 题库练习
          </button>
          <button type="button" className={view === "drill" ? "active" : ""} onClick={() => setView("drill")}>
            <Crosshair size={14} /> 专项训练
          </button>
          <button type="button" className={view === "spaced" ? "active" : ""} onClick={() => setView("spaced")}>
            <Brain size={14} /> 到期复习
          </button>
          <button type="button" className={view === "wrong" ? "active" : ""} onClick={() => setView("wrong")}>
            <XCircle size={14} /> 错题本 {stats?.wrong_book_count ? `(${stats.wrong_book_count})` : ""}
          </button>
        </div>
      </div>

      <div className="home-stat-grid training-stats">
        <MiniStat icon={<PenLine size={15} />} label="累计作答" value={`${stats?.total_attempts ?? 0} 题`} />
        <MiniStat icon={<TrendingUp size={15} />} label="正确率" value={stats ? `${Math.round(Number(stats.correct_rate || 0) * 100)}%` : "—"} />
        <MiniStat icon={<CheckCircle2 size={15} />} label="本周作答" value={`${stats?.week_attempts ?? 0} 题`} sub={`今日 ${stats?.today_attempts ?? 0}`} />
        <MiniStat icon={<Star size={15} />} label="已攻克错题" value={`${stats?.mastered_count ?? 0} 题`} sub={`待清 ${stats?.wrong_book_count ?? 0}`} />
      </div>

      {error && <p className="resume-hint error">{error}</p>}

      {view === "practice" ? (
        <>
          <div className="training-filters card-v3">
            <select className="v3-input" value={filters.category} onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))}>
              {CATEGORY_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
            </select>
            <select className="v3-input" value={filters.difficulty} onChange={(e) => setFilters((f) => ({ ...f, difficulty: e.target.value }))}>
              {DIFFICULTY_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
            </select>
            <select className="v3-input" value={filters.question_type} onChange={(e) => setFilters((f) => ({ ...f, question_type: e.target.value }))}>
              {TYPE_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
            </select>
            <input
              className="v3-input"
              placeholder="搜索关键词"
              value={filters.keyword}
              onChange={(e) => setFilters((f) => ({ ...f, keyword: e.target.value }))}
            onKeyDown={(e) => { if (e.key === "Enter") loadQuestions({ reset: true }); }}
            />
            <button type="button" className="btn-ghost-v3 small" onClick={() => loadQuestions({ reset: true })}>
              <RefreshCw size={13} /> 查询
            </button>
            <button type="button" className="btn-primary-v3 small" onClick={() => loadQuestions({ reset: true, random: true })}>
              <Shuffle size={13} /> 随机一组
            </button>
          </div>

          {loading && !questions.length ? (
            <div className="home-loading"><Loader2 size={22} className="spin" /> 正在抽题…</div>
          ) : !activeQuestion ? (
            <div className="reports-empty card-v3">
              <PenLine size={24} />
              <h3>没有符合条件的题目</h3>
              <p>换个筛选条件，或先导入题库。</p>
            </div>
          ) : (
            <div className="training-layout">
              <div className="training-question-list">
                {questions.map((q, index) => (
                  <button
                    key={q.id}
                    type="button"
                    className={`training-question-item ${q.id === activeQuestion.id ? "active" : ""}`}
                    onClick={() => setActiveId(q.id)}
                  >
                    <span>{index + 1}</span>
                    <strong>{(q.prompt || "未命名题目").slice(0, 28)}</strong>
                    <i>{isChoice(q) ? "选择" : "主观"}</i>
                  </button>
                ))}
                <InfiniteScrollSentinel
                  hasMore={questions.length < total}
                  loading={loading}
                  error={loadError}
                  onLoadMore={() => loadQuestions()}
                />
              </div>

              <QuestionCard
                question={activeQuestion}
                result={result}
                submitting={submitting}
                answerDraft={answerDraft}
                onDraftChange={setAnswerDraft}
                onSubmit={submitAnswer}
                onNext={() => {
                  const idx = questions.findIndex((q) => q.id === activeQuestion.id);
                  if (idx >= 0 && idx < questions.length - 1) setActiveId(questions[idx + 1].id);
                  else if (questions.length < total) loadQuestions();
                }}
              />
            </div>
          )}
        </>
      ) : view === "wrong" ? (
        <WrongBookView state={wrongBookState} entries={wrongBook} onLoadMore={() => loadWrongBook({ append: true })} onPractice={practiceWrongEntry} onMark={markWrong} />
      ) : view === "drill" ? (
        <SpecializedDrillPanel onPractice={practiceQuestion} />
      ) : (
        <SpacedReviewPanel onPractice={practiceQuestion} />
      )}
    </div>
  );
}

function MiniStat({ icon, label, value, sub }) {
  return (
    <div className="report-trend-card card-v3">
      <span className="home-stat-icon">{icon}</span>
      <small>{label}</small>
      <strong>{value}</strong>
      {sub && <em>{sub}</em>}
    </div>
  );
}

function QuestionCard({ question, result, submitting, answerDraft, onDraftChange, onSubmit, onNext }) {
  const choice = isChoice(question);
  return (
    <article className="training-question-card card-v3">
      <div className="training-question-head">
        <div className="training-question-tags">
          <i className="v3-chip">{question.practice_category || "综合"}</i>
          {question.subject && <i className="v3-chip">{question.subject}</i>}
          <i className="v3-chip">{question.difficulty || "medium"}</i>
        </div>
      </div>
      <h3 className="training-prompt">{question.prompt}</h3>

      {choice ? (
        <div className="training-choices">
          {(question.choices || []).map((item, index) => {
            const label = choiceLabel(item, index);
            const text = choiceText(item);
            const picked = answerDraft === label;
            const isCorrect = result && result.reference_answer && label === String(result.reference_answer).trim().slice(0, 1);
            const isWrongPick = result && picked && result.correct === false;
            return (
              <button
                key={index}
                type="button"
                className={`training-choice ${picked ? "picked" : ""} ${result ? (isCorrect ? "correct" : isWrongPick ? "wrong" : "") : ""}`}
                disabled={submitting || Boolean(result)}
                onClick={() => onSubmit(label)}
              >
                <b>{label}</b>
                <span>{text}</span>
                {result && isCorrect && <CheckCircle2 size={16} />}
                {result && isWrongPick && <XCircle size={16} />}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="training-subjective">
          <textarea
            className="v3-input training-answer"
            placeholder="输入你的回答，提交后 AI 会按要点打分并给出讲评…"
            rows={7}
            value={answerDraft}
            disabled={submitting || Boolean(result)}
            onChange={(e) => onDraftChange(e.target.value)}
          />
          {!result && (
            <button type="button" className="btn-primary-v3" disabled={submitting} onClick={() => onSubmit(answerDraft)}>
              {submitting ? <Loader2 size={15} className="spin" /> : <PenLine size={15} />}
              提交作答
            </button>
          )}
        </div>
      )}

      {result && (
        <div className={`training-result ${result.correct === false ? "wrong" : result.correct === true ? "correct" : "open"}`}>
          <div className="training-result-head">
            {result.correct === true ? <CheckCircle2 size={17} /> : result.correct === false ? <XCircle size={17} /> : <Target size={17} />}
            <strong>
              {result.correct === true ? "回答正确" : result.correct === false ? "回答有误，已自动收入错题本" : `已记录 · 参考得分 ${result.score ?? "—"}`}
            </strong>
            {result.graded_by === "llm" && <i className="v3-chip">AI 讲评</i>}
            <button type="button" className="btn-ghost-v3 small" onClick={onNext}>
              下一题 <ArrowRight size={13} />
            </button>
          </div>
          {result.feedback && <p className="training-feedback">{result.feedback}</p>}
          {(result.reference_answer || result.explanation) && (
            <div className="training-reference">
              <strong>参考答案</strong>
              <p>{result.reference_answer || ""}{result.explanation ? `：${result.explanation}` : ""}</p>
            </div>
          )}
          {Array.isArray(result.suggestions) && result.suggestions.length > 0 && (
            <ul className="training-suggestions">
              {result.suggestions.slice(0, 3).map((s, i) => <li key={i}>{typeof s === "string" ? s : s?.text || s?.title || ""}</li>)}
            </ul>
          )}
        </div>
      )}
    </article>
  );
}

function WrongBookView({ state, entries, onLoadMore, onPractice, onMark }) {
  if (state.loading && !entries.length) return <div className="home-loading"><Loader2 size={22} className="spin" /> 加载错题本…</div>;
  if (!entries.length) {
    return (
      <div className="reports-empty card-v3">
        <CheckCircle2 size={24} />
        <h3>错题本是空的</h3>
        <p>作答错误的题目会自动收录；攻克后可以标记掌握。</p>
      </div>
    );
  }
  return (
    <div className="wrong-book-list">
      {entries.map((entry) => {
        const question = entry.question || entry;
        const mastered = entry.mark_type === "mastered" || Number(entry.mastery_level || 0) >= 3;
        return (
          <article key={entry.id || question.id} className={`wrong-book-item card-v3 ${mastered ? "mastered" : ""}`}>
            <div className="wrong-book-main">
              <strong>{question.prompt}</strong>
              <span>
                {question.practice_category || "综合"} · {question.subject || question.question_type || "练习"} · 错 {entry.attempt_count || entry.wrong_count || 1} 次
              </span>
              <div className="wrong-book-stars">
                {[1, 2, 3, 4, 5].map((level) => (
                  <Star key={level} size={13} fill={level <= Number(entry.mastery_level || 0) ? "currentColor" : "none"} />
                ))}
              </div>
            </div>
            <div className="wrong-book-actions">
              <button type="button" className="btn-primary-v3 small" onClick={() => onPractice(entry)}>
                <Undo2 size={13} /> 重做
              </button>
              <button type="button" className="btn-ghost-v3 small" onClick={() => onMark(entry, mastered ? "wrong" : "mastered")}>
                <CheckCircle2 size={13} /> {mastered ? "标记未掌握" : "标记已掌握"}
              </button>
            </div>
          </article>
        );
      })}
      <InfiniteScrollSentinel hasMore={state.hasMore} loading={state.loading} error={state.error} onLoadMore={onLoadMore} />
    </div>
  );
}
