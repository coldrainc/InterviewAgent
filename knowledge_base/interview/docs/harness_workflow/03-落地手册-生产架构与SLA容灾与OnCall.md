# Workflow Agent Harness 生产落地手册

> 面向商业生产环境的端到端落地方案。覆盖：架构选型、容量规划、SLA、多活容灾、安全合规、灰度发布、监控告警、OnCall 机制、CI/CD、K8s 部署、30/60/90 天迁移计划、风险应对。
> 本文档与「AI-Native 全栈工作流优化方案与 Harness 设计.md」互补：方案文档讲"为什么 + 怎么设计"，本手册讲"怎么上线 + 怎么运维"。

---

## 一、生产架构（目标态）

### 1.1 架构总览

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  接入层（高可用）                                                                 │
│  CDN + WAF + SLB（阿里云/华为云/AWS ALB）→ 多可用区 K8s Ingress(Nginx/Traefik)  │
├────────────────────────────────────────────────────────────────────────────────┤
│  服务层（Harness + Workflow Agent，微服务拆分）                                    │
│                                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────┐   ┌────────────────┐ │
│  │ Harness API  │   │ Agent Runner │   │ Analyzer       │   │ Golden Data    │ │
│  │ (FastAPI)    │   │ (LangGraph)  │   │ Worker(Celery) │   │ Pipeline       │ │
│  │ 网关/鉴权     │   │ Agent 执行    │   │ 失败模式诊断     │   │ 工单→用例生产   │ │
│  └──────┬───────┘   └──────┬───────┘   └────────┬───────┘   └───────┬────────┘ │
│         │                  │                    │                    │          │
├─────────┼──────────────────┼────────────────────┼────────────────────┼──────────┤
│  中间件层（生产选型）       │                    │                    │          │
│  ┌─────────┐ ┌─────────┐ ┌▼─────────────────────▼─┐ ┌─────────────┐ │          │
│  │ Redis   │ │ Kafka   │ │ MongoDB 副本集 (3节点)   │ │ TOS/S3 对象 │ │          │
│  │ 集群    │ │ 集群    │ │ - scenario/metrics      │ │ (trace dump  │ │          │
│  │ 缓存/锁 │ │ 异步队列│ │ - baselines/runs        │ │  长期归档)   │ │          │
│  └─────────┘ └────┬────┘ │ - analyzer_findings    │ └─────────────┘ │          │
│                   │      └────────────────────────┘                  │          │
│                   │                                                   │          │
│  ┌──────────┐ ┌────▼─────┐  ┌───────────────────────┐  ┌────────────▼───────┐   │
│  │OTel Col. │ │ Promethe │  │ Grafana + Alertmanager │  │ Elasticsearch      │   │
│  │ 链路采集  │ │ 指标     │  │ 看板 + 告警            │  │ (Trace/Log全文检)  │   │
│  └────┬─────┘ └────┬─────┘  └───────────────────────┘  └────────────────────┘   │
└───────┼───────────┼──────────────────────────────────────────────────────────────┘
        │           │
        ▼           ▼
   Jaeger /      长存储
   SkyWalking    (VictoriaMetrics)
