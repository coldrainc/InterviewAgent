import { useEffect, useState } from "react";
import {
  ArrowLeft, BookOpen, Check, Clock, ExternalLink, FileText, Flame, ListChecks,
  Mic, NotebookPen, Target, Zap
} from "lucide-react";

export function ReviewTaskDetailPage({ selection, onClose, onStartTask }) {
  const task = selection?.task;
  const [activeMaterial, setActiveMaterial] = useState(null);

  useEffect(() => {
    if (!task) return undefined;
    const closeOnEscape = (event) => event.key === "Escape" && onClose?.();
    const closeWithWorkspace = () => onClose?.();
    window.addEventListener("keydown", closeOnEscape);
    window.addEventListener("v3-close-all-drawers", closeWithWorkspace);
    return () => {
      window.removeEventListener("keydown", closeOnEscape);
      window.removeEventListener("v3-close-all-drawers", closeWithWorkspace);
    };
  }, [task, onClose]);

  useEffect(() => {
    setActiveMaterial(null);
  }, [task?.id]);

  if (!task) return null;

  const progress = selection.progress || {};
  const detail = buildTaskDetail(task, selection.day);
  const docs = normalizeDocs(task.docs, detail.materials);
  const action = task.link_type === "interview" || task.simulation
    ? { label: "开始模拟面试", icon: <Mic size={15} /> }
    : task.link_type === "practice"
      ? { label: "进入题库训练", icon: <BookOpen size={15} /> }
      : null;

  if (activeMaterial) {
    return (
      <ReviewMaterialPage
        doc={activeMaterial}
        task={task}
        day={selection.day}
        detail={detail}
        onBack={() => setActiveMaterial(null)}
      />
    );
  }

  return (
    <article className="v3-task-detail-page" aria-label="任务学习页">
      <button type="button" className="v3-btn ghost small v3-task-detail-back" onClick={onClose}>
        <ArrowLeft size={14} /> 返回计划
      </button>

      <header className="v3-task-detail-hero">
        <div>
          <span className="v3-task-detail-kicker">{selection.day?.day_label || "复习任务"} · {selection.day?.title || "学习页"}</span>
          <h3>{task.title || "未命名任务"}</h3>
          <p>{detail.objective}</p>
        </div>
        <div className="v3-task-detail-status">
          <span className={`v3-chip ${progress.done ? "toggle on" : ""}`}>
            {progress.done ? <Check size={11} /> : <Clock size={11} />}
            {progress.done ? "已完成" : "待完成"}
          </span>
          {task.critical && <span className="v3-chip warn"><Flame size={11} /> 核心任务</span>}
          {task.simulation && <span className="v3-chip accent"><Zap size={11} /> 模拟</span>}
        </div>
      </header>

      <div className="v3-task-detail-grid">
        <div className="v3-task-detail-main">
          <DetailSection icon={<Target size={16} />} title="复习内容">
            <ReadableText text={detail.content} />
          </DetailSection>

          {docs.length > 0 && (
            <DetailSection title="关联资料">
              <div className="v3-material-library">
                {docs.map((doc, index) => (
                  <MaterialCard
                    key={`${doc.href || doc.pageUrl || doc.label}-${index}`}
                    doc={doc}
                    onOpen={() => setActiveMaterial(doc)}
                  />
                ))}
              </div>
            </DetailSection>
          )}

          <DetailSection icon={<ListChecks size={16} />} title="执行步骤">
            <ol className="v3-task-detail-list">
              {detail.steps.map((step, index) => <li key={`${step}-${index}`}>{step}</li>)}
            </ol>
          </DetailSection>

          <DetailSection icon={<NotebookPen size={16} />} title="复盘问题">
            <ul className="v3-task-detail-list">
              {detail.questions.map((question, index) => <li key={`${question}-${index}`}>{question}</li>)}
            </ul>
          </DetailSection>
        </div>

        <aside className="v3-task-detail-aside">
          <DetailSection title="验收产出">
            <ul className="v3-task-detail-list compact">
              {detail.deliverables.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
            </ul>
          </DetailSection>

          <DetailSection title="学习记录">
            <div className="v3-task-detail-facts">
              <div><small>掌握度</small><strong>{Number(progress.mastery || progress.mastery_score || 0)}/5</strong></div>
              <div><small>学习笔记</small><strong>{progress.note?.trim() || "暂未记录"}</strong></div>
            </div>
          </DetailSection>

          {!!(task.tags || []).filter(Boolean).length && (
            <DetailSection title="任务标签">
              <div className="v3-task-detail-tags">
                {task.tags.filter(Boolean).map((tag) => <span className="v3-chip" key={tag}>{tag}</span>)}
              </div>
            </DetailSection>
          )}

          {action && <button type="button" className="v3-btn primary" onClick={() => onStartTask?.(task)}>{action.icon}{action.label}</button>}
        </aside>
      </div>
    </article>
  );
}

function ReviewMaterialPage({ doc, task, day, detail, onBack }) {
  return (
    <article className="v3-material-page" aria-label="资料阅读页">
      <button type="button" className="v3-btn ghost small v3-task-detail-back" onClick={onBack}>
        <ArrowLeft size={14} /> 返回任务
      </button>
      <header className="v3-material-page-hero">
        <span>{day?.day_label || "复习资料"} · {task?.title || "任务资料"}</span>
        <h3>{doc?.label || "资料正文"}</h3>
        <p>站内资料页</p>
      </header>
      <section className="v3-material-context">
        <div>
          <span>本任务复习内容</span>
          <ReadableText text={detail?.content || detail?.objective || task?.reason || ""} />
        </div>
        {!!detail?.steps?.length && (
          <div>
            <span>建议读法</span>
            <ol className="v3-task-detail-list compact">
              {detail.steps.slice(0, 4).map((step, index) => <li key={`${step}-${index}`}>{step}</li>)}
            </ol>
          </div>
        )}
      </section>
      <section className="v3-material-page-body">
        {doc?.content ? (
          <MaterialContent text={doc.content} />
        ) : doc?.href ? (
          <a href={doc.href} target="_blank" rel="noopener noreferrer">
            <ExternalLink size={14} /> 打开外部资料
          </a>
        ) : (
          <p>这份资料还没有正文内容。</p>
        )}
      </section>
    </article>
  );
}

function DetailSection({ title, children }) {
  return <section className="v3-task-detail-section"><span>{title}</span>{children}</section>;
}

function ReadableText({ text }) {
  const chunks = String(text || "").split(/\n{2,}/).map((item) => item.trim()).filter(Boolean);
  if (!chunks.length) return null;
  return <>{chunks.map((item, index) => <p key={`${item}-${index}`}>{item}</p>)}</>;
}

function MaterialCard({ doc, onOpen }) {
  const preview = String(doc.content || "").replace(/[#>*_`~-]/g, "").replace(/\s+/g, " ").trim();
  const handleOpen = () => {
    if (doc.content) {
      onOpen?.();
      return;
    }
    if (doc.href) window.open(doc.href, "_blank", "noopener,noreferrer");
  };
  return (
    <button type="button" className="v3-material-card" onClick={handleOpen}>
      <span className="v3-material-card-icon"><FileText size={15} /></span>
      <span className="v3-material-card-body">
        <strong>{doc.label}</strong>
        <small>{preview ? preview.slice(0, 96) : "打开资料页阅读完整内容"}</small>
      </span>
      <ExternalLink size={14} />
    </button>
  );
}

function MaterialLink({ doc, onOpen }) {
  if (doc.content) {
    return (
      <button type="button" className="v3-material-link" onClick={onOpen}>
          <FileText size={14} />
          <span>{doc.label}</span>
          <ExternalLink size={13} />
      </button>
    );
  }
  if (doc.href) {
    return (
      <a href={doc.href} target="_blank" rel="noopener noreferrer">
        <FileText size={14} /><span>{doc.label}</span><ExternalLink size={13} />
      </a>
    );
  }
  return (
    <div className="v3-material-item inert">
      <div><FileText size={14} /><span>{doc.label}</span></div>
    </div>
  );
}

function MaterialContent({ text }) {
  const lines = String(text || "").split(/\r?\n/);
  const blocks = [];
  let listItems = [];
  let listOrdered = false;
  let codeLines = [];
  let codeFence = false;

  function flushList() {
    if (!listItems.length) return;
    blocks.push({ type: "list", ordered: listOrdered, items: listItems });
    listItems = [];
    listOrdered = false;
  }

  function flushCode() {
    if (!codeLines.length) return;
    blocks.push({ type: "code", text: codeLines.join("\n") });
    codeLines = [];
  }

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (line.startsWith("```")) {
      if (codeFence) {
        flushCode();
        codeFence = false;
      } else {
        flushList();
        codeFence = true;
      }
      continue;
    }
    if (codeFence) {
      codeLines.push(rawLine);
      continue;
    }
    if (!line) {
      flushList();
      continue;
    }
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(line)) {
      flushList();
      blocks.push({ type: "divider" });
      continue;
    }
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      flushList();
      blocks.push({ type: "heading", level: heading[1].length, text: heading[2] });
      continue;
    }
    const bullet = line.match(/^[-*•]\s+(.+)$/);
    if (bullet) {
      if (listOrdered) flushList();
      listOrdered = false;
      listItems.push(bullet[1]);
      continue;
    }
    const ordered = line.match(/^\d+[.)、]\s+(.+)$/);
    if (ordered) {
      if (listItems.length && !listOrdered) flushList();
      listOrdered = true;
      listItems.push(ordered[1]);
      continue;
    }
    const quote = line.match(/^>\s?(.+)$/);
    if (quote) {
      flushList();
      blocks.push({ type: "quote", text: quote[1] });
      continue;
    }
    flushList();
    blocks.push({ type: "paragraph", text: line });
  }
  flushList();
  flushCode();

  return (
    <div className="v3-material-content">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          const Tag = block.level <= 1 ? "h2" : block.level === 2 ? "h3" : "h4";
          return <Tag key={`${block.text}-${index}`}>{renderInlineMarkdown(block.text)}</Tag>;
        }
        if (block.type === "list") {
          const Tag = block.ordered ? "ol" : "ul";
          return <Tag key={`list-${index}`}>{block.items.map((item, itemIndex) => <li key={`${item}-${itemIndex}`}>{renderInlineMarkdown(item)}</li>)}</Tag>;
        }
        if (block.type === "quote") {
          return <blockquote key={`${block.text}-${index}`}>{renderInlineMarkdown(block.text)}</blockquote>;
        }
        if (block.type === "code") {
          return <pre key={`code-${index}`}><code>{block.text}</code></pre>;
        }
        if (block.type === "divider") {
          return <hr key={`divider-${index}`} />;
        }
        return <p key={`${block.text}-${index}`}>{renderInlineMarkdown(block.text)}</p>;
      })}
    </div>
  );
}

