const { config } = require("./config");

const modeOptions = [
  { value: "interviewer", label: "Agent 面试我" },
  { value: "candidate", label: "Agent 回答我" }
];

const defaultInterviewSetup = {
  mode: "interviewer",
  industry: "internet",
  targetRole: "AI 应用工程师",
  seniority: "高级",
  interviewGoal: "请基于我的简历和 AI 项目经历进行真实面试。",
  interviewerRequirements: "",
  focusAreas: ["简历项目深挖", "RAG / Agent 生产化", "评测、上线、安全与观测"]
};

function getInterviewSetup() {
  const saved = wx.getStorageSync(config.storageKeys.interviewSetup);
  if (!saved || typeof saved !== "object") {
    return { ...defaultInterviewSetup };
  }
  return {
    ...defaultInterviewSetup,
    ...saved,
    focusAreas: Array.isArray(saved.focusAreas) && saved.focusAreas.length
      ? saved.focusAreas
      : defaultInterviewSetup.focusAreas
  };
}

function saveInterviewSetup(patch = {}) {
  const setup = {
    ...getInterviewSetup(),
    ...patch
  };
  wx.setStorageSync(config.storageKeys.interviewSetup, setup);
  return setup;
}

function getModeLabel(mode) {
  return modeOptions.find((item) => item.value === mode)?.label || modeOptions[0].label;
}

function getIndustryLabel(industries, industry) {
  return industries.find((item) => item.value === industry)?.label || "互联网行业";
}

function getSetupSummary(setup, selectedIndustryLabel) {
  return `${getModeLabel(setup.mode)} · ${setup.targetRole || "目标岗位"} · ${selectedIndustryLabel || "行业"}`;
}

function buildInterviewGoal(setup = {}) {
  const sections = [`面试目标：\n${setup.interviewGoal || defaultInterviewSetup.interviewGoal}`];
  if (setup.interviewerRequirements) {
    sections.push(`面试官要求：\n${setup.interviewerRequirements}`);
  }
  return sections.join("\n\n");
}

module.exports = {
  defaultInterviewSetup,
  modeOptions,
  getInterviewSetup,
  saveInterviewSetup,
  getModeLabel,
  getIndustryLabel,
  getSetupSummary,
  buildInterviewGoal
};
