# Interview Agent Backend

Python 后端子工程，负责面试 Agent 的核心能力：

- AgentLoop / InterviewState
- LangChain Harness / Scripted Harness
- HarnessGuardrails
- RAG 索引、检索、评测
- EmbeddingService
- Qdrant / JSON 向量库适配
- 本地 FastAPI API
- CLI 命令和 Python 测试

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