```

### 1.2 微服务拆分与职责

| 服务 | 职责 | 部署形态 | 核心依赖 |
|---|---|---|---|
| **Harness API** | Scenario CRUD、Run 触发、报告查询、门禁判定、鉴权、限流 | K8s Deployment，HPA | Mongo、Redis、Kafka |
| **Agent Runner** | 拉取 scenario run 任务、调用 LangGraph/自研 Workflow Runtime、采 trajectory、写 Mongo | K8s Job / Celery Worker | Mongo、MCP Skill 服务、LLM API |
| **Analyzer Worker** | 消费已完成 run 的 trajectory，跑 analyzers + LLM-Judge（异步） | Celery Worker | Mongo、LLM API |
| **Golden Data Pipeline** | 定时从工单/PR/评论抽取候选，用 LLM 合成 scenario 候选，进入人工评审 | Airflow DAG / 定时 Job | Mongo、Confluence/飞书 API、LLM API |

### 1.3 技术选型矩阵（经过生产验证）

| 领域 | 选项 | 为什么选它 | 替代方案 |
|---|---|---|---|
| **后端框架** | FastAPI + Pydantic v2 | 类型严格、async 原生、OpenAPI 自动生成、团队 TS/Py 栈友好 | NestJS（若团队偏 TS） |
| **Agent 编排** | LangGraph | 状态机 + checkpointing + 可视化回放，社区成熟；自研 Runtime 可包成 GraphNode | 纯自研（复杂度过高，不推荐首阶段） |
| **任务队列** | Celery + Redis Broker / Kafka | Celery 生态成熟，重试/死信/并发开箱即用；Kafka 吞吐更高，选依赖团队经验 | RabbitMQ |
| **存储 - 业务数据** | **MongoDB 4.4+ 三节点副本集** | 文档型正好适配 Scenario/Trajectory 变结构 schema，和你简历中已有技术栈一致 | PostgreSQL + JSONB（强一致要求高用它） |
| **存储 - Trace 长归档** | 对象存储（TOS/S3/OSS）按天分区 + Parquet | 成本低、量大、支持 Presto/Spark 离线分析 | Elasticsearch（成本高但全文检索强） |
| **Trace 采集** | OpenTelemetry SDK（Python）+ OTel Collector + Jaeger/SkyWalking | 业界标准，跨语言、跨服务全链路可串 | Zipkin（偏老） |
| **指标** | Prometheus + VictoriaMetrics（长存）+ Grafana | 云原生标配，VM 比 Prometheus 自带 TSDB 存得久、省成本 | InfluxDB |
| **日志** | Filebeat → Kafka → Logstash → Elasticsearch + Kibana | 经典 EFK，业务检索 + 排障分析一体 | Loki（更轻、弱全文） |
| **CI/CD** | GitHub Actions（代码托管）/ GitLab CI → ArgoCD → K8s | GitOps，审计可追溯；ArgoCD 自动同步镜像 | Jenkins（历史包袱重） |
| **容器编排** | 自建 K8s（1.28+）或 云厂商托管（ACK/EKS/CCE） | 生产级事实标准 | Nomad（小众） |
| **配置/密钥** | Kubernetes Secret + Vault（或云 KMS） | 密钥不上代码仓、定期轮转 | 云 Secret Manager |
| **LLM 访问** | LLM Gateway（如 LiteLLM Proxy）+ 多模型 fallback | 统一鉴权、限流、降级、成本控制；多模型容灾（主模型挂了切备份） | 直连 API |

---

## 二、容量规划 & 成本估算（按中等团队）

### 2.1 假设（可按你团队替换）

- 注册 scenario：500 条
- 日 PR 门禁 runs：每 PR 触发 20 条 smoke × 20 PR/天 = **400 runs/天**
- Nightly runs：500 条全量 × 1 = **500 runs/天**
- 平均 run：5 步 × 2k tokens/step = **10k tokens/run**；耗时 30s；工具调用 3 次
- LLM 模型：主 = deepseek-chat / qwen-plus（¥0.002~0.004 / 1k tokens），备用 = gpt-4o-mini
- 团队规模：15 研发 + 2 SRE

### 2.2 资源需求

| 资源 | 规格 | 节点数 | 说明 |
|---|---|---|---|
| Harness API | 4C8G Pod | 2 + HPA(max=6) | P99 < 200ms |
| Agent Runner Worker | 8C16G Pod（并发 4 worker × 2） | 4 + KEDA 扩缩 | 占 CPU 最多，GPU 可选 |
| Analyzer Worker | 4C8G Pod | 2 | 低优先级队列，可容忍延迟 |
| MongoDB | 8C32G × 3 副本集 | 3 | 200G SSD，WiredTiger cache |
| Redis | 4C8G 哨兵集群 | 3 | 缓存 + 锁 + Celery broker |
| Kafka | 4C16G × 3 Broker | 3 | 保留 7 天 Topic |
| Prometheus + VM | 4C16G | 2 | 保留 90 天指标 |
| ES + Kibana | 8C32G × 3 Data + 3 Master | 6 | 日志保留 14 天 |
| 对象存储 | - | - | trace dump 约 100G/月 |

### 2.3 月度成本（估算，2026 中国公有云）

| 项目 | 月成本（人民币） | 说明 |
|---|---|---|
| 云主机（K8s 工作节点，约 24 台 8C16G ECS） | ¥35,000–45,000 | 按需+包年混合 |
| MongoDB 托管 三副本 8C32G | ¥7,000 | 或自建 ECS |
| Redis / Kafka / ES / Prometheus 托管 | ¥12,000 | 自建可省 40% |
| 对象存储 + 网络流量 | ¥2,000 | |
| LLM Token 费用 | **¥8,000–¥15,000** | 900 runs × 10k tokens × ¥0.003/1k + Nightly LLM Judge |
| 合计（含冗余 30%） | **¥85,000–¥110,000 / 月** | 首月再加一次性迁移与压测约 ¥30k |

> **降本手段**（Harness 本身就是控制 AI 成本的工具）：
> - Token 缓存（Redis key=prompt hash，相同 prompt 复用 judge 结果）
> - 小模型做 judge（qwen2.5-7b-instruct 自部署，比 API 省 5x）
> - Deterministic evaluator 通过即不跑 LLM-judge
> - Scenario 分层：PR 只跑 smoke 20 条；Nightly 才全量

---

## 三、SLA 与可靠性

### 3.1 SLA 承诺

| 指标 | SLA | 测量方式 |
|---|---|---|
| Harness API 可用性 | ≥ 99.9%（月停机 < 43 分钟） | K8s 探针 + Pingdom 外部监控 |
| PR 门禁延迟（端到端） | P95 < 5 分钟 | 从 scenario 开始到 gate 决策 |
| Nightly 完成率 | ≥ 99%（超时重试后） | 22:00 启动，次日 06:00 前完成 |
| 数据持久性（Scenario / Run 结果） | ≥ 99.999% | Mongo 副本集 + 跨区域冷备 |
| 门禁误报（把正常代码阻断）率 | < 1% | 月度复盘，按 scenario 抽样比对人工 |

### 3.2 可用性设计

- **多可用区部署**：所有服务/中间件跨 AZ，Mongo/RDS 同区域跨 AZ 副本集
- **Harness API 无状态**：Session 不存本地，统一走 Redis + JWT
- **Agent Runner**：KEDA 基于 Kafka lag 弹性扩缩；任务幂等（run_id 唯一约束）
- **降级策略**：
  - LLM API 不可用：Deterministic evaluator 照常跑，LLM-Judge 项标记 deferred，标记结果不阻断门禁（开关控制，默认 P0 故障时 deferred 视作通过）
  - Mongo 不可读超过 30s：降级为"最近一次 baseline + 简单断言通过"，写告警；事后补跑
  - Scenario 运行超时：默认 15 分钟硬超时 kill（防止 LLM 死循环占满 Worker），失败计入统计但不阻断后续 run

### 3.3 灾备 & RPO/RTO

| 故障场景 | RPO | RTO | 手段 |
|---|---|---|---|
| 单 AZ 故障 | 0（跨 AZ 同步复制） | < 5 分钟 | K8s 自动重调度，Mongo 主节点自动故障切换 |
| Mongo 数据误删 / 逻辑错误 | ≤ 1 小时（PITR） | < 2 小时 | Mongo 全量每日 + oplog 增量每 15 min → 对象存储 |
| 整个区域不可用（灾难） | ≤ 24 小时（冷备同步） | < 12 小时 | 备区域拉起：对象存储跨区域复制 + Mongo 定期快照；DNS 切换 |
| LLM 主 API 故障（模型不可用） | 0（同一请求） | < 30s | LLM Gateway 自动降级到备用模型（主=Qwen → 备=DeepSeek） |

---

## 四、安全合规

### 4.1 身份与权限（RBAC）

| 角色 | 权限 |
|---|---|
| Admin | 全量（scenario 删改、baseline 更新、门禁阈值编辑、用户管理） |
| Platform Engineer | scenario 增改、run 触发、报告查看、analyzer 发布 |
| Developer | scenario 增改（自己团队）、run PR 门禁、查看报告 |
| Viewer | 只读 |
| CI Service Account | 仅 `harness.run` + `harness.report.read` 最小权限 |

实现：FastAPI 接公司 SSO（OIDC/LDAP）→ JWT → RBAC 中间件；所有 API 操作写审计日志（Mongo `audit_log` 集合 + ES）。

### 4.2 数据安全

- **Trajectory/Prompt 敏感信息裁剪**：
  - 正则匹配 `sk-xxx`、AK/SK、手机号、身份证、邮箱域名内部地址、数据库连接串等
  - 在写 Mongo 前由 Harness API 统一清洗（可配合你方案中的"SHA-256 脱敏裁剪"思路）
- **传输加密**：全链路 TLS 1.3；服务间 mTLS（Istio sidecar 或 K8s NetworkPolicy）
- **静态加密**：Mongo 磁盘加密（云盘默认）、对象存储 SSE-KMS、K8s Secret 加密
- **数据保留策略**：Run 详细 traces（含 span 输入输出）保留 30 天 → 30 天后输出详情置空、仅保留指标聚合与摘要；Scenario 与 Baseline 永久保留
- **跨境合规**：若有海外场景，Scenario/Trace 数据不出境（GeoDNS + 区域独立部署）

### 4.3 安全测试与审计

- 季度：渗透测试（OWASP Top 10 + LLM 注入 / Prompt Injection）
- 每月：依赖扫描（Trivy 扫描镜像 + SCA 扫 pip/npm 依赖漏洞）
- 持续：WAF 防常见注入；API 网关按 user/IP 限流（防止恶意跑 scenario 刷 Token 费用）

---

## 五、发布 & 灰度 & 回滚

### 5.1 环境划分

| 环境 | 用途 | 数据 | 部署触发 |
|---|---|---|---|
| **DEV** | 本地 + 开发联调 | 造的小数据集 + Mongo 本地 | 本地 helm install / skaffold |
| **TEST** | 功能测试 + 集成测试 | 与生产同 schema，100 条 scenario | MR 合主干后自动部署 |
| **STAGING** | 预发：灰度门禁验证 + 真实场景回放 | 生产 scenario 子集（镜像）| 发布前手动 |
| **PROD** | 真实 CI 门禁 + Nightly | 真实数据 | ArgoCD 自动同步指定 tag |

### 5.2 发布策略

- 常规迭代：**双周发布**，主干开发 → TEST 自动 → STAGING 验证 → PROD 蓝绿
- 大版本（如 Agent Runtime 升级、Harness schema 变更）：**金丝雀发布**
  - 10% runs 路由到新版本运行 1 小时
  - 核心指标对比 baseline：成功率差 < 2%、延迟 < 1.5x 才全量
  - 否则自动切回老版本
- 应急修复（P0 bug）：**热修复**，跳过双周流程，直接 TEST→STAGING→PROD，次日补回归

### 5.3 回滚

- **代码回滚**：ArgoCD 一键回退到上一个镜像版本（镜像带 Git SHA 标签）
- **Baseline 回滚**：Baseline 每次更新 MongoDB 自动存历史版本集合 `baseline_history`，按版本号一键切回
- **Scenario 回滚**：Scenario 文档版本化（Mongo update 自动保留前 N 版），bad scenario 可 revert 到指定 version

---

## 六、可观测性 & 监控告警

### 6.1 指标（Prometheus /metrics）

Harness API / Agent Runner 都暴露以下自定义指标：

```python
# harness/metrics.py
from prometheus_client import Counter, Histogram, Gauge

