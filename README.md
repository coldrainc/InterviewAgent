# Interview Agent

一个用于面试场景的 Agent 工程骨架，核心包含：

- `AgentLoop`：显式控制面试阶段、候选人回答、追问、换题和终止。
- `LangChainInterviewHarness`：用 LangChain 封装 LLM prompt、模型调用、Responses API 和降级逻辑。
- `HarnessGuardrails`：输入/输出护栏，覆盖密钥脱敏、评分标准防泄露、中文约束、长度控制和失败降级。
- `MarkdownKnowledgeBase`：加载本地 Markdown 面试资料，检索相关片段注入 prompt。
- `ScriptedInterviewHarness`：离线可测试 harness，不需要 API key。
- CLI：支持真实模型交互和本地 demo。

默认问答语言是中文。除非候选人明确要求英文或其他语言，面试官会用中文提问、澄清、追问和评价。

当前面试模式是简历驱动：可以在桌面端或 API 中提供候选人姓名、目标岗位、级别、简历摘要、完整简历、项目经历和面试目标。Agent 会把这些信息和 AI 知识库一起放入 Harness 上下文，优先围绕真实项目、本人职责、技术取舍、指标结果、评测上线和安全治理追问。

AgentLoop 会对每次正式回答做轻量质量判断：是否有本人职责、技术细节、量化指标、工程取舍、生产化信号。回答证据不足时会继续深挖当前方向；证据较充分或追问次数达到上限时，会给出阶段性判断并切换到其他重点。候选人的澄清问题，例如“什么是 RAG”，只会触发知识解释和答题辅导，不会推进面试轮次，也不会沉淀为历史记忆。

桌面端支持两种模式：

- `Agent 面试我`：Agent 作为面试官，基于简历、项目经历、AI 知识库和历史记忆追问你。
- `Agent 回答我`：你作为面试官提问，Agent 作为候选人，结合简历和互联网行业场景回答你的面试题。

行业选择当前暂时只开放 `互联网行业`，后续可以扩展到金融、教育、医疗、制造等行业。

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e "backend[dev]"
cp .env.example .env
```

离线 demo：

```bash
interview-agent demo
```

最简启动真实面试：

```bash
./interview
```

生产化本地开发推荐流程：

```bash
make install
make up
make migrate
make embedding-service
make index
make doctor
make eval-rag
make run
```

桌面端对话 UI：

```bash
make up
make migrate
make embedding-service
make api
npm --prefix apps/desktop install
make desktop
```

开启 API Token 鉴权后启动桌面端：

```bash
export INTERVIEW_API_AUTH_REQUIRED=true
export INTERVIEW_API_TOKENS=dev-token:default
export INTERVIEW_AGENT_API_TOKEN=dev-token
make api
make desktop
```

桌面端左侧可以导入 PDF / Markdown 简历，也可以手动粘贴简历和项目经历。上传后的简历会进入生产式存储：PostgreSQL 保存简历解析结果和元数据，MinIO 保存原始文件，相同文件按内容 hash 去重，不会每次重复保存；你可以上传多份简历，并选择当前使用哪一份。选择 `Agent 面试我` 后，第一题会从当前简历中最能体现 AI 工程深度的项目切入；选择 `Agent 回答我` 后，你可以直接输入面试题，Agent 会以当前简历对应的候选人身份回答。快捷卡片会作为本轮面试目标传入后端，不会被当成候选人的正式回答。

桌面端需要本地 API：

```text
http://127.0.0.1:8020
```

安全相关配置：

```text
INTERVIEW_API_AUTH_REQUIRED=true             # 生产建议开启
INTERVIEW_API_TOKENS=token-a:tenant_a        # token 到租户的映射
INTERVIEW_MAX_UPLOAD_BYTES=5242880           # 上传文件大小限制
INTERVIEW_MAX_MESSAGE_CHARS=8000             # 单条消息/大字段长度限制
INTERVIEW_RATE_LIMIT_PER_MINUTE=60           # 每租户每客户端分钟限流
INTERVIEW_STORE_UPLOAD_SOURCE_PATH=false     # 默认不保存用户本机路径
```

API 支持 `Authorization: Bearer <token>` 或 `X-API-Key: <token>`。未开启鉴权时使用 `INTERVIEW_DEFAULT_TENANT_ID`，便于本地开发；生产环境应开启鉴权并使用真实租户隔离。

账户和计费：

```text
POST /auth/register       # 邮箱注册，默认 2 次 Agent 生成试用
POST /auth/login          # 邮箱密码登录
GET  /account             # 查看试用次数和积分余额
POST /account/recharge    # 本地/后台模拟充值，生产要换成支付回调
GET  /metadata/models     # 查看可选模型和每百万 token 积分价格
```

`POST /sessions` 支持传入 `model_id`。试用用完后，系统会按输入/输出 token 和模型价格扣积分；没有真实 provider usage 时会使用本地 token 估算。详细方案见 [docs/billing-and-models.md](/Users/bytedance/Documents/InterViewAgent/docs/billing-and-models.md)。

生产级 RAG 推荐先构建持久化索引：

```bash
./interview index
./interview
```

构建 Hybrid RAG（BM25 + embedding 向量检索）：

```bash
./interview index --embeddings
./interview
```

生产学习模式默认使用 Docker Compose 启动三类基础设施：

```bash
make up
```

它会启动：

```text
PostgreSQL  localhost:5432  # 业务主库：简历、会话、轮次、记忆、知识库元数据
Qdrant      localhost:6333  # 向量库：RAG chunk 和后续 memory 向量
MinIO       localhost:9002  # 对象存储：上传的简历/文档原文件
```

数据库迁移：

```bash
make migrate
```

MinIO 控制台：

```text
http://localhost:9003
账号：interview_agent
密码：interview_agent_password
```

构建 Qdrant 向量索引：

```bash
./interview index --embeddings --vector-store qdrant
./interview
```

默认 Qdrant collection：

```text
interview_agent
```

自定义 Qdrant 地址和 collection：

```bash
./interview index --embeddings \
  --vector-store qdrant \
  --qdrant-url http://localhost:6333 \
  --qdrant-collection interview_agent_prod
