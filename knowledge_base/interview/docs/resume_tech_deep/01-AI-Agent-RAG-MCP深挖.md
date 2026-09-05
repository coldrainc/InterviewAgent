# AI Agent / RAG / MCP 深挖

## 1. 一句话定位

AI Agent 是能围绕目标进行规划、调用工具、观察结果并继续执行的系统；RAG 是用知识检索增强模型回答；MCP 是把外部工具和资源标准化暴露给模型调用的协议/框架思路。

面试里可以这样说：

> AI Agent 不是简单调一次大模型，而是“模型 + 工具 + 记忆 + 工作流 + 评测 + 安全边界”的工程系统。

## 2. Agent 基本架构

```text
User Goal
  -> Planner / Agent Loop
  -> Tool Selection
  -> Tool Execution
  -> Observation
  -> Memory / State Update
  -> Next Action
  -> Final Answer / Artifact
```

核心模块：

- Planner：拆任务。
- Executor：执行工具。
- Tool Registry：工具注册和 schema。
- Memory：短期上下文和长期记忆。
- RAG：知识检索。
- Guardrails：安全边界。
- Evaluator：评测结果质量。
- Sandbox：隔离执行代码或命令。

## 3. Agent Loop 原理

典型循环：

```text
Think
  -> Decide Action
  -> Call Tool
  -> Observe Result
  -> Update State
  -> Continue / Finish
```

工程里通常不会让模型无限循环，需要：

- 最大步数。
- 超时。
- 工具白名单。
- 失败重试上限。
- 中间状态记录。
- 人工确认门禁。

## 4. 工具调用设计

工具需要标准化描述：

```json
{
  "name": "search_doc",
  "description": "Search internal documents",
  "input_schema": {
    "query": "string"
  }
}
```

模型不是直接调用任意函数，而是在候选工具中选择，然后由系统执行。

工具设计重点：

- 输入 schema 清晰。
- 输出结构化。
- 错误码稳定。
- 不返回过多噪音。
- 对危险操作加确认。
- 可记录 trace。

## 5. MCP 原理

MCP 可以理解成“模型连接外部工具和资源的标准接口”。

```text
LLM Client
  -> MCP Server
  -> Tools / Resources / Prompts
  -> External System
```

MCP Server 可以暴露：

- Tool：可执行动作。
- Resource：可读取资源。
- Prompt：标准提示词模板。

价值：

- 工具接入标准化。
- 模型和工具解耦。
- 多工具可以复用同一套协议。
- 权限和审计更容易统一。

## 6. RAG 原理

RAG 的目标是让模型回答时基于外部知识，而不是只靠参数记忆。

基本链路：

```text
User Query
  -> Query Rewrite / Normalize
  -> Retrieve Documents
  -> Rerank
  -> Build Context
  -> LLM Generate
  -> Cite / Verify
```

常见检索方式：

- BM25：关键词匹配，适合精确词。
- Vector Search：语义召回，适合语义相近。
- Hybrid Search：BM25 + 向量召回组合。
- Rerank：对候选结果重新排序。

## 7. RAG 工程难点

### 数据切分

Chunk 太大：

- 噪音多。
- 命中不准。

Chunk 太小：

- 上下文缺失。
- 语义不完整。

### 检索召回

要解决：

- 关键词召回不到。
- 语义召回太泛。
- 版本过期。
- 多文档冲突。

### 防幻觉

需要：

- 引用来源。
- 不确定时拒答。
- 明确区分事实和推断。
- 对关键结论做二次验证。

## 8. Agent + RAG 结合

```text
Agent
  -> 判断需要知识
  -> RAG retrieve
  -> 获取证据
  -> 调工具验证
  -> 生成答案 / 方案
```

RAG 给 Agent 提供“知识证据”，工具调用给 Agent 提供“行动能力”。

例子：

- 先查文档。
- 再读代码。
- 再跑命令验证。
- 最后生成方案。

## 9. Sandbox 在 AI Agent 里的作用

Agent 会调用工具、跑代码、读文件，因此需要 sandbox 控制风险。

限制内容：

- 文件读写范围。
- 网络访问。
- 命令执行。
- token 访问。
- 进程创建。
- 输出敏感信息。

典型机制：

```text
Agent action
  -> policy check
  -> sandbox execute
  -> capture stdout / stderr / files
  -> return structured observation
```

## 10. 评测体系

Agent 系统必须评测，不然容易“看起来能用，实际不稳”。

评测维度：

- 任务完成率。
- 工具选择准确率。
- 检索命中率。
- 引用正确率。
- 幻觉率。
- 步数和耗时。
- 失败恢复能力。
- 安全边界命中率。

常见评测方式：

- 固定 benchmark。
- 人工标注对比。
- golden answer。
- trace 回放。
- A/B prompt 或策略。

