# 生产级 RAG 要求

## 行业要求概览

生产级 RAG 需要解决的不只是“向量检索 + 大模型回答”，还包括：

- 数据解析质量。
- 增量更新。
- 多租户和权限。
- 检索效果评测。
- 引用和可解释性。
- 延迟和成本。
- 幻觉和拒答。
- 监控和回滚。

## 数据 ingestion 要求

### 1. Document Schema

每个文档应标准化为：

```text
document_id
source_uri
title
content
mime_type
owner
tenant_id
acl
created_at
updated_at
version
content_hash
metadata
```

### 2. Chunk Schema

每个 chunk 至少包含：

```text
chunk_id
document_id
parent_id
section_path
text
start_offset
end_offset
token_count
acl
version
embedding_model
content_hash
```

### 3. 解析质量

重点处理：

- PDF 段落错乱。
- 表格丢表头。
- 图片 OCR。
- 代码块和日志。
- Markdown 标题层级。
- HTML 导航和广告噪音。

面试追问：

- PDF 表格解析错了怎么发现？
- OCR 内容置信度低怎么办？
- 文档解析失败是否阻塞索引构建？

## 检索架构要求

推荐多路召回：

```text
query
  -> query rewrite / expansion
  -> BM25 sparse retrieval
  -> dense vector retrieval
  -> metadata filter
  -> rerank
  -> diversity / MMR
  -> context packing
  -> answer generation
```

不同场景：

- 专有名词、错误码、API 名称：BM25 往往更有效。
- 语义相似、同义表达：向量检索更有效。
- 多跳问题：需要 query decomposition。
- 长文档：parent-child retrieval。
- 个性化：结合用户历史和权限。

## 权限和多租户

生产 RAG 的权限要求非常关键：

- 检索前 filter：减少无权限 chunk 进入候选。
- 检索后 filter：兜底防泄漏。
- reranker 和 LLM 不能接触无权限内容。
- cache key 包含 tenant_id、user_id 或 role、ACL version。
- 权限变更触发索引 metadata 更新或重建。

面试追问：

- 只在生成答案前过滤为什么不够？
- 多租户共 collection 和独立 collection 怎么选？
- 权限变更后旧缓存怎么失效？

## 增量更新

增量更新要求：

- 监听数据源变更。
- 用 content_hash 判断内容变化。
- 更新 chunk 和 embedding。
- 删除旧 chunk。
- 保留索引版本。
- 支持失败回滚。

更稳妥的方式：

```text
build staging index
  -> validate chunk count / sample retrieval / ACL
  -> switch alias
  -> keep previous version
```

## 幻觉控制

RAG 幻觉常见原因：

- 没有召回答案。
- 召回了错误上下文。
- 上下文被截断。
- 模型没有遵循上下文。
- 引用和答案没有绑定。

控制手段：

- 无证据拒答。
- 答案句子级引用。
- 生成后 groundedness check。
- context compression 保留关键证据。
- 高风险业务使用 extractive answer。

## 面试高频问题

### Q1: RAG 系统怎样从 demo 走向生产？

需要补齐 ingestion、权限、评测、观测、增量更新、缓存、灰度和回滚。

### Q2: 为什么 hybrid search 比单纯向量检索更稳？

因为真实查询既有语义问题，也有精确词匹配问题。错误码、产品名、函数名、政策编号经常依赖 sparse retrieval。

### Q3: RAG 线上答错了怎么定位？

按链路看：文档是否存在、解析是否正确、chunk 是否合理、召回是否命中、rerank 是否保留、prompt 是否包含、模型是否 grounded。