```

索引完成后，工程会把当前向量库后端写入：

```text
.interview_agent/vector_store.json
```

运行 `./interview` 时会按这个配置自动连接 Qdrant；如果 Qdrant 不可用，会回退到本地 JSON 向量库或 BM25。

健康检查：

```bash
./interview doctor
```

RAG 检索回归评测：

```bash
./interview eval-rag
```

生产化 embedding 推荐拆成本地 EmbeddingService：

```bash
./interview embedding-service
./interview index --embeddings --embedding-provider service --vector-store qdrant
./interview
```

默认服务地址：

```text
http://127.0.0.1:8010
```

运行时配置会写入：

```json
{
  "embedding_provider": "service",
  "embedding_service_url": "http://127.0.0.1:8010"
}
```

默认 embedding provider 是本地模型：

```text
BAAI/bge-small-zh-v1.5
```

第一次构建向量索引会下载模型；之后运行面试时只从本地缓存加载模型，不依赖 Hugging Face 网络。也可以显式指定 provider：

```bash
./interview index --embeddings --embedding-provider local --embedding-download
./interview index --embeddings --embedding-provider openai --embedding-model text-embedding-3-small
```

如果模型已经缓存，推荐使用默认的离线缓存模式：

```bash
./interview index --embeddings
```

Hybrid RAG 实现细节：

```text
离线：
Markdown → 语义/标题切 chunk → tokens/BM25 统计 → embedding 向量化
       → .interview_agent/rag_index.json
       → .interview_agent/rag_vectors.json 或 Qdrant collection

在线：
query → query expansion → BM25 候选召回
      → query embedding → 向量库 Top-K
      → hybrid score = 0.55 * vector + 0.45 * BM25
      → MMR 去重 → Top-K context → prompt
