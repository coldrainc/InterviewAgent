# GitHub AI Knowledge Sources

这些资料用于补充面试官知识库，覆盖 LLM、RAG、Agent、Prompt Engineering、生产化、安全和评估。

## Sources

- `microsoft/generative-ai-for-beginners`
  - 选取核心课程 README，覆盖 GenAI 应用生命周期、RAG、向量数据库、函数调用、安全、Agent 等。
- `microsoft/ai-agents-for-beginners`
  - 选取核心课程 README，覆盖 Agentic RAG、工具使用、多 Agent、规划、记忆、生产化和安全。
- `dair-ai/Prompt-Engineering-Guide`
  - 选取 prompts guides，覆盖基础/高级 prompt、可靠性、对抗提示和应用场景。
- `ather-techie/rag-interview-system`
  - RAG 系统设计、失败模式、面试题库、评估和决策系统。
- `sreekanth-madisetty/Awesome-LLM-Interview-Questions`
  - LLM/RAG/Agent/微调/量化等面试题。
- `llmgenai/LLMInterviewQuestions`
  - LLM 面试问题集合。
- `real-ai-project-interview-questions`
  - 基于公开 AI/RAG/Agent/system design 面试题源和本项目生产化目标整理的原创项目追问题库，覆盖真实面试中的方案设计、故障排查、指标评测、上线运维、安全治理。
- `industry-ai-engineering-requirements`
  - 基于 NIST AI RMF、ISO/IEC 42001、OWASP LLM Top 10、OpenTelemetry GenAI、MCP/A2A 协议和主流 LLMOps/云厂商实践整理的行业级 AI 工程要求知识库。

## Import Policy

- 只导入 Markdown 文档。
- 跳过 translations、assets、notebooks、代码样例和大体量非文本资源。
- 原始 GitHub 仓库未 vendored 到项目内，只保留筛选后的知识库文档。
- 对公开题源进行归纳和重写，不复制大段原文；新增题库优先保持“真实问法 + 追问 + 回答要点”的结构，便于 Agent 在面试中生成追问。
