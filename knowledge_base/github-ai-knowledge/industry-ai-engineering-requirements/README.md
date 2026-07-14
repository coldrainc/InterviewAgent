# 行业级 AI 工程要求知识库

这组文档补充“现在行业对 AI 项目和 AI 工程师的要求”。重点不是某个框架 API，而是生产系统应该具备的能力：评测、观测、风险治理、安全、数据闭环、成本、可靠性、Agent 协议和上线流程。

## 参考方向

- NIST AI RMF / Generative AI Profile：风险识别、度量、治理和持续管理。
- ISO/IEC 42001：AI 管理体系、组织治理、责任边界和持续改进。
- OWASP Top 10 for LLM Applications：Prompt Injection、敏感信息泄漏、供应链、过度代理等风险。
- OpenTelemetry GenAI semantic conventions：LLM / Agent 调用链路观测。
- MLflow / LangSmith / 云厂商 GenAI 实践：评测、追踪、实验管理和线上反馈。
- MCP / A2A 等 Agent 协议：工具生态、权限、协议边界和跨 Agent 协作。

## 文档清单

- `llmops-architecture.md`：生产级 LLMOps 架构要求。
- `evaluation-quality-system.md`：评测体系、数据集、指标和准入门禁。
- `production-rag-requirements.md`：生产级 RAG 的数据、索引、权限、评测和更新。
- `agent-engineering-requirements.md`：Agent 工程、工具调用、协议、记忆和多 Agent。
- `security-governance-compliance.md`：LLM 安全、数据治理、合规和风险管理。
- `observability-cost-reliability.md`：可观测性、成本治理、可靠性和事故复盘。

## 面试使用方式

如果候选人只会讲“我会调用大模型 API”，可以追问：

1. 怎么证明质量可上线？
2. 出错后怎么定位？
3. 权限和敏感数据怎么保护？
4. Prompt / 模型 / 检索策略如何版本化和回滚？
5. 如何控制成本和 P95 延迟？
6. Agent 调工具的权限、幂等、审计如何做？