function renderInlineMarkdown(text) {
  const parts = [];
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__)/g;
  let cursor = 0;
  let match;
  const value = String(text || "");
  while ((match = pattern.exec(value)) !== null) {
    if (match.index > cursor) parts.push(value.slice(cursor, match.index));
    const token = match[0];
    const key = `${token}-${match.index}`;
    if (token.startsWith("`")) {
      parts.push(<code key={key}>{token.slice(1, -1)}</code>);
    } else {
      parts.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    }
    cursor = match.index + token.length;
  }
  if (cursor < value.length) parts.push(value.slice(cursor));
  return parts.length ? parts : value;
}

function normalizeDocs(value, materials = []) {
  const normalizedMaterials = Array.isArray(materials) ? materials : [];
  const materialMap = new Map();
  for (const item of normalizedMaterials) {
    for (const key of [
      item?.source_index,
      item?.page_url,
      item?.href,
      item?.url,
      item?.label,
    ]) {
      const normalizedKey = String(key || "");
      if (normalizedKey) materialMap.set(normalizedKey, item);
    }
  }
  const docs = Array.isArray(value) && value.length
    ? value
    : normalizedMaterials.map((item, index) => ({
        label: item?.label || `资料 ${index + 1}`,
        source_index: item?.source_index ?? index,
        page_url: item?.page_url || `/review-site/materials/${item?.source_index ?? index}`,
        url: item?.url || item?.href || ""
      }));
  if (!docs.length) return [];
  return docs.flatMap((doc, index) => {
    const raw = typeof doc === "string" ? doc : doc?.url || doc?.link || "";
    const href = safeHttpUrl(raw);
    const label = typeof doc === "string" ? `资料 ${index + 1}` : doc?.label || doc?.title || `资料 ${index + 1}`;
    const sourceIndex = typeof doc === "object" ? doc?.source_index : index;
    const pageUrl = typeof doc === "object" ? doc?.page_url : "";
    const material = materialMap.get(String(sourceIndex ?? ""))
      || materialMap.get(pageUrl || "")
      || materialMap.get(raw)
      || materialMap.get(label)
      || {};
    if (!href && !material.content) return [];
    return [{
      href,
      label: material.label || label,
      pageUrl: material.page_url || pageUrl || `/review-site/materials/${sourceIndex ?? index}`,
      content: material.content || ""
    }];
  });
}