## 11. Agent 状态机设计

Agent 不是一段 prompt，而是一个带状态的执行系统。真正工程化时，需要把 Agent Loop 显式建模成状态机。

```text
created
  -> planning
  -> tool_calling
  -> observing
  -> reflecting
  -> waiting_user
  -> completed
  -> failed
  -> canceled
```

每个状态都要有明确输入和输出：

- planning：把目标拆成可执行步骤。
- tool_calling：选择工具并生成结构化参数。
- observing：接收工具执行结果。
- reflecting：判断结果是否足够，是否需要修正计划。
- waiting_user：遇到高风险操作或缺少关键信息时等待确认。
- completed：产出最终答案或文件。
- failed：失败归因，给出可恢复路径。

状态机的价值：

- 避免模型无限循环。
- 支持中断和恢复。
- 支持 trace 回放。
- 支持任务可视化。
- 支持对每一步做评测。

面试里可以这样延伸：

> Agent 工程化的核心是把“模型思考”变成可观测、可控制、可恢复的状态机，而不是让模型自由发挥。

## 12. Planner / Executor 分层

复杂 Agent 通常会拆成 Planner 和 Executor。

```text
Planner
  -> 理解目标
  -> 拆分任务
  -> 选择策略
  -> 生成计划

Executor
  -> 按计划调用工具
  -> 收集结果
  -> 处理失败
  -> 回写状态
```

为什么要拆：

- Planner 关注“做什么”。
- Executor 关注“怎么做”。
- 计划可以被用户审阅。
- 执行可以被重试和回放。
- 失败时能定位是计划错还是工具错。

常见执行策略：

- ReAct：边思考边调用工具。
- Plan-and-Execute：先生成计划，再逐步执行。
- Reflection：执行后自检，必要时修正。
- Multi-Agent：不同角色分别负责检索、编码、审查、验证。

工程取舍：

- 简单任务用 ReAct，灵活但不可控。
- 高风险任务用 Plan-and-Execute，可审阅但成本更高。
- 质量要求高的任务加 Reflection 或 Reviewer。

## 13. Tool Schema 设计细节

Tool Schema 决定模型能不能稳定调用工具。Schema 写得含糊，模型就容易传错参数、调用错工具或重复调用。

好的 Tool Schema 需要包含：

- 工具名称：表达能力，不要太泛。
- description：说明何时用、何时不用。
- input schema：字段类型、必填、枚举、格式约束。
- output schema：结构稳定，方便模型继续推理。
- error schema：错误码稳定，可判断是否重试。
- side effect：是否会写文件、发消息、提交代码。
- confirmation policy：哪些操作必须用户确认。

示例：

```json
{
  "name": "create_document",
  "description": "Create a document from structured markdown. Use only after content is finalized.",
  "input_schema": {
    "title": "string",
    "markdown": "string",
    "folder_token": "string"
  },
  "side_effect": "creates_remote_document",
  "requires_confirmation": true
}
```

工具设计原则：

- 少给模型自由文本入口。
- 参数尽量枚举化。
- 输出保留关键证据，不返回整片噪音。
- 危险动作分两步：dry-run -> execute。
- 工具错误要可分类：权限、输入、外部依赖、超时、未知。

## 14. Tool Registry 与工具选择

Tool Registry 不是简单的函数列表，它承担工具发现、权限过滤和上下文裁剪。

```text
All Tools
  -> 根据任务筛选候选工具
  -> 根据权限过滤
  -> 根据上下文预算裁剪描述
  -> 提供给模型选择
```

为什么不能把所有工具都塞给模型：

- token 变大。
- 工具相似时容易选错。
- 高风险工具暴露过多。
- 模型会被不相关能力干扰。

更好的做法：

- 先做 intent routing。
- 只暴露当前任务相关工具。
- 对写操作默认隐藏执行入口，只暴露检查入口。
- 对高风险工具加 confirmation。

工具选择失败的常见原因：

- 工具描述过泛。
- 多个工具能力重叠。
- 输入字段含义不清。
- 工具输出不可解释。
- 没有把失败条件写进 description。

## 15. MCP Server 生命周期

MCP 可以把工具、资源、Prompt 以统一协议暴露给模型客户端。工程上可以把它看成 Agent 和外部系统之间的标准适配层。

```text
Client
  -> discover capabilities
  -> list tools/resources/prompts
  -> call tool / read resource
  -> receive structured result
```

MCP Server 设计关注：

- 初始化：声明 server 能力。
- 工具注册：暴露可执行动作。
- 资源注册：暴露可读取上下文。
- Prompt 注册：暴露可复用任务模板。
- 权限：控制哪些资源和工具可访问。
- 审计：记录谁调用了什么。
- 错误：返回稳定错误结构。

