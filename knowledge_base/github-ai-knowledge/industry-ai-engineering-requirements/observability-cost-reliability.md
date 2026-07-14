# AI 可观测性、成本与可靠性要求

## 可观测性为什么更复杂

传统服务看 QPS、延迟、错误率还不够。AI 系统还要知道：

- 模型为什么这样回答。
- 检索到了什么。
- prompt 是哪个版本。
- 工具调用了什么。
- token 花了多少。
- 是否命中缓存。
- 是否触发 guardrail。
- 用户是否满意。

## Trace 字段建议

### 通用字段

```text
trace_id
request_id
user_id_hash
tenant_id
feature_name
environment
prompt_id
prompt_version
model_provider
model_name
model_version
input_tokens
output_tokens
cost
latency_ms
status
error_type
```

### RAG 字段

```text
query
rewritten_query
retriever_type
top_k
retrieved_sources
retrieval_scores
rerank_scores
context_token_count
knowledge_base_version
vector_index_version
```

### Agent 字段

```text
agent_id
workflow_id
step_index
tool_name
tool_args_hash
tool_latency_ms
tool_status
retry_count
approval_required
approval_status
final_task_status
```

## 成本治理

成本归因维度：

- feature。
- user / tenant。
- model。
- prompt version。
- retriever strategy。
- tool。
- cache hit / miss。

常见优化：

- prompt 压缩。
- history summary。
- RAG top_k 控制。
- rerank 候选控制。
- 小模型路由。
- semantic cache。
- batch。
- 异步任务。

## 可靠性设计

### 超时

每一段都要有 timeout：

- embedding。
- vector search。
- reranker。
- model call。
- tool call。
- output validation。

### 降级

降级策略：

- RAG 向量库失败，回退 BM25。
- reranker 超时，使用 hybrid score。
- 大模型失败，切小模型或返回保守答案。
- 工具失败，提示用户并保留任务状态。
- 生成失败，返回结构化错误而不是空白。

### 熔断

当 provider 错误率或延迟超过阈值：

- 暂停流量。
- 切换 provider。
- 降低并发。
- 关闭高成本功能。

## 事故复盘

AI 事故复盘需要包含：

- 触发输入。
- 检索上下文。
- prompt / model / tool 版本。
- 输出内容。
- guardrail 是否触发。
- 用户影响范围。
- 根因分类。
- 修复措施。
- 新增 eval case。

根因分类示例：

- retrieval failure。
- stale index。
- prompt regression。
- model regression。
- tool permission bug。
- schema validation missing。
- unsafe output。
- latency timeout。

## 面试高频问题

### Q1: 用户说 AI 答错了，你怎么定位？

先看 trace：输入、检索、rerank、prompt、模型输出、后处理、guardrail、反馈。没有 trace 很难定位。

### Q2: 如何把 P95 延迟降下来？

先拆分耗时，再针对瓶颈优化。常见方法是并发召回、减少上下文、缓存 embedding、降低 rerank 候选数、使用流式输出、模型路由。

### Q3: 如何降低 token 成本？

减少输入最有效。不要把全量历史和过多 chunk 塞进 prompt。使用摘要、检索式 memory、上下文压缩和小模型路由。

