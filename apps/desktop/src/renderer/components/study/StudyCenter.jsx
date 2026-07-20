import { useState } from "react";
import { BookOpenCheck, CheckCircle2, Eye, EyeOff, Filter, RefreshCw, UploadCloud } from "lucide-react";

const subjectOptions = [
  { value: "", label: "全部科目" },
  { value: "general", label: "通用" },
  { value: "project", label: "项目深挖" },
  { value: "system_design", label: "系统设计" },
  { value: "algorithm", label: "算法 / 数据结构" },
  { value: "backend", label: "后端工程" },
  { value: "frontend", label: "前端工程" },
  { value: "database", label: "数据库" },
  { value: "security", label: "应用安全" },
  { value: "recommendation", label: "推荐系统" },
  { value: "customer_service", label: "智能客服" },
  { value: "risk_control", label: "风控" },
  { value: "compliance", label: "合规" },
  { value: "audit", label: "审计" },
  { value: "multi_tenant", label: "多租户" },
  { value: "rbac", label: "RBAC 权限" },
  { value: "integration", label: "系统集成" },
  { value: "rag", label: "RAG" },
  { value: "agent_harness", label: "Agent Harness" },
  { value: "agentops", label: "AgentOps" },
  { value: "search", label: "搜索" },
  { value: "multi_agent", label: "多 Agent 协作" },
  { value: "workflow", label: "复杂任务编排" },
  { value: "async_workflow", label: "异步工作流" },
  { value: "long_running_tasks", label: "长任务执行平台" },
  { value: "evaluation", label: "质量评估" },
  { value: "behavioral", label: "行为面试" },
  { value: "communication", label: "沟通协作" },
  { value: "xingce", label: "行测" },
  { value: "shenlun", label: "申论" },
  { value: "interview", label: "结构化面试" }
];

const categoryOptions = [
  { value: "", label: "全部面试类型", description: "混合查看所有面试类型的默认题和自定义题。", subjects: [] },
  { value: "internet", label: "互联网行业", description: "高并发、系统设计、项目深挖和工程稳定性。", subjects: ["project", "system_design", "algorithm", "backend", "frontend", "database", "security"] },
  { value: "ai_application", label: "AI 应用 / 大模型", description: "RAG、Agent、评测、工具调用和安全治理。", subjects: ["rag", "agent_harness", "agentops", "search", "multi_agent", "workflow", "async_workflow", "long_running_tasks", "evaluation"] },
  { value: "ecommerce", label: "电商 / 本地生活", description: "商品搜索、导购客服、交易转化和售后风控。", subjects: ["search", "recommendation", "customer_service", "risk_control", "system_design"] },
  { value: "fintech", label: "金融科技", description: "金融知识库、合规、风控、审计和高可靠。", subjects: ["rag", "risk_control", "compliance", "audit", "system_design"] },
  { value: "enterprise_saas", label: "企业 SaaS / ToB", description: "多租户、权限、工作流、系统集成和私有化交付。", subjects: ["multi_tenant", "rbac", "workflow", "integration", "audit"] },
  { value: "civil_service", label: "考公 / 公职考试", description: "行测、申论、结构化面试和公共服务表达。", subjects: ["xingce", "shenlun", "interview"] }
];

export function StudyCenter({
  studyState,
  studyFilters,
  onFilterChange,
  onReload,
  onImportQuestions,
  activeInterviewType,
  activeInterviewLabel,
  onBack
}) {
  const questions = studyState.questions?.items || [];
  const total = studyState.questions?.total || 0;
  const categories = normalizeCategoryOptions(studyState.categories);
  const activeCategory = categories.find((item) => item.value === studyFilters.category);
  const visibleSubjectOptions = subjectOptionsForCategory(activeCategory);
  return (
    <section className="study-center">
      <div className="study-hero">
        <div>
          <span className="eyebrow">Practice Center</span>
          <h3>面试刷题</h3>
          <p>刷题类型和面试配置保持一致。先选面试类型，再按对应科目做题、复盘和上传补充题库。</p>
        </div>
        <div className="setup-hero-actions">
          <button type="button" className="secondary-action inline" onClick={onBack}>返回工作台</button>
        </div>
      </div>

      <div className="practice-context">
        <span>当前面试配置：{activeInterviewLabel || categoryLabel(activeInterviewType) || "未选择"}</span>
        {activeInterviewType && studyFilters.category !== activeInterviewType && (
          <button type="button" onClick={() => onFilterChange({ category: activeInterviewType, subject: "" })}>
            同步到当前面试类型
          </button>
        )}
      </div>

      <div className="practice-category-tabs" aria-label="刷题类型">
        {categories.map((item) => (
          <button
            key={item.value || "all"}
            type="button"
            className={studyFilters.category === item.value ? "active" : ""}
            onClick={() => onFilterChange({ category: item.value, subject: "" })}
          >
            <strong>{item.label}</strong>
            <span>{item.description}</span>
          </button>
        ))}
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
            <div className="study-toolbar">
              <button
                className="secondary-action inline compact"
                type="button"
                onClick={onImportQuestions}
                disabled={studyState.status === "loading"}
              >
                <UploadCloud size={15} />
                上传题库
              </button>
              <button className="icon-button" type="button" onClick={onReload} aria-label="刷新题库">
                <RefreshCw size={15} />
              </button>
            </div>
          </div>
          <div className="study-filters">
            <label>
              <span>训练类型</span>
              <select value={studyFilters.category} onChange={(event) => onFilterChange({ category: event.target.value, subject: "" })}>
                {categories.map((item) => <option key={item.value || "all"} value={item.value}>{item.label}</option>)}
              </select>
            </label>
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
                {visibleSubjectOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
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
          {studyState.importMessage && <p className="resume-hint success">{studyState.importMessage}</p>}
          <p className="resume-hint">当前筛选共 {total} 道题，题库类型与面试配置保持同一套分类。CSV 字段支持 category、exam_year、exam_name、subject、question_type、prompt、choices、answer、explanation、difficulty、tags。</p>
          <div className="question-list">
            {questions.length ? questions.map((question) => (
              <QuestionCard key={question.id} question={question} />
            )) : (
              <p className="resume-hint">暂无匹配题目。可以切换训练类型，或上传自己的合法题库作为补充。</p>
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
        <span>{categoryLabel(question.practice_category || question.category)}</span>
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

function categoryLabel(value) {
  return categoryOptions.find((item) => item.value === value)?.label || value || "通用";
}

function normalizeCategoryOptions(categories) {
  const backendOptions = Array.isArray(categories) ? categories : [];
  const merged = [
    categoryOptions[0],
    ...backendOptions.map((item) => ({
      value: item.value || "",
      label: item.label || categoryLabel(item.value),
      description: item.description || "",
      subjects: Array.isArray(item.subjects) ? item.subjects : []
    }))
  ];
  const seen = new Set();
  const source = merged.length > 1
    ? merged
    : categoryOptions.map((item) => ({ ...item, description: item.value ? "按该类型查看默认题和上传题。" : "混合查看所有题。" }));
  return source.filter((item) => {
    if (seen.has(item.value)) return false;
    seen.add(item.value);
    return true;
  });
}

function subjectOptionsForCategory(category) {
  if (!category?.subjects?.length) {
    return subjectOptions;
  }
  const allowed = new Set(["", ...category.subjects, "general", "behavioral", "communication"]);
  return subjectOptions.filter((item) => allowed.has(item.value));
}
