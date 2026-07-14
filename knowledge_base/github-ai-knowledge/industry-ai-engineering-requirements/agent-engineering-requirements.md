# Agent 工程要求

## 行业趋势

Agent 项目正在从“开放 ReAct demo”转向“可控工作流 + 工具协议 + 权限治理”。现在面试更看重：

- 任务边界是否清晰。
- Agent 是否可控、可测、可恢复。
- 工具调用是否安全。
- 状态和记忆是否可治理。
- 多 Agent 是否真的必要。
- MCP / A2A 等协议是否理解其边界和风险。

## Agent 基本架构

```text
User Goal
  -> Task Classifier
  -> Planner / Workflow
  -> Tool Router
  -> Executor
  -> Verifier
  -> Memory Writer
  -> Final Response
```

## AgentLoop 硬约束

生产 Agent 必须有 deterministic guardrails：

- max_steps。
- max_wall_time。
- max_cost。
- max_tool_errors。
- repeated_tool_call_limit。
- no_progress_limit。
- human_approval_required_actions。
- abort / pause / resume。

面试追问：

- 你怎么检测 Agent 没有进展？
- 如果模型连续调用相同工具怎么办？
- 终止条件由模型判断还是代码判断？

## 工具调用要求

### Tool Schema

工具 schema 应包括：

```text
name
description
input_schema
output_schema
risk_level
required_permissions
timeout
retry_policy
idempotency_key
audit_fields
```

### 工具风险分级

- read-only：搜索、查询、摘要。
- low-risk write：创建草稿、生成报告。
- medium-risk write：发内部通知、创建工单。
- high-risk write：删除、付款、权限变更、外发消息。

高风险工具必须：

- dry-run。
- 展示影响范围。
- 用户确认。
- 审计。
- 可回滚或补偿。

## 记忆系统要求

Agent memory 需要写入决策，不是保存所有对话。

应进入 memory：

- 稳定用户偏好。
- 长期事实。
- 已确认业务规则。
- 失败复盘。
- 可复用解决方案。

不应进入 memory：

- 寒暄。
- 短期临时状态。
- 重复确认。
- 密钥、token、身份证、手机号等敏感信息。
- 未确认的模型猜测。

## MCP / Agent 协议理解

MCP 可以把工具和资源以统一协议暴露给模型应用，但它不是安全边界本身。生产使用时仍需：

- server allowlist。
- tool permission。
- user consent。
- token scope。
- prompt injection 防护。
- tool output sanitization。
- audit logging。

A2A 或类似跨 Agent 协作协议强调 agent interoperability，但真实项目中仍要定义：

- agent identity。
- capability discovery。
- auth。
- task contract。
- result schema。
- failure handling。

## 多 Agent 要求

只有在以下场景才值得多 Agent：

- 任务天然分工。
- 需要并行。
- 需要互审。
- 单 Agent 上下文和工具过多。

多 Agent 风险：

- 成本上升。
- 延迟变长。
- 责任不清。
- 重复工作。
- 结果冲突。

## 面试高频问题

### Q1: Agent 和 Workflow 怎么选？

固定流程、强合规、高风险操作优先 workflow；开放探索、路径不确定可以用 Agent；成熟生产系统常是外层 workflow，局部节点 Agent 化。

### Q2: Agent 工具调用怎么防越权？

工具层独立做权限校验，模型不能绕过 RBAC/ABAC。高风险写操作需要 human-in-the-loop、幂等、审计和回滚。

### Q3: Agent 如何评测？

评估最终任务成功率，也评估轨迹：工具选择、参数、步骤数、错误恢复、成本、延迟和危险行为。