function safeHttpUrl(value) {
  try {
    const parsed = new URL(String(value || ""));
    return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : "";
  } catch {
    return "";
  }
}

function buildTaskDetail(task, day) {
  const payload = task?.link_payload && typeof task.link_payload === "object" ? task.link_payload : {};
  const detail = payload.detail && typeof payload.detail === "object" ? payload.detail : {};
  const tags = (task?.tags || []).filter(Boolean);
  const title = task?.title || "这项任务";
  return {
    objective: cleanText(detail.objective) || cleanText(payload.objective) || cleanText(task?.reason) || `围绕「${title}」形成可复述、可举例、可落到项目的答案。`,
    content: cleanText(detail.content) || cleanText(payload.content) || cleanText(task?.reason) || fallbackContent(title, tags, day),
    steps: listOrFallback(detail.steps || payload.steps, fallbackSteps(title, tags)),
    questions: listOrFallback(detail.questions || payload.questions || payload.review_questions, fallbackQuestions(title, tags)),
    deliverables: listOrFallback(detail.deliverables || payload.deliverables, fallbackDeliverables(title, day)),
    materials: Array.isArray(detail.materials) ? detail.materials : []
  };
}

function cleanText(value) {
  return String(value || "").trim();
}

function listOrFallback(value, fallback) {
  const list = Array.isArray(value)
    ? value.map((item) => cleanText(item)).filter(Boolean)
    : [];
  return list.length ? list : fallback;
}