RUNS_TOTAL = Counter('harness_runs_total', 'Total runs triggered',
                     ['scenario_id', 'gate_level', 'status'])
RUN_DURATION = Histogram('harness_run_duration_seconds', 'Run 端到端耗时',
                         ['gate_level'], buckets=[1,5,15,60,180,600])
TOKENS_TOTAL = Counter('harness_tokens_total', 'LLM tokens consumed',
                       ['model', 'scenario_id'])
COST_USD_TOTAL = Counter('harness_cost_usd_total', 'Dollar cost accumulated')
GATE_DECISIONS = Counter('harness_gate_decisions_total',
                         'Pass/Fail counts', ['gate_level', 'verdict'])
ANALYZER_FINDINGS = Counter('harness_analyzer_findings_total',
                            'Failure modes detected', ['tag', 'severity'])
LATENCY_API = Histogram('harness_api_duration_seconds', 'API latency',
                        ['method', 'path', 'status_code'])
QUEUE_LAG = Gauge('harness_kafka_lag', 'Consumer lag for run/analyzer queues',
                  ['topic', 'consumer_group'])
```

### 6.2 告警规则（Alertmanager）

**P0（电话 + OnCall 立即处理，≤ 15 分钟）**
- Harness API 5xx 率 > 5%，持续 5 分钟
- Mongo 主节点不可用超过 2 分钟
- Kafka run 队列 lag > 1000 且持续增长（会影响次日门禁出报告）
- PR 门禁阻断异常率（连续 20 个 PR 都被同一 scenario 阻断）> 30%：疑似 scenario 误配

**P1（钉钉/飞书群告警，≤ 1 小时）**
- Nightly 未按计划完成（次日 06:00 前仍 < 90% scenario 完成）
- LLM 调用失败率 > 20%，或平均延迟 > 30s 持续 10 分钟
- Token 日消耗超月预算 5%（按天线性监控）
- Analyzer 检测到 `output_truncation` 或 `tool_repetition_loop` 数量突增 3 倍

**P2（邮件 + 看板黄条，工作日处理）**
- 某 scenario 连续 3 次 Nightly 失败（需人工 review 是否 scenario 本身过时）
- Baseline 核心指标（task_success_rate）漂移 > 1%（提醒 Check）

### 6.3 Traces & Logs

- 每个 Scenario Run 有统一 `run_id`，作为 OTel `trace_id` 贯穿：API → Runner → LLM Gateway → Tool Call → Analyzer → DB 写入
- Jaeger/SkyWalking UI 可按 `scenario_id` / `gate_level` / `run_id` 检索
- 结构化日志：JSON 格式、每条必带 `{ts, level, service, run_id, scenario_id, user_id, msg}`，用 EFK 全文检索

---

## 七、OnCall 机制 & 故障处理

### 7.1 OnCall 轮值

- 人员：2 名 Platform Eng 主备轮值（每周一轮） + 1 名 SRE 副线
- 工具：PagerDuty / 夜莺 + 飞书/钉钉机器人 + 电话呼叫
- 交接：每轮 OnCall 结束写 Handoff Doc：未解决告警、已知问题、后续 Action

### 7.2 故障处理 Playbook（示例）

**Playbook #1：门禁大面积误阻断**
1. 验证：打开 Harness 报告页，确认受影响 PR 数量和 scenario 分布
2. **止血开关**（Harness API 配置项）：
   - `GATE_ENABLED=false` → 临时解除门禁阻断（进入"观察模式"：仍跑报告，但退出码恒 0）
   - `DEFERRED_LLM_AS_PASS=true` → LLM-Judge 项全部按 deferred 通过
3. 定位：拉取失败 scenario 的 traces，看近 24h baseline diff，找突变原因（常见：Prompt 改动 / LLM 模型版本升级 / Scenario 被误改）
4. 修复：Revert 对应 scenario 或 baseline 版本；或 LLM Gateway 切回老模型
5. 复盘：事后 24h 内写 RCA 文档（现象→时间线→根因→修复→预防项→Owner→DDL）

**Playbook #2：Agent Runner 队列堆积**
1. KEDA 自动扩容后仍 lag↑ → 手动加 Worker 到最大副本数
2. 检查 LLM API：是否 429 限流 → 临时降并发 + 走备用模型
3. 扫 scenario：若有单个 scenario 单次触发 30min+ 超时 → 临时拉黑名单 + 单独排

**Playbook #3：Trajectory/报告数据不一致**
1. 查 Mongo run 记录 + Kafka 消费位点
2. Mongo `runs` 按 `_id` 修单条；批量跑 `repair_runs.py` 重算聚合指标
3. 补 Analyzer：对指定 date range 重跑 Analyzer Worker（脚本见 `scripts/rerun_analyzer.py`）

---

## 八、对接现有系统清单（集成点）

| 系统 | 对接方式 | 用途 | Owner |
|---|---|---|---|
| 公司 SSO / LDAP | OIDC | Harness 登录 + RBAC | IT + 你方 |
| 代码托管（GitLab/GitHub） | Webhook + App Token | PR 门禁触发、CI 评论回贴报告 | DevOps |
| Jira / 飞书 工单系统 | REST API（read only） | Golden Data Pipeline 抽工单造 scenario | 你方 |
| LLM 平台（内部网关 / 外部 API） | HTTP + SDK | Agent Run、LLM-Judge、Golden Pipeline | AI Platform |
| MCP Skill 服务（Workflow Agent） | MCP 协议 | Agent Runner 调用工具 | AI Platform |
| 监控平台（Prom/Grafana/ES） | OTel + Prom remote_write | 可观测性 | SRE |
| 告警/OnCall | Alertmanager → PagerDuty/夜莺 | 告警分发 | SRE |
| 对象存储 | S3/TOS SDK | Traces 长归档 | 你方 |
| 飞书/钉钉/Slack | Webhook | Nightly 报告、P1 告警通知 | 你方 |

---

## 九、30 / 60 / 90 天落地计划

### 9.1 人员分工（建议团队配置）

- **Tech Lead / 你**：架构、方案决策、跨系统对接、里程碑把关
- **后端工程师 × 2**：Harness API、持久化、集成（SSO/Mongo/Kafka/LLM Gateway）
- **平台工程师 × 1**：K8s 部署、CI/CD、监控告警、OnCall 体系
- **测试 / QA 工程师 × 1**：Scenario 金数据集编写与评审、回归验证
- **（兼职）SRE × 0.5**：中间件运维 + 容灾演练

### 9.2 Milestones

#### Phase 1 · **M1 + M2（0–30 天）：Test Harness + 门禁 MVP 上线**

**目标**：Developer 在 PR 中能看到 Harness 跑结果；能发现 Prompt/工具改动的明显回归。

| 周 | 内容 | 交付物 | 验收标准 |
|---|---|---|---|
| W1 | 基础环境搭建：K8s namespace、Mongo/Redis/Kafka、CI Runner 授权；脚手架建项目 | 环境可用 + CI 绿色 | 所有开发能本地 deploy 一套 harness |
| W2 | Harness API：Scenario 读写、Run 触发、Mongo 持久化、RBAC 基础 + SSO | API 联调通过 | CRUD + 鉴权用例全部过 |
| W3 | Agent Runner MVP：接入**你现有 Workflow Agent 真实 Runtime**（不是 DummyAgent）；采 span 写 Mongo；Deterministic Evaluator 全量实现 | 跑 scenario 生成真实 metrics | 10 条真实 scenario 成功率 > 80% |
| W4 | **PR 门禁上线**：对接 GitHub/GitLab Actions，跑 20 条 smoke scenario，0/1 退出码阻断；Baseline v1.0 建立 | 线上 PR 被真正阻断/放行 | 连续 3 天门禁无明显误报、无漏报；Developer 可接受 |
| W4+1 | **P0 止血开关 + OnCall**：GATE_ENABLED、DEFERRED_LLM_AS_PASS 配置；基础 P0 告警； | 验证：手动触发故障能 10 分钟内止血 | 模拟误阻断演练通过 |

#### Phase 2 · **M3（31–60 天）：Agent Harness + Analyzer + Nightly 报告**

**目标**：过程性评测、诊断、Nightly 报告；团队开始用 Analyzer 发现的 failure mode 反哺 Agent 优化。

| 周 | 内容 | 交付物 | 验收标准 |
|---|---|---|---|
| W5 | Trajectory 标准化：OTel SDK + Jaeger 全链路；Evaluator：trajectory 3D + tool accuracy/order | OTel trace 可见 | 每步 span 都能在 Jaeger 查到对应 |
| W6 | LLM-Judge：接入小模型 judge（qwen-7b or 4o-mini），结果与 deterministic 融合；Scenario 量扩到 100 | LLM-Judge 线上化 | 人工抽检 50 条 scenario，judge 与人工一致性 > 85% |
| W7 | Analyzers：重复循环/延迟尖刺/失败模式分类；Analyzer Worker（Celery）异步执行 | Analyzer 报告 | 人工插入 10 条坏 case，Analyzer 全检出 |
| W8 | **Nightly Pipeline 上线**：全量 scenario + Agent Harness + Analyzer → HTML 报告 → Slack 推送；Grafana 看板（核心指标） | 每天早上能在群里看到报告 | 连续 7 天 Nightly 正常完成、告警正常分级 |
| W9 | **第一次优化循环**：用 Analyzer 报告的 Top 10 failure mode，给 Workflow Agent 提 10 个优化项，落地 5 个后指标明显改善 | 指标对比记录 | task_success_rate 相对上线初提升 ≥ 5% |

#### Phase 3 · **M4（61–90 天）：Golden Data Pipeline + 容灾 + 成本治理**

**目标**：评测集自动增长、系统具备生产级容灾、成本可控。

| 周 | 内容 | 交付物 | 验收标准 |
|---|---|---|---|
| W10 | Golden Data Pipeline：从工单/PR 评论抽候选 → LLM 合成 scenario → 人工评审队列 → 入库 | Pipeline 可运行 | 每周自动产出 ≥ 5 条候选 scenario，评审通过率 ≥ 60% |
| W11 | 多 AZ + PITR：Mongo 跨 AZ 副本集 + 每日全量 + 15min oplog 增量；冷演练一次 | 备份报告 + 演练记录 | 随机选一天 PITR 恢复到 1 小时前任意时点，数据校验 OK |
| W12 | 成本治理：Token 缓存 + 小模型 judge + Deterministic 通过跳 judge；Budget 告警 + 月度成本报告 | 月成本下降 ≥ 25%（对比 W5） | 实际账单 + 内部对账 |
| W13 | 压力测试：模拟 10 倍 Nightly 跑，验证 HPA/扩容/限流/超时正常 | 压测报告 | P99 run 延迟无退化、没有服务雪崩、队列最终消化 |
| W14 | SLA 正式生效、OnCall 轮值启动、RCA 文档模板固化；向其他团队（除直播外）开放接入 | 接入文档 + 用户数 | 至少 1 个其他团队接入并跑通 20 条 scenario |
| W15+ | 长期：RL Harness（奖励模型训练）、LangGraph State 回放、A/B 对比看板等进阶能力 | 长期 Roadmap | |

### 9.3 风险清单与应对

| 风险 | 概率 | 影响 | 应对措施 |
|---|---|---|---|
| LLM 输出不稳定导致门禁 flakiness 高 | 高 | P1 | 固定 seed+temp=0、多次跑取 median、失败自动重试 2 次、引入"允许波动窗口" |
| Scenario 质量差 / 过时，误阻断大量 PR | 高 | P1 | 评审准入机制；Scenario 连续失败自动冻结 + 通知 Owner；P0 止血开关常备 |
| Token 成本远超预算 | 中 | P1 | 小模型 judge、缓存、分层门禁、Budget 上限硬截止、每日 Budget 告警 |
| 与 Workflow Agent Runtime 对接困难 | 中 | P1 | 提前 W2 就启动接入 PoC，用 `AgentExecutor` 协议定义最小接口；不通就走"HTTP 调用 Agent 服务 + JSON 转 span"宽松模式 |
| 中间件/Mongo/K8s 运维能力不足 | 中 | P2 | 优先云托管版（ACK + 云 Mongo + 云 Redis/Kafka），少自建；和 SRE 共担 |
| 开发者不信任门禁、要求关掉 | 中 | P2 | 上线初门禁可设为"观察模式（不阻断但出报告）"2 周，积累成功案例后再切阻断；组织培训 + FAQ |
| Prompt Injection 通过 scenario 污染评测集 | 低 | P2 | Scenario 入库做静态扫描 + 评审；禁止 scenario 中包含用户可控输入直接拼到 system prompt 无隔离 |

---

## 十、常见问题（FAQ for Rollout）

1. **我们现在 Workflow Agent 是自研 Runtime（不是 LangGraph），接进去难吗？**
   不难。只要实现 `AgentExecutor` 协议：输入 prompt/context/tools_whitelist/seed，流式吐 turn dict。即使 Runtime 只提供 HTTP 接口，包一层 `RemoteExecutor` 发 HTTP + SSE 即可。

2. **Scenario 谁来写？写多少够？**
   起步 20 条：从历史线上 Top 故障 + 团队最常用的 5 个 Agent 场景各 4 条；之后靠 Golden Pipeline 自动产，3 个月目标 200+ 条。写 scenario 不是一次性活，是长期运营工作。

3. **我们没有专门的 SRE / 运维，能上生产吗？**
   能。全用云托管版：ACK 托管 K8s + 云 Mongo 副本集 + 云 Redis + 云 Kafka + 云 Prometheus + 云 ES。SRE 压力降低 70%，初期 1 名平台工程师 + 1 名后端兼职值守即可。

4. **上了 Harness 是不是就不用人工测了？**
   不是。Harness 是**自动化回归 + 指标化**，让你"每次改动都知道和上次比好了坏了多少"；人工主要负责：评审新增 scenario、分析 Analyzer 报告、决定 Prompt/Agent 优化方向。Harness 替代的是"重复人工点按钮 + 看输出对不对"。

5. **最容易踩的坑是什么？**
   ① 一上来就做"AI 全能型"——先跑通 Deterministic，再上 LLM-Judge，再上 Analyzer，别同时上；
   ② 没做止血开关——门禁误阻断 1 次就会让开发者失去信心，GATE_ENABLED 开关必须上线前验证好；
   ③ 没做 Baseline 版本化——每改 Baseline 要可追溯可回滚，谁改的、为什么改要留痕。

---

## 附：关键文档与脚本索引

| 文档/脚本 | 路径 |
|---|---|
| 方案总览（为什么做 + 设计） | `AI-Native全栈工作流优化方案与Harness设计.md` |
| 生产落地手册（本文件） | `Harness生产落地手册.md` |
| Harness 代码骨架（MVP 可运行） | `demos/workflow-harness/` |
| Harness 生产级代码（API+LangGraph+OTel+Dockerfile） | `demos/workflow-harness-production/`（同目录交付） |
| CI/CD + K8s + Grafana 配置 | `demos/workflow-harness-production/infra/` |
