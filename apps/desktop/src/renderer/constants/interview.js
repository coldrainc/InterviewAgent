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

export const llmModes = [
  {
    value: "fast",
    label: "快速",
    description: "DeepSeek V4 Flash，不开启思考，适合高频追问。",
    modelId: "deepseek-v4-flash",
    thinkingEnabled: false,
    reasoningEffort: "low"
  },
  {
    value: "standard",
    label: "标准思考",
    description: "DeepSeek V4 Pro，开启 high 思考，适合默认面试。",
    modelId: "deepseek-v4-pro",
    thinkingEnabled: true,
    reasoningEffort: "high"
  },
  {
    value: "deep",
    label: "深度思考",
    description: "DeepSeek V4 Pro，开启 max 思考，适合复杂系统设计和最终评价。",
    modelId: "deepseek-v4-pro",
    thinkingEnabled: true,
    reasoningEffort: "max"
  }
];

export const fallbackIndustries = [
  {
    value: "internet",
    label: "互联网行业",
    description: "面向高并发用户产品、内容/直播/社区/工具类业务。",
    production_signals: ["p95/p99 延迟", "QPS", "灰度通过率"],
    recommended_focus_areas: []
  },
  {
    value: "ai_application",
    label: "AI 应用 / 大模型",
    description: "面向 Agent、RAG、LLMOps、AI Copilot 和行业知识助手。",
    production_signals: ["忠实度", "检索命中率", "工具成功率"],
    recommended_focus_areas: ["RAG / Agent 生产化", "质量评估", "安全护栏"]
  },
  {
    value: "ecommerce",
    label: "电商 / 本地生活",
    description: "面向搜索推荐、导购客服、交易链路、履约售后。",
    production_signals: ["CTR", "CVR", "GMV"],
    recommended_focus_areas: ["商品搜索", "智能客服", "交易风控"]
  },
  {
    value: "fintech",
    label: "金融科技",
    description: "面向金融投研、风控、合规、客服和运营自动化。",
    production_signals: ["准确率", "审计覆盖率", "人工复核通过率"],
    recommended_focus_areas: ["合规风控", "金融知识库", "审计留痕"]
  },
  {
    value: "enterprise_saas",
    label: "企业 SaaS / ToB",
    description: "面向企业知识库、办公协作、CRM/ERP/工单等工作流。",
    production_signals: ["租户隔离通过率", "SLA", "工具调用成功率"],
    recommended_focus_areas: ["多租户权限", "业务工作流", "系统集成"]
  },
  {
    value: "civil_service",
    label: "考公 / 公职考试",
    description: "面向公务员、事业单位和选调备考，覆盖行测、申论和结构化面试。",
    production_signals: ["正确率", "限时完成率", "错题复盘率"],
    recommended_focus_areas: ["行测模块刷题", "申论材料分析", "结构化面试表达"]
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
