import { fallbackIndustries, fallbackModels } from "../constants/interview";

export function formatTime() {
  return new Date().toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit"
  });
}

export function formatDateTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export function turnsToMessages(turns) {
  const restored = [];
  turns.forEach((turn) => {
    if (turn.candidate) {
      restored.push({
        id: crypto.randomUUID(),
        role: "user",
        text: turn.candidate,
        fallback: false,
        time: formatDateTime(turn.updated_at)
      });
    }
    if (turn.interviewer) {
      restored.push({
        id: crypto.randomUUID(),
        role: "agent",
        text: turn.interviewer,
        fallback: Boolean(turn.fallback_used),
        time: formatDateTime(turn.created_at)
      });
    }
  });
  return restored;
}

export function normalizeDesktopError(message = "") {
  return message
    .replace(/^Error invoking remote method '[^']+':\s*/u, "")
    .replace(/^Error:\s*/u, "");
}

export function buildInterviewGoal(profile, seedMessage = "") {
  const baseGoal =
    profile.interviewGoal ||
    "请基于我的简历和做过的事情进行 AI 工程面试，重点深挖真实项目、RAG/Agent、评测、上线和安全治理。";
  if (!seedMessage) return baseGoal;
  return `${baseGoal}\n本轮启动意图：${seedMessage}`;
}

export function buildFocusAreas(profile, seedMessage = "", industryOptions = fallbackIndustries) {
  const role = profile.targetRole || "AI 应用工程师";
  const industry = currentIndustry(industryOptions, profile.industry);
  const label = industry?.label || "";
  const recommended = industry?.recommended_focus_areas || [];
  const areas = recommended.length
    ? recommended
    : [
        `${label}简历项目深挖`,
        `${label}${role}核心能力`,
        `${label}RAG / Agent / LLMOps 生产化`,
        `${label}评测、上线、安全与观测`,
        `${label}行为协作与项目复盘`
      ];
  if (seedMessage.includes("RAG")) {
    return ["简历中的 RAG 项目深挖", ...areas.filter((area) => !area.includes("简历项目"))];
  }
  if (seedMessage.includes("LLMOps") || seedMessage.includes("评测")) {
    return ["LLMOps、评测和上线治理", ...areas.filter((area) => !area.includes("评测"))];
  }
  if (seedMessage.includes("Agent") || seedMessage.includes("工具调用")) {
    return ["Agent 工具调用和安全护栏", ...areas.filter((area) => !area.includes("RAG / Agent"))];
  }
  return areas;
}

export function currentIndustry(industryOptions, value) {
  return industryOptions.find((industry) => industry.value === value) || industryOptions[0] || fallbackIndustries[0];
}

export function currentModel(modelOptions, value) {
  return modelOptions.find((model) => model.id === value) || modelOptions[0] || fallbackModels[0];
}

export function formatCredits(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number)) return String(value || "0");
  if (number >= 100) return number.toFixed(0);
  if (number >= 1) return number.toFixed(2);
  return number.toFixed(6).replace(/0+$/u, "").replace(/\.$/u, "");
}
