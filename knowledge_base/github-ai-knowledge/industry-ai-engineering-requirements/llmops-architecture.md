# 生产级 LLMOps 架构要求

## 核心要求

行业里的 AI 应用已经从“能调通模型”进入“可持续运营”的阶段。生产级 LLMOps 通常需要覆盖：

- 模型接入层：多模型、多 provider、fallback、限流、熔断、超时。
- 编排层：prompt template、RAG、tool calling、workflow、AgentLoop。
- 数据层：文档、向量、会话、记忆、反馈、评测集。
- 质量层：离线评测、线上反馈、人工审核、回归测试。
- 安全层：输入过滤、输出护栏、权限、PII 脱敏、审计。
- 观测层：trace、token、latency、retrieval hits、tool calls、cost。
- 发布层：版本管理、灰度、A/B、回滚、配置开关。

## 生产链路参考

```text
Client
  -> API Gateway / Auth / Rate Limit
  -> Input Policy / PII Redaction
  -> Orchestrator
       -> Prompt Registry
       -> RAG Retriever / Reranker
       -> Tool Router / Agent Workflow
       -> Model Router
  -> Output Validation / Safety Guardrails
  -> Response / Citation / Structured Result
  -> Trace / Feedback / Eval Dataset
```

## 关键设计点

### 1. Model Router

模型路由不只是“主模型失败后换一个”。更合理的路由维度包括：

- 任务类型：分类、抽取、摘要、问答、代码、推理。
- 风险等级：高风险任务用更强模型或人工审核。
- 延迟要求：实时交互优先低延迟模型。
- 成本预算：低价值任务使用小模型。
- 语言和领域：中文、代码、法律、医疗、金融等。

面试追问：

- 你如何判断一个请求可以用小模型？
- fallback 到弱模型时怎么提示用户？
- 不同模型输出格式不一致怎么兼容？

### 2. Prompt Registry

Prompt 应该版本化管理，而不是散落在代码里：

- prompt_id、version、owner、description。
- 输入变量 schema 和默认值。
- 支持灰度、回滚、A/B。
- 每次变更必须跑 eval set。
- 记录 prompt hash，便于线上问题回溯。

面试追问：

- prompt 变更为什么可能比代码变更更危险？
- prompt 和业务配置怎么隔离？
- 谁有权限修改 production prompt？

### 3. Workflow 优先于裸 Agent

生产系统更常见的是“确定性工作流 + 局部模型决策”，而不是完全开放的 Agent。

适合工作流的场景：

- 步骤固定。
- 有合规要求。
- 需要断点恢复。
- 有副作用工具调用。
- 需要可测试和可审计。

适合 Agent 的场景：

- 信息收集路径不确定。
- 工具组合有多种可能。
- 任务是开放探索。
- 允许试错和人工确认。

面试追问：

- 你的 Agent 项目哪些节点是确定性的？
- 哪些决策交给模型，哪些必须由代码控制？
- 如果模型误判下一步怎么办？

## 面试高频问题

### Q1: 一个 LLM 应用从 demo 到生产差什么？

高质量回答应包括：质量评测、trace、权限、成本、回滚、数据闭环、失败降级、用户反馈和安全护栏。

### Q2: 为什么需要 LLMOps？

因为 LLM 应用的行为会随模型版本、prompt、检索数据、用户输入和工具状态变化。没有 LLMOps，就无法稳定复现问题、评估改动、控制成本和治理风险。

### Q3: 如何做多环境管理？

至少区分 dev、staging、production。prompt、索引、模型路由、工具权限、评测集都要有环境隔离。生产数据不能随意流入测试环境。