```

如果没有构建向量索引，系统自动回退到 BM25 检索。

注意：本地 embedding 不需要 OpenAI/AIGW embedding 权限。当前 AIGW 聊天模型配置可用于面试问答；如果切到 `--embedding-provider openai` 后 embedding 请求返回鉴权或 provider 错误，命令会自动回退为 BM25 索引，不影响面试运行。

每次面试会默认保存：

```text
PostgreSQL interview_sessions           # 会话主记录和配置快照
PostgreSQL interview_turns              # 每轮面试官/候选人对话
PostgreSQL memory_items                 # 筛选后的可复用历史问答记忆
.interview_agent/conversations/*.jsonl  # 导出事件流，便于调试和阅读
.interview_agent/conversations/*.md     # 导出完整面试记录
.interview_agent/memory/*.md            # 导出可检索历史问答记忆
```

生产职责边界：

```text
PostgreSQL：业务事实数据，负责事务、一致性、查询、审计和迁移。
Qdrant：只放向量和 payload 引用，不作为业务主库。
MinIO/S3：只放原始文件和大对象，不把 PDF/Markdown 二进制塞进数据库。
Redis：后续可接入缓存、任务队列、限流和短期会话状态。
```

重新构建索引时，默认会把静态知识库和历史面试 memory 一起纳入索引：

```bash
./interview index
```

默认索引来源包括：

```text
knowledge_base/ai-interview-guide/docs
knowledge_base/github-ai-knowledge
.interview_agent/memory
```

只索引静态知识库：

```bash
./interview index --no-include-memory
```

它等价于：

```bash
.venv/bin/interview-agent run --config backend/examples/interview_config.json
```

默认启动会优先加载 `.interview_agent/rag_index.json` 持久化索引；如果索引不存在，才 fallback 到 Markdown 按需检索。默认不自动联网搜索，启动更快。需要联网搜索上下文时：

```bash
./interview --web-search
```

交互式离线面试：

```bash
interview-agent run --offline --config backend/examples/interview_config.json
```

终端命令：

```text
/kb RAG 检索优化        # 手动检索本地知识库，不推进面试
/search RAG 检索优化    # /kb 的兼容别名
搜索 AgentLoop          # 中文知识库搜索命令
/web RAG 最新优化       # 手动联网搜索，用于调试联网上下文
/transcript             # 查看当前面试记录
/help                   # 查看命令帮助
/quit                   # 退出
```

使用 OpenAI + LangChain：

```bash
export OPENAI_API_KEY=sk-your-key
interview-agent run --model gpt-4o-mini --config backend/examples/interview_config.json
```

## Codex Config

CLI 默认会读取 Codex 配置中的模型默认值：

```text
~/.codex/config.toml
.codex/config.toml
```

当前工程只复用这些模型调用相关字段：

```toml
model = "gpt-4o-mini"
openai_base_url = "https://api.openai.com/v1"
```

也支持 Codex 的 provider 配置形式：

```toml
model = "custom-model"
model_provider = "custom"

[model_providers.custom]
base_url = "https://custom.example/v1"
env_key = "CUSTOM_API_KEY"
```

这会让项目使用 `custom-model`、`https://custom.example/v1`，并从 `CUSTOM_API_KEY` 环境变量读取 API key。

如果 provider 是 `AIGW`，或 `base_url` 包含 `aigateway`，且没有显式配置 `env_key`，项目默认使用：

```bash
GATEWAY_API_KEY
```

优先级：

```text
--model > Codex config.toml > OPENAI_MODEL > gpt-4o-mini
```

注意：Codex 配置可以作为 provider 配置源，但 Codex 本身不是模型代理服务。Codex 的登录态不能直接当作普通 OpenAI API key 使用。本工程调用 LangChain/OpenAI SDK 时仍需要 `OPENAI_API_KEY`，或 provider 配置中 `env_key` 指向的环境变量。

关闭 Codex 配置读取：

```bash
interview-agent run --no-use-codex-config
```

## Knowledge Base

默认知识库目录：

```text
knowledge_base/ai-interview-guide/docs
```

该目录来自：

```text
https://github.com/guocong-bincai/ai-interview-guide
```

CLI 会自动配置这个目录作为知识库。生产推荐先运行 `./interview index` 生成持久化 RAG 索引；运行面试时只加载索引并在每轮面试生成时，按当前阶段、focus area 和候选人回答检索相关片段，作为 LangChain prompt 的上下文。

这就是项目里的默认 RAG 流程，不需要候选人手动输入 `/search` 才会触发。`/kb` 和 `/search` 只是给调试或临时查看知识库片段用。

联网搜索也可以作为 Harness 的自动上下文来源，默认开启：

```bash
interview-agent run --config backend/examples/interview_config.json --web-search
```

关闭联网搜索：

```bash
interview-agent run --config backend/examples/interview_config.json --no-web-search
```

联网搜索 provider 优先级：

```text
TAVILY_API_KEY > BRAVE_SEARCH_API_KEY > SEARXNG_URL > DuckDuckGo HTML fallback
```

使用自定义知识库：

```bash
interview-agent run --offline --knowledge-base path/to/docs
```

## Architecture

```text
Candidate input
    |
    v
AgentLoop
    |-- stores InterviewState
    |-- chooses next InterviewStage
    |-- decides termination
    v
InterviewHarness
    |-- LangChainInterviewHarness for LLM calls
    |-- ScriptedInterviewHarness for tests/offline demos
    v
Interviewer message / evaluation
```

## Project Layout

```text
backend/
  src/interview_agent/      # Python 后端包
    core/                   # 面试领域模型、AgentLoop、Harness、护栏
    rag/                    # 知识库、RAG index、向量库、RAG 评测
    embeddings/             # embedding 客户端和 EmbeddingService
    infrastructure/         # 配置、Codex provider、会话持久化、doctor、联网搜索
    interfaces/             # CLI、FastAPI、本地终端交互
  tests/                    # Python tests
  examples/                 # backend config examples
apps/
  desktop/                  # Electron 桌面端，独立 package.json / node_modules
scripts/
  interview                 # root wrapper
knowledge_base/             # Markdown knowledge sources
.interview_agent/           # local runtime data, ignored by git

backend/src/interview_agent/core/
  agent_loop.py     # loop controller
  config.py         # interview config and rubric models
  state.py          # transcript and turn state
  harness.py        # LangChain and scripted harnesses
  guardrails.py     # harness input/output safety checks
backend/src/interview_agent/rag/
  knowledge_base.py # local Markdown retrieval facade
  rag_index.py      # persistent BM25/vector hybrid index
  vector_store.py   # JSON and Qdrant vector stores
backend/src/interview_agent/interfaces/
  cli.py            # Typer CLI
  api.py            # FastAPI API for desktop clients
backend/examples/
  interview_config.json
knowledge_base/
  ai-interview-guide/docs/
backend/tests/
  test_agent_loop.py
  test_knowledge_base.py
```

## Tests

```bash
make test
```
