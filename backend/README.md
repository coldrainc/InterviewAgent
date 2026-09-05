# Interview Agent Backend

Python 后端子工程，负责面试 Agent 的核心能力：

- AgentLoop / InterviewState / LangGraph 编排
- LangChain Harness / Scripted Harness
- HarnessGuardrails
- RAG 索引、检索、评测
- EmbeddingService
- Qdrant / JSON 向量库适配
- 本地 FastAPI API
- CLI 命令和 Python 测试
- 刷题训练题库、力扣算法样题、样题初始化、答题评分和解析反馈接口

LangChain 负责模型 provider、prompt、RAG 上下文和流式生成封装；LangGraph 负责面试轮次的生产级 loop 编排，包括条件路由、checkpoint、节点事件、短回答/澄清问题分支和显式循环降级。

## Install

从仓库根目录安装：

```bash
.venv/bin/python -m pip install -e "backend[dev]"
```

也可以直接使用根目录封装：

```bash
make install
```

## Test

```bash
cd backend
../.venv/bin/python -m pytest
```

或从根目录运行：

```bash
make test
```

本地离线 E2E：

```bash
make install
make test-e2e-local
```

该测试使用内存 SQLite、本地对象存储和离线 Scripted harness，覆盖注册、简历上传、创建面试 session、发送回答、LangGraph/显式 loop orchestration 元数据和持久化恢复，不需要真实模型 API key。

## Layout

```text
backend/
  pyproject.toml
  examples/
    interview_config.json
  src/interview_agent/
    core/
      agent_loop.py
      config.py
      state.py
      harness.py
      guardrails.py
    rag/
      knowledge_base.py
      rag_index.py
      vector_store.py
      rag_eval.py
    embeddings/
      embedding.py
      embedding_service.py
    infrastructure/
      settings.py
      codex_config.py
      conversation_store.py
      doctor.py
      web_search.py
    interfaces/
      cli.py
      api.py
      terminal.py
  tests/
```
