const SECRET_PATTERNS = [
  [/\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b/giu, "[登录凭证已隐藏]"],
  [/\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]{10,})?\b/gu, "[登录凭证已隐藏]"],
  [/\b(?:sk|rk|pk|api)[-_][A-Za-z0-9_-]{12,}\b/giu, "[敏感信息已隐藏]"],
  [/(?:authorization|access[_ -]?token|refresh[_ -]?token|api[_ -]?key|secret)\s*[:=]\s*["']?[^\s,"'}]{8,}/giu, "[敏感信息已隐藏]"],
  [/([?&](?:token|access_token|refresh_token|api_key|key|secret)=)[^&#\s]+/giu, "$1[敏感信息已隐藏]"]
];

const INTERNAL_DETAIL_PATTERNS = [
  /\b(?:request|trace|span|session)[_-]?id\s*[:=]\s*[A-Za-z0-9-]{8,}/iu,
  /\b(?:HTTP\s*)?5\d\d\b/u,
  /\b(?:ECONNREFUSED|ETIMEDOUT|ENOTFOUND|TypeError|ValidationError)\b/u,
  /\/api\/[A-Za-z0-9_?&=./{}:-]+/u,
  /(?:Nginx|CSP|localhost|127\.0\.0\.1|stack trace|traceback)/iu
];

export function redactSensitiveText(value = "") {
  let text = String(value || "");
  for (const [pattern, replacement] of SECRET_PATTERNS) {
    text = text.replace(pattern, replacement);
  }
  return text;
}

export function productErrorMessage(errorOrMessage, fallback = "操作没有完成，请稍后重试。") {
  const raw = typeof errorOrMessage === "string"
    ? errorOrMessage
    : errorOrMessage?.message || errorOrMessage?.error?.message || "";
  const message = redactSensitiveText(raw)
    .replace(/^Error invoking remote method '[^']+':\s*/u, "")
    .replace(/^Error:\s*/u, "")
    .trim();

  if (!message) return fallback;
  if (message.includes("[敏感信息已隐藏]") || message.includes("[登录凭证已隐藏]")) {
    return fallback;
  }
  if (/401|unauthorized|登录状态|认证|凭证.*(?:失效|过期)/iu.test(message)) {
    return "登录状态已失效，请重新登录。";
  }
  if (/403|forbidden|没有权限|无权/iu.test(message)) {
    return "当前账户没有权限执行此操作。";
  }
  if (/404|not found|不存在/iu.test(message)) {
    return "相关内容不存在或已被删除。";
  }
  if (/429|too many|频繁|限流/iu.test(message)) {
    return "操作有些频繁，请稍后再试。";
  }
  if (/无法连接|fetch|network|网络|ECONN|Nginx|CSP|localhost|127\.0\.0\.1/iu.test(message)) {
    return "暂时无法连接服务，请检查网络后重试。";
  }
  if (/超时|timeout|时间较长/iu.test(message)) {
    return "响应时间较长，请稍后重试。";
  }
  if (/invalid json|无效 JSON|stack trace|traceback|ValidationError|TypeError/iu.test(message)) {
    return fallback;
  }
  if (INTERNAL_DETAIL_PATTERNS.some((pattern) => pattern.test(message))) {
    return fallback;
  }
  return message.length > 160 ? fallback : message;
}
