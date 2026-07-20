const QUESTION_BANK_MAX_ROWS = 500;

const CSV_FIELD_ALIASES = {
  year: "exam_year",
  examYear: "exam_year",
  question: "prompt",
  type: "question_type",
  practiceCategory: "practice_category",
  practice_category: "practice_category",
  category: "practice_category",
  sourceUrl: "source_url",
  sourceURL: "source_url"
};

export function parseQuestionBankFile(filename, text) {
  const cleanedText = String(text || "").trim();
  if (!cleanedText) {
    throw new Error("题库文件为空。");
  }
  const extension = filename.split(".").pop()?.toLowerCase();
  const questions = extension === "csv"
    ? parseQuestionBankCsv(cleanedText)
    : parseQuestionBankJson(cleanedText);
  if (!questions.length) {
    throw new Error("没有识别到可导入的题目。");
  }
  if (questions.length > QUESTION_BANK_MAX_ROWS) {
    throw new Error(`单次最多导入 ${QUESTION_BANK_MAX_ROWS} 道题，请拆分文件后再上传。`);
  }
  return questions.map(normalizeQuestionRow);
}

function parseQuestionBankJson(text) {
  let payload;
  try {
    payload = JSON.parse(text);
  } catch (_error) {
    throw new Error("JSON 题库格式不正确。");
  }
  const rows = Array.isArray(payload) ? payload : payload?.questions;
  if (!Array.isArray(rows)) {
    throw new Error("JSON 题库需要是数组，或包含 questions 数组。");
  }
  return rows;
}

function parseQuestionBankCsv(text) {
  const rows = parseCsvRows(text);
  if (rows.length < 2) return [];
  const headers = rows[0].map((header) => normalizeHeader(header));
  return rows.slice(1).map((row) => {
    const item = {};
    headers.forEach((header, index) => {
      if (header) item[header] = row[index] || "";
    });
    return item;
  });
}

function parseCsvRows(text) {
  const rows = [];
  let field = "";
  let row = [];
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];
    if (quoted) {
      if (char === "\"" && next === "\"") {
        field += "\"";
        index += 1;
      } else if (char === "\"") {
        quoted = false;
      } else {
        field += char;
      }
      continue;
    }
    if (char === "\"") {
      quoted = true;
    } else if (char === ",") {
      row.push(field.trim());
      field = "";
    } else if (char === "\n") {
      row.push(field.trim());
      rows.push(row);
      row = [];
      field = "";
    } else if (char !== "\r") {
      field += char;
    }
  }
  row.push(field.trim());
  if (row.some(Boolean)) rows.push(row);
  return rows.filter((current) => current.some(Boolean));
}

function normalizeHeader(value) {
  const header = String(value || "").trim();
  return CSV_FIELD_ALIASES[header] || header;
}

function normalizeQuestionRow(row) {
  const normalized = { ...row };
  normalized.source = normalized.source || "user-upload";
  normalized.practice_category = normalizeCategory(normalized.practice_category || normalized.category || inferCategory(normalized));
  normalized.exam_year = Number(normalized.exam_year || normalized.year || 0);
  normalized.exam_name = String(normalized.exam_name || "自定义题库").trim();
  normalized.subject = normalizeSubject(normalized.subject || "general");
  normalized.question_type = String(normalized.question_type || normalized.type || "综合训练").trim();
  normalized.prompt = String(normalized.prompt || normalized.question || "").trim();
  normalized.choices = normalizeList(normalized.choices);
  normalized.tags = normalizeList(normalized.tags);
  normalized.answer = String(normalized.answer || "").trim();
  normalized.explanation = String(normalized.explanation || "").trim();
  normalized.difficulty = String(normalized.difficulty || "medium").trim();
  if (!normalized.prompt) {
    throw new Error("题库中存在空题目，请补充 prompt/question 字段。");
  }
  if (!normalized.exam_year) {
    throw new Error("题库中存在无效年份，请补充 exam_year/year 字段。");
  }
  return normalized;
}

function normalizeCategory(value) {
  const cleaned = String(value || "internet").trim().toLowerCase();
  const aliases = {
    "考公": "civil_service",
    "公考": "civil_service",
    "公务员": "civil_service",
    "civil-service": "civil_service",
    "civil service": "civil_service",
    "互联网": "internet",
    "互联网行业": "internet",
    "技术面试": "internet",
    "ai": "ai_application",
    "ai工程": "ai_application",
    "ai 工程": "ai_application",
    "ai应用": "ai_application",
    "ai 应用": "ai_application",
    "大模型": "ai_application",
    "ai_engineering": "ai_application",
    "电商": "ecommerce",
    "本地生活": "ecommerce",
    "电商 / 本地生活": "ecommerce",
    "金融": "fintech",
    "金融科技": "fintech",
    "tob": "enterprise_saas",
    "to b": "enterprise_saas",
    "企业saas": "enterprise_saas",
    "企业 saas": "enterprise_saas",
    "面试": "internet",
    "通用面试": "internet"
  };
  return aliases[cleaned] || cleaned || "internet";
}

function normalizeSubject(value) {
  const cleaned = String(value || "general").trim().toLowerCase();
  const aliases = {
    "项目深挖": "project",
    "系统设计": "system_design",
    "后端": "backend",
    "后端工程": "backend",
    "前端": "frontend",
    "前端工程": "frontend",
    "数据库": "database",
    "应用安全": "security",
    "安全": "security",
    "推荐": "recommendation",
    "推荐系统": "recommendation",
    "客服": "customer_service",
    "智能客服": "customer_service",
    "风控": "risk_control",
    "风险控制": "risk_control",
    "合规": "compliance",
    "审计": "audit",
    "多租户": "multi_tenant",
    "权限": "rbac",
    "rbac": "rbac",
    "系统集成": "integration",
    "集成": "integration",
    "算法": "algorithm",
    "数据结构": "algorithm",
    "agent harness": "agent_harness",
    "agentharness": "agent_harness",
    "agentops": "agentops",
    "agent ops": "agentops",
    "搜索": "search",
    "ai搜索": "search",
    "多 agent": "multi_agent",
    "多agent": "multi_agent",
    "多 agent 协作": "multi_agent",
    "复杂任务编排": "workflow",
    "任务编排": "workflow",
    "异步工作流": "async_workflow",
    "长任务": "long_running_tasks",
    "长任务执行平台": "long_running_tasks",
    "质量评估": "evaluation",
    "评估": "evaluation",
    "行为面试": "behavioral",
    "沟通协作": "communication",
    "行测": "xingce",
    "申论": "shenlun",
    "结构化面试": "interview"
  };
  return aliases[cleaned] || cleaned || "general";
}

function inferCategory(row) {
  const subject = String(row.subject || "").trim().toLowerCase();
  const examName = String(row.exam_name || "").trim().toLowerCase();
  if (["xingce", "shenlun"].includes(subject) || /考公|国考|省考|申论|行测/.test(examName)) {
    return "civil_service";
  }
  if (/ai|rag|agent|llm/.test(examName)) {
    return "ai_application";
  }
  return "internet";
}

function normalizeList(value) {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  return String(value || "")
    .split("|")
    .map((item) => item.trim())
    .filter(Boolean);
}
