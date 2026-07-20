const QUESTION_BANK_MAX_ROWS = 500;

const CSV_FIELD_ALIASES = {
  year: "exam_year",
  examYear: "exam_year",
  question: "prompt",
  type: "question_type",
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
  normalized.exam_year = Number(normalized.exam_year || normalized.year || 0);
  normalized.exam_name = String(normalized.exam_name || "自定义题库").trim();
  normalized.subject = String(normalized.subject || "xingce").trim();
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

function normalizeList(value) {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  return String(value || "")
    .split("|")
    .map((item) => item.trim())
    .filter(Boolean);
}