MCP 的价值不是“多一种调用方式”，而是把上下文和工具标准化：

- 文档、代码、数据库、浏览器都可以用统一抽象接入。
- Agent 不需要知道每个系统的私有 API。
- 工具可以被多个 Agent 客户端复用。
- 权限和审计可以集中治理。

## 16. MCP Tool / Resource / Prompt 的边界

MCP 三类能力要分清楚：

```text
Tool
  -> 做动作
  -> 有副作用或计算结果

Resource
  -> 读上下文
  -> 只读、可引用、可缓存

Prompt
  -> 标准任务模板
  -> 指导模型如何处理某类任务
```

例子：

- Tool：创建文档、查询数据库、运行测试、发送消息。
- Resource：读取代码文件、读取设计文档、读取任务详情。
- Prompt：代码评审模板、需求分析模板、故障排查模板。

边界设计不清会导致：

- 读取动作被实现成写工具，权限过大。
- Prompt 写死业务逻辑，难以复用。
- Resource 输出太长，污染上下文。
- Tool 既读又写，难以审计。

更好的设计是：

```text
先 Resource 取证
再 Prompt 约束推理
最后 Tool 执行动作
```

## 17. RAG 数据治理

RAG 的效果首先取决于知识库质量。模型生成不好，很多时候不是模型问题，而是数据源混乱。

数据治理要处理：

- 文档来源。
- 文档版本。
- 更新时间。
- owner。
- 权限。
- 适用范围。
- 过期策略。
- 冲突关系。

知识条目最好带 metadata：

```text
doc_id
title
source_url
owner
updated_at
version
domain
permission_level
chunk_id
section_path
```

这些 metadata 的用途：

- 检索时按领域过滤。
- 回答时引用来源。
- 多版本冲突时优先新文档。
- 权限不足时拒绝返回。
- 排查错误回答时定位具体 chunk。

## 18. Chunking 设计

Chunking 是 RAG 最容易被低估的部分。切得不好，后续 embedding、召回、rerank 都会被拖垮。

常见策略：

- 固定长度切分。
- 按标题层级切分。
- 按语义段落切分。
- 按代码函数 / 类切分。
- 父子 chunk：小 chunk 召回，大 chunk 补上下文。

不同资料适合不同策略：

- 文档：按标题层级切。
- API 文档：按接口粒度切。
- 代码：按类、函数、文件结构切。
- FAQ：按问答对切。
- 日志：按时间窗口和 traceId 切。

关键参数：

- chunk size。
- overlap。
- metadata。
- section path。
- parent document。

面试可以说：

> Chunk 不是越小越好。小 chunk 召回精准但容易丢上下文，大 chunk 语义完整但噪音多。工程上常用小 chunk 召回，再回填父级上下文。

## 19. Embedding / BM25 / Hybrid Search

检索不是只有向量库。

BM25 优点：

- 精确关键词强。
- 类名、函数名、错误码、配置 key 命中好。
- 可解释性强。

BM25 缺点：

- 同义表达召回弱。
- 口语化 query 容易漏。

Vector Search 优点：

- 语义召回好。
- 适合自然语言问题。
- 能找到表达不同但含义接近的内容。

Vector Search 缺点：

- 对精确 token 不稳定。
- 容易召回泛化内容。
- 对过短 query 效果差。

Hybrid Search 的核心是组合：

```text
Query
  -> BM25 candidates
  -> Vector candidates
  -> merge / deduplicate
  -> rerank
  -> topK context
```

直播/客户端/工程知识场景里，Hybrid 通常更稳，因为既有业务词，也有代码符号、错误码、文件路径。

## 20. Rerank 和上下文构造

召回只是第一步，真正进入模型上下文前还要 rerank 和 context packing。

Rerank 要判断：

- 是否回答了 query。
- 是否属于正确业务域。
- 是否版本最新。
- 是否包含可引用证据。
- 是否和其他结果冲突。

Context 构造要注意：

- 先放最相关证据。
- 保留标题路径和来源。
- 同类重复内容去重。
- 冲突内容标记出来。
- 不把低置信内容伪装成事实。

推荐结构：

```text
Evidence 1
  source
  section
  content
  confidence

Evidence 2
  source
  section
  content
  confidence

Known conflicts
  old doc says A
  new doc says B
```

这样模型回答时更容易遵守证据边界。

## 21. 防幻觉与引用校验

RAG 不是天然防幻觉。只有把“证据边界”做进链路，才能降低错误回答。

关键机制：

- 强制引用来源。
- 事实必须来自 retrieved context。
- 推断和事实分开写。
- 低置信时拒答或提示不确定。
- 对关键结论二次检索。
- 对代码类问题优先读源码而不是只信文档。

