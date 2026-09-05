# Workflow Agent Harness — 生产级代码

> 相对于 demos/workflow-harness 的演示骨架，这里增加：
> - FastAPI 真实服务（CRUD + Run 触发 + 报告查询 + 鉴权 RBAC）
> - MongoDB 真实持久化（motor 异步驱动 + Pydantic 模型映射）
> - LangGraph AgentExecutor 实现（直接接 LangGraph 图，支持 checkpointing）
> - OpenTelemetry 全链路采集（Python SDK + FastAPI middleware）
> - Prometheus 自定义指标
> - 生产 Dockerfile + docker-compose 本地一键拉起整套依赖
> - 集成测试（pytest + testcontainers-mongodb）

## 目录

```
app/
├── main.py                 # FastAPI app 入口、路由注册、中间件、启动钩子
├── config.py               # 环境变量配置（Pydantic Settings）
├── security.py             # JWT + SSO OIDC 登录 / RBAC 中间件 / 审计日志
├── models/mongo.py         # Mongo 文档模型（ScenarioDoc/RunDoc/BaselineDoc/AnalyzerFindingDoc）
├── repos/
│   ├── scenario_repo.py    # Scenario CRUD + 分页查询
│   ├── run_repo.py         # Run 写入 / 状态机 / 指标聚合查询
│   └── baseline_repo.py    # Baseline 读写 / 版本历史
├── services/
│   ├── run_manager.py      # 触发 run / 检查超时 / 重试
│   ├── gate_service.py     # 门禁决策 + Baseline 比较
│   └── report_service.py   # HTML / JSON 报告生成
├── executors/
│   ├── langgraph_executor.py  # AgentExecutor：LangGraph 真实接入
│   └── llm.py              # LiteLLM Proxy 封装（多模型 fallback）
├── telemetry/
│   ├── otel.py             # OTel SDK 初始化 + FastAPI 追踪中间件
│   └── metrics.py          # Prometheus 指标定义 + ASGI 中间件
├── tasks/
│   ├── runner_worker.py    # Celery worker：消费 run 任务，调用 AgentExecutor + 写 Mongo
│   └── analyzer_worker.py  # Celery worker：消费完成 run，跑 analyzers + LLM Judge
└── scripts/
    └── seed_scenarios.py   # 初始化 Scenario（首次部署）

infra/
├── docker-compose.yml      # 本地依赖：Mongo + Redis + Kafka + OTel + Prometheus + Grafana
├── Dockerfile              # Harness API 生产镜像
├── Dockerfile.worker       # Celery Worker 镜像
├── k8s/                    # K8s 部署：Namespace/Deployment/HPA/Kafka Topic/Ingress
├── ci/                     # GitHub Actions：CI 门禁 / Nightly / Release
└── grafana/dashboard.json  # Harness 核心指标看板
```

## 本地启动

```bash
cd demos/workflow-harness-production
# 1. 拉起依赖
docker compose -f infra/docker-compose.yml up -d
# 2. 初始化虚拟环境与依赖
poetry install
# 3. 初始化 scenario 数据（从 demos/workflow-harness/scenarios 导入）
poetry run python -m app.scripts.seed_scenarios
# 4. 启动 API + Worker
poetry run uvicorn app.main:app --reload --port 8000
# 另一个终端
poetry run celery -A app.tasks.runner_worker.celery_app worker -Q run_queue -c 4 -l INFO
```
