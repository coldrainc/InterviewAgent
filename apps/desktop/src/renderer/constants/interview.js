export const quickPrompts = [
  "请开始一场 AI Agent 项目面试",
  "我做过 RAG 知识库项目，请追问我生产化细节",
  "请围绕 LLMOps、评测和上线治理提问",
  "我想练习 Agent 工具调用和安全护栏"
];

export const interviewModes = [
  { value: "interviewer", label: "Agent 面试我" },
  { value: "candidate", label: "Agent 回答我" }
];

export const fallbackIndustries = [
  {
    value: "internet",
    label: "互联网行业",
    description: "面向高并发用户产品、内容/直播/社区/工具类业务。",
    production_signals: ["p95/p99 延迟", "QPS", "灰度通过率"],
    recommended_focus_areas: []
  }
];

export const fallbackModels = [
  {
    id: "gpt-5.5",
    provider: "openai",
    display_name: "OpenAI GPT-5.5",
    category: "默认通用",
    input_credits_per_1m: "500.00",
    output_credits_per_1m: "3000.00"
  },
  {
    id: "gpt-5.5-pro",
    provider: "openai",
    display_name: "OpenAI GPT-5.5 Pro",
    category: "最高质量",
    input_credits_per_1m: "3000.00",
    output_credits_per_1m: "18000.00"
  },
  {
    id: "gpt-5.4-mini",
    provider: "openai",
    display_name: "OpenAI GPT-5.4 mini",
    category: "高性价比",
    input_credits_per_1m: "75.00",
    output_credits_per_1m: "450.00"
  },
  {
    id: "claude-fable-5",
    provider: "anthropic",
    display_name: "Claude Fable 5",
    category: "长上下文深度分析",
    input_credits_per_1m: "1000.00",
    output_credits_per_1m: "5000.00"
  },
  {
    id: "gemini-3.5-flash",
    provider: "google",
    display_name: "Gemini 3.5 Flash",
    category: "多模态低延迟",
    input_credits_per_1m: "150.00",
    output_credits_per_1m: "900.00"
  },
  {
    id: "deepseek-v4-pro",
    provider: "deepseek",
    display_name: "DeepSeek V4 Pro",
    category: "高性价比推理",
    input_credits_per_1m: "44.00",
    output_credits_per_1m: "88.00"
  },
  {
    id: "qwen3.7-max",
    provider: "alibaba",
    display_name: "Qwen3.7 Max",
    category: "中文企业旗舰",
    input_credits_per_1m: "250.00",
    output_credits_per_1m: "750.00"
  },
  {
    id: "kimi-k2.7-code",
    provider: "moonshot",
    display_name: "Kimi K2.7 Code",
    category: "代码与 Agent",
    input_credits_per_1m: "100.00",
    output_credits_per_1m: "400.00"
  }
];
