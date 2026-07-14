# Production Storage Architecture

Interview Agent 的生产式存储按职责拆分，而不是把所有数据塞进一个地方。

## 组件分工

| 组件 | 职责 | 当前实现 |
| --- | --- | --- |
| PostgreSQL | 业务主库，保存简历解析结果、面试会话、轮次、记忆、知识库元数据 | SQLAlchemy Async ORM + Alembic |
| Qdrant | 向量库，只保存向量和可回查的 payload 引用 | `interview_agent.rag.vector_store` |
| MinIO / S3 | 原始文件对象存储，保存上传的 PDF / Markdown / 后续知识文档 | `ObjectStorage` 抽象 |
| 本地 Markdown/JSONL | 调试和人工阅读导出，不再作为生产主存储 | `ConversationStore` export |

## 表设计

### `resumes`

保存简历的解析结果和文件元数据。

- `content_hash`：按文件内容 sha256 去重。
- `summary` / `text`：解析后的文本，用于面试上下文。
- `object_bucket` / `object_key`：指向 MinIO/S3 中的原始文件。
- `metadata_json`：解析器版本、content type 等可扩展信息。

### `interview_sessions`

保存一次面试会话的主记录。

- `config_json`：面试配置快照，避免后续配置变化影响历史回放。
- `state_json`：AgentLoop 当前状态快照。
- `resume_id`：关联当前使用的简历。
- `mode` / `industry`：支持后续多模式、多行业扩展。

### `interview_turns`

保存每一轮问答。

- `turn_index`：会话内顺序。
- `stage`：intro / questioning / follow_up / evaluation。
- `interviewer` / `candidate`：面试官问题和候选人回答。
- `guardrails_json` / `fallback_used`：Harness 护栏和降级记录。

### `memory_items`

保存经过过滤的可复用历史问答记忆。

低价值回答，例如“不会”“不知道”“继续”“什么是 RAG”，不会写入 memory。
有效回答会被保存为可检索内容，后续可进入 RAG 索引或向量化到 Qdrant。

### `knowledge_documents` / `rag_chunks`

用于后续把知识库索引也纳入数据库管理。

当前 RAG 索引仍使用已有 Markdown indexer 和 Qdrant collection；这两张表已经预留好生产级 metadata 管理边界。

## 写入链路

### 简历上传

```text
Desktop/Electron
  -> POST /resumes
  -> ResumeService
  -> resume_parser
  -> MinIO.put_object(original file)
  -> PostgreSQL.resumes(upsert by content_hash)
```

### 面试会话

```text
POST /sessions
  -> AgentLoop.start()
  -> InterviewPersistenceService
  -> PostgreSQL.interview_sessions
  -> PostgreSQL.interview_turns
  -> Markdown/JSONL export
```

### 每轮对话

```text
POST /sessions/{id}/messages
  -> AgentLoop.step()
  -> memory_decision()
  -> PostgreSQL.interview_turns
  -> PostgreSQL.memory_items(only valuable answers)
  -> Markdown/JSONL export
```

## 为什么 Qdrant 不做主库

Qdrant 适合相似度检索，但不适合作为业务事实主库。

业务主库需要事务、外键、审计、复杂查询、迁移和一致性约束；这些由 PostgreSQL 负责。
Qdrant payload 只放最小必要引用，例如 `chunk_id`、`document_id`、`memory_item_id`，检索命中后再回 PostgreSQL 查业务数据。

## 本地生产栈

```bash
make up
make migrate
make api
```

如果本机没有 Docker Compose，`make up` 会回退到 `docker run` 启动：

- `interview-agent-postgres`
- `interview-agent-qdrant`
- `interview-agent-minio`

MinIO 使用 `9002/9003`，避免和本机已有服务占用的 `9000/9001` 冲突。

## 后续生产演进

1. 增加用户表和租户权限，把当前默认 `tenant_id=default` 升级为真实用户隔离。
2. 把 `knowledge_documents` / `rag_chunks` 接入索引器，统一管理知识库自动更新。
3. 给 `memory_items` 增加异步 embedding 任务，写入 Qdrant 并保存 `vector_point_id`。
4. 引入 Redis 做 API 限流、短期会话缓存和后台任务队列。
5. 增加 OpenTelemetry trace，记录 AgentLoop、RAG、LLM、Guardrails 的全链路耗时和失败原因。