function fallbackContent(title, tags, day) {
  const focus = tags.slice(0, 3).join("、") || day?.title || "面试复习";
  return `围绕「${title}」完成一次结构化复习：先把核心概念讲清楚，再补充项目案例、边界条件和追问回答，最后压缩成 60 秒口述版本。重点关注：${focus}。`;
}

function fallbackSteps(title, tags) {
  const focus = tags.includes("Codex") ? "Codex 的任务隔离、工具边界、工作树和审批体验" : "概念、项目案例、风险点和面试表达";
  return [
    `用 10 分钟列出「${title}」必须讲到的 3 个关键词。`,
    `补齐 ${focus}，每个点写一句业务价值和一个工程取舍。`,
    "整理 1 个可量化项目案例，包含背景、动作、结果和复盘。",
    "用 60 秒口述一遍，并记录卡顿点。"
  ];
}

function fallbackQuestions(title, tags) {
  const codexQuestion = tags.includes("Codex") ? "如果面试官追问 Codex 和普通 IDE 插件的差异，你如何从权限、上下文和交付闭环回答？" : "";
  return [
    `面试官问「你为什么这么设计 ${title}」，你的第一句话是什么？`,
    "这个方案最大的风险是什么？你如何监控、回滚或降级？",
    codexQuestion || "能不能把这个能力落到你简历中的一个项目，并给出具体指标？"
  ];
}

function fallbackDeliverables(title, day) {
  return [
    `完成「${title}」的 5 行速记。`,
    "沉淀 1 段 60 秒口述答案。",
    `满足当天验收：${day?.acceptance || "能脱稿复述关键结论，并回答 2 个追问。"}`
  ];
}