回答生成后还可以做校验：

```text
Generated Answer
  -> extract claims
  -> match claims to evidence
  -> unsupported claims flagged
  -> revise answer
```

常见失败：

- 文档过期但模型照答。
- 检索结果只相关不充分。
- 模型把经验判断写成事实。
- 引用了 A 文档却回答了 B 结论。

面试表达：

> RAG 防幻觉不是靠“把文档塞进去”，而是靠检索、rerank、引用、claim verify 和拒答策略共同保证。

## 22. Memory 设计

Agent Memory 分短期和长期。

短期记忆：

- 当前任务目标。
- 已执行步骤。
- 工具结果。
- 用户最新指令。
- 当前 plan。

长期记忆：

- 用户偏好。
- 项目规范。
- 历史决策。
- 常见问题。
- 业务知识。

Memory 风险：

- 过期信息污染当前任务。
- 隐私和敏感信息被保存。
- 记忆和实时证据冲突。
- 记忆过多导致上下文噪音。

治理方式：

- 写入门禁，只保存长期有价值信息。
- 标记来源和更新时间。
- 任务内事实优先于长期记忆。
- 关键结论重新取证。
- 支持删除和更正。

## 23. 权限、安全和审计

Agent 能调用工具后，就必须按“有副作用系统”设计。

风险动作包括：

- 写文件。
- 删除文件。
- 提交代码。
- 发消息。
- 创建远端文档。
- 调数据库。
- 执行 shell。
- 访问密钥。

安全策略：

- tool allowlist。
- workspace sandbox。
- read / write 分权。
- dry-run。
- 用户确认。
- token 最小权限。
- 敏感信息脱敏。
- 操作审计。

审计日志应该记录：

```text
who
when
goal
tool
input summary
output summary
side effect
approval
traceId
```

面试可以强调：

> Agent 平台不是让模型权限越大越好，而是让模型在可控权限内完成任务。越接近生产系统，越需要审计和确认门禁。

## 24. 评测与 Trace 体系

Agent 评测要看完整任务链路，而不是只看最终回答像不像。

评测维度：

- 任务完成率。
- 首次成功率。
- 平均工具调用步数。
- 工具选择准确率。
- 参数正确率。
- 检索召回率。
- 引用支持率。
- 幻觉率。
- 用户确认次数。
- 失败恢复率。
- 平均耗时。

Trace 需要记录：

```text
goal
plan
each action
tool input
tool output
model decision
error
retry
final artifact
```

有了 Trace 才能回答：

- 为什么调用这个工具。
- 哪一步失败。
- 是检索没召回，还是模型理解错。
- 是工具报错，还是参数不对。
- prompt 改动有没有提升。

评测集设计：

- 简单任务：一两步工具调用。
- 长链路任务：规划、读取、修改、验证。
- 失败任务：权限不足、文件不存在、接口超时。
- 安全任务：高风险写操作必须确认。
- 反事实任务：没有证据时必须拒答。

## 25. 可延伸技术点

这些点适合作为面试追问：

- Agent 和 Workflow 的区别是什么。
- ReAct 和 Plan-and-Execute 怎么选。
- Tool schema 为什么会影响 Agent 稳定性。
- MCP 相比普通 HTTP API 的价值是什么。
- Tool、Resource、Prompt 的边界怎么划。
- RAG 为什么要 Hybrid Search。
- Chunk 太大或太小分别有什么问题。
- Rerank 在 RAG 里解决什么问题。
- 如何判断一个回答是否被证据支持。
- Memory 如何避免污染当前任务。
- Agent 调 shell 或写文件时如何做安全控制。
- 如何设计 Agent benchmark 和 trace 回放。

## 26. 面试口径

如果问 Agent 和普通 LLM 调用区别：

> 普通 LLM 调用是一次问答，Agent 是带状态的任务执行系统。它会规划步骤、调用工具、观察结果、更新状态，再决定下一步。工程重点是工具 schema、状态管理、失败恢复、权限边界和评测。

如果问 RAG 难点：

> RAG 难点不是接一个向量库，而是数据怎么切、怎么召回、怎么 rerank、怎么引用和防幻觉。尤其内部知识库经常有过期和冲突信息，所以需要证据来源和二次验证。

如果问 MCP 的价值：

> MCP 的价值是把工具和资源标准化暴露给模型。模型不直接依赖具体系统，而是通过统一协议发现工具、读取资源、调用能力，这样工具接入、权限和审计都更清楚。

如果结合你的经历讲：

> 我做 AI Agent 平台时，关注的不只是 prompt，而是 Runtime、Sandbox、MCP 工具调用、RAG 知识库、评测和工作流闭环。目标是让 Agent 真正能稳定执行任务，而不是只生成一段看起来合理的回答。
