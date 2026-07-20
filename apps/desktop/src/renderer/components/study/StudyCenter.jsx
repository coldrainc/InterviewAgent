import { useState } from "react";
import { BookOpenCheck, CheckCircle2, Database, Eye, EyeOff, Filter, RefreshCw } from "lucide-react";

const subjectOptions = [
  { value: "", label: "全部科目" },
  { value: "xingce", label: "行测" },
  { value: "shenlun", label: "申论" },
  { value: "interview", label: "结构化面试" }
];

export function StudyCenter({
  studyState,
  studyFilters,
  onFilterChange,
  onReload,
  onSeed,
  onBack
}) {
  const questions = studyState.questions?.items || [];
  const total = studyState.questions?.total || 0;
  return (
    <section className="study-center">
      <div className="study-hero">
        <div>
          <span className="eyebrow">Civil Service Study</span>
          <h3>刷题学习</h3>
          <p>围绕考公行测、申论和结构化面试做模块训练，题库支持后续批量导入历年数据。</p>
        </div>
        <div className="setup-hero-actions">
          <button type="button" className="secondary-action inline" onClick={onBack}>返回工作台</button>
          <button type="button" className="primary-action inline" onClick={onSeed} disabled={studyState.status === "loading"}>
            <Database size={17} />
            初始化样题
          </button>
        </div>
      </div>

      <div className="study-grid">
        <section className="study-block">
          <div className="panel-heading">
            <span><BookOpenCheck size={15} /> 学习路径</span>
          </div>
          <div className="learning-plan">
            {(studyState.plan || []).map((item) => (
              <article key={item.stage} className="learning-step">
                <span>{item.stage}</span>
                <strong>{item.title}</strong>
                <p>{item.description}</p>
                <ul>
                  {(item.tasks || []).map((task) => <li key={task}>{task}</li>)}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <section className="study-block wide">
          <div className="panel-heading">
            <span><Filter size={15} /> 题库训练</span>
            <button className="icon-button" type="button" onClick={onReload} aria-label="刷新题库">
              <RefreshCw size={15} />
            </button>
          </div>
          <div className="study-filters">
            <label>
              <span>年份</span>
              <input
                value={studyFilters.year}
                inputMode="numeric"
                placeholder="全部"
                onChange={(event) => onFilterChange({ year: event.target.value })}
              />
            </label>
            <label>
              <span>科目</span>
              <select value={studyFilters.subject} onChange={(event) => onFilterChange({ subject: event.target.value })}>
                {subjectOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
            <label>
              <span>题型</span>
              <input
                value={studyFilters.questionType}
                placeholder="如 言语理解"
                onChange={(event) => onFilterChange({ questionType: event.target.value })}
              />
            </label>
          </div>

          {studyState.error && <p className="resume-hint error">{studyState.error}</p>}
          {studyState.seedMessage && <p className="resume-hint success">{studyState.seedMessage}</p>}
          <p className="resume-hint">当前筛选共 {total} 道题。题目来源会标记为样题、导入或指定数据源。</p>
          <div className="question-list">
            {questions.length ? questions.map((question) => (
              <QuestionCard key={question.id} question={question} />
            )) : (
              <p className="resume-hint">暂无题目。可以先初始化样题，或用导入脚本批量导入合法题库。</p>
            )}
          </div>
        </section>
      </div>
    </section>
  );
}

function QuestionCard({ question }) {
  const [visible, setVisible] = useState(false);
  return (
    <article className="question-card">
      <div className="question-meta">
        <span>{question.exam_year}</span>
        <span>{question.exam_name}</span>
        <span>{question.subject}</span>
        <span>{question.question_type}</span>
        <span>{question.difficulty}</span>
      </div>
      <p className="question-prompt">{question.prompt}</p>
      {Boolean(question.choices?.length) && (
        <ol className="choice-list">
          {question.choices.map((choice, index) => (
            <li key={`${choice}-${index}`}>{String.fromCharCode(65 + index)}. {choice}</li>
          ))}
        </ol>
      )}
      <div className="question-actions">
        <button type="button" onClick={() => setVisible((current) => !current)}>
          {visible ? <EyeOff size={14} /> : <Eye size={14} />}
          {visible ? "隐藏解析" : "查看解析"}
        </button>
      </div>
      {visible && (
        <div className="answer-panel">
          <strong><CheckCircle2 size={14} /> 参考答案：{question.answer || "开放题"}</strong>
          <p>{question.explanation || "暂无解析。"}</p>
        </div>
      )}
    </article>
  );
}
