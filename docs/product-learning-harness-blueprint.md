# Interview Agent 产品与 Learning Harness 落地蓝图

> 状态：Phase 1-4 已落地，Phase 5 邀请灰度基线已落地（2026-09-05）
> 目标：把现有面试、刷题、计划、复习、打卡能力，收敛为可执行、可验证、可调整的备考闭环。

## 1. 产品结论

Interview Agent 不应只是“AI 面试聊天 + 若干工具页面”，而应成为一个以目标为中心的备考执行系统。用户给出目标和约束后，系统负责诊断、规划、执行引导、结果验证、复盘和计划调整；用户始终知道今天该做什么、为什么做、做到什么程度才算完成。

北极星指标：每周完成且通过验证的有效学习任务数。辅助指标包括首日有效行动率、7 日计划留存率、任务验证通过率、薄弱项改善率、计划按期完成率和模拟面试分数趋势。

明确不以消息数、计划生成数、页面访问量作为核心成功指标，避免“生成很多、完成很少”。

## 2. 用户与核心场景

### 2.1 面试者模式

- 输入岗位、级别、公司、面试日期、简历和每日可用时间。
- 完成基线测评，得到能力画像、风险项和冲刺计划。
- 按今日任务执行模拟面试、专项刷题、知识复习和表达训练。
- 每项任务提交证据，系统验证并更新掌握度。
- 面试报告中的薄弱项自动回流到后续计划。

### 2.2 面试官模式

- 输入岗位画像、面试时长、考察维度和候选人信息。
- Agent 生成结构化题纲，面试官可编辑、锁定或换题。
- AI 辅助追问、记录证据，但最终评价权属于面试官。
- 输出基于证据的评分、风险、待确认项和复盘报告。
- 面试数据默认隔离，敏感信息支持删除与导出。

### 2.3 自主刷题与复习

- 可按主题、难度、公司、薄弱项、错题和计划来源筛选。
- 客观题即时判定；主观题展示评分维度、引用证据和改进建议。
- 错题不是静态收藏，而是进入间隔复习队列。
- 用户可调整计划强度、暂停、顺延、补做和跳过，但必须记录原因。

## 3. 产品闭环

统一闭环为：

`目标契约 -> 基线诊断 -> 计划拆解 -> 今日执行 -> 证据验证 -> 反馈复盘 -> 自适应修订`

每一步必须产生可持久化结果：

| 阶段 | 输入 | 输出 | 不通过时 |
| --- | --- | --- | --- |
| 目标契约 | 岗位、日期、时间、偏好 | GoalContract | 要求补齐关键约束 |
| 诊断 | 简历、历史、基线测评 | AbilitySnapshot | 标记未知，不伪造结论 |
| 规划 | 目标、能力差距 | Plan、Stage、Task | 降低强度或请求确认 |
| 执行 | TypedTask、上下文 | Interview/Attempt/Note | 保留断点并给出下一动作 |
| 验证 | 验收规则、执行证据 | VerificationResult | 不计完成，返回缺失证据 |
| 复盘 | 结果、耗时、掌握度 | EffectReceipt | 进入人工复核 |
| 修订 | Receipts、剩余时间 | PlanRevision | 保留原版本和修订原因 |

## 4. 信息架构与交互

### 4.1 一级导航

1. 今日：唯一默认首页，展示下一最佳动作、今日任务、进度、风险和快捷入口。
2. 面试：模拟面试、面试官工作台、历史会话、报告。
3. 训练：题库、专项训练、错题、收藏、间隔复习。
4. 计划：目标、计划时间线、日历、调整记录。
5. 知识：简历、岗位材料、个人答案库、复习资料。
6. 成长：能力雷达、趋势、成就、学习统计。

账号、模型、计费、隐私、导入导出放入设置，不占用主要工作路径。

### 4.2 今日工作台

页面优先级固定：

1. 下一最佳动作：一条明确建议和一个主按钮。
2. 今日任务：按优先级排序，显示类型、预计时间、来源、验收状态。
3. 风险提示：逾期、连续失败、计划过载、数据不足。
4. 周趋势：学习时长、验证完成数、正确率和面试分数。

任务卡只允许一个主操作。`start` 负责建立执行断点，`complete` 触发验证，`reopen` 撤销完成。自动验证未通过时不允许假完成，必须展示缺失证据及继续入口。

### 4.3 面试体验

- 面试前：目标、模式、时长、主题、简历、模型与设备检查。
- 面试中：问题区、回答区、进度、计时、结束按钮；避免暴露评分答案。
- 面试官模式：支持采纳/改写 AI 追问、手工笔记、维度标记。
- 中断恢复：保存阶段、当前题、已回答内容和剩余时间。
- 面试后：先给总结，再给证据、分项评分、薄弱项和可加入计划的任务。

### 4.4 异常和边界状态

- 无计划：今日页引导完成目标配置或快速开始一次诊断。
- 无题库：给出导入/同步入口，不显示空白列表。
- 模型超时：保留用户输入，可重试或使用规则降级。
- 离线：允许浏览缓存计划与资料；需要模型/服务的操作明确标记。
- 计划过载：当预计时长超过可用时间，必须提示并支持一键降载。
- 多端冲突：后写入需携带版本号；冲突时保留双方修改并请求选择。
- 删除账号：说明影响范围、冷静期、导出和不可恢复边界。

## 5. Learning Harness 设计

### 5.1 核心对象

- `GoalContract`：目标岗位、截止日期、时间预算、成功标准和约束。
- `AbilitySnapshot`：能力维度、置信度、证据来源和更新时间。
- `LearningPlan`：目标快照、版本、状态和修订原因。
- `StageLedger`：阶段及任务的执行账本，不依赖前端临时状态。
- `TypedTask`：`interview | practice | review | material | checkin`。
- `AcceptanceRule`：自动验证、自我确认或人工复核规则。
- `Evidence`：会话报告、作答记录、笔记、耗时或外部材料。
- `VerificationResult`：`not_run | verified | rejected | needs_review`。
- `EffectReceipt`：命令、前后状态、验证证据、时间与下一动作。
- `PlanRevision`：计划变更 diff、原因、触发信号和操作者。

### 5.2 任务状态机

`todo -> in_progress -> completed`

扩展状态：`blocked`、`skipped`、`expired`。其中 `completed` 只能由验证器产生；前端勾选只是提交 `complete` 命令，不直接改数据库布尔值。

规则：

- `start`：写入开始 receipt，状态进入 `in_progress`。
- `complete`：执行 Verifier；通过后进入 `completed`，否则进入 `blocked`。
- `verify`：重新验证已有证据。
- `reopen`：回到 `todo`，保留历史 receipt。
- 所有命令必须校验 tenant/user/task 所属关系。
- receipt 只追加，最多保留在线热数据；完整历史在 Phase 2 独立表保存。

### 5.3 验证策略

| 任务类型 | Phase 1 | 目标形态 |
| --- | --- | --- |
| interview | 关联 `plan_task_id` 的会话已完成且有报告 | 可配置最低时长、轮次、分数 |
| practice | 任务启动后存在匹配题目/主题的作答 | 可配置题数、正确率、连续掌握 |
| review | 用户自我确认并记录 receipt | 问答抽检或间隔复习验证 |
| material | 用户自我确认 | 阅读进度 + 摘要/测验 |
| checkin | 聚合当日任务和耗时 | 由任务完成自动生成，无独立造数 |

### 5.4 自适应修订

RevisionPolicy 每日轻量执行、每周完整执行。触发条件包括连续两次验证失败、连续两天任务完成率低于 50%、掌握度提升、面试日期变化或时间预算变化。

修订动作限定为调整顺序、难度、任务量、复习间隔和增加诊断任务。禁止无解释地重写整份计划。所有调整显示“为什么改”和“改了什么”，用户可接受、撤回或锁定任务。

## 6. 工程架构与拆分

### 6.1 架构原则

当前阶段采用模块化单体。原因是业务模型仍在快速收敛，面试、刷题和计划共享事务与身份边界；立即拆微服务会放大部署、数据一致性和调试成本。

目标目录：

```text
backend/src/interview_agent/
  app/                    # 应用启动、依赖装配
  domains/
    identity/
    interview/
    practice/
    planning/
    learning/             # 跨能力编排的产品核心
    knowledge/
    billing/
    ops/
  harness/
    contracts.py
    executor.py
    verifier.py
    revision.py
    receipts.py
  infrastructure/
  interfaces/http/
    routers/
```

Phase 1 先增加 `learning/`，不搬动原模块；Phase 2 将 `interfaces/api.py` 按路由域拆开；Phase 3 才迁移 service/repository。每次迁移保持 API 兼容并有契约测试，禁止“移动文件同时改业务逻辑”。

### 6.2 API 边界

- `/learning/today`：面向产品的今日聚合视图（Phase 2 替代 `/study/dashboard`）。
- `/learning/tasks/{id}`：统一任务详情。
- `/learning/tasks/{id}/commands`：`start/complete/reopen/verify/skip`。
- `/learning/goals`、`/learning/plans`、`/learning/revisions`：目标与计划版本。
- 领域 API `/interviews`、`/practice` 继续负责能力执行，不直接修改计划状态。
- Learning Harness 通过证据查询完成状态，不让各领域反向依赖 planning。

接口统一返回 `request_id`；命令接口后续增加 `Idempotency-Key` 和 `expected_version`。错误码区分业务拒绝、资源不存在、版本冲突和系统失败。

### 6.3 数据演进

Phase 1 复用 `review_plan_tasks` 和 `review_progresses.metadata_json`，保存最近 receipts，快速验证协议。

Phase 2 新增：

- `learning_goals`
- `learning_plan_versions`
- `learning_task_runs`
- `learning_evidence`
- `learning_verifications`
- `learning_effect_receipts`
- `learning_plan_revisions`

迁移采用双写、回填、读切换、停止旧写、清理五步。每步包含计数对账与回滚开关。现有 `jobs/job_steps/job_events` 只承载长任务执行，不作为长期产品账本。

### 6.4 前端拆分

```text
apps/desktop/src/renderer/
  app/                    # shell、路由、provider
  features/
    today/
    interview/
    practice/
    planning/
    knowledge/
    growth/
  shared/
    api/
    ui/
    hooks/
```

先拆 `HomePage` 的任务卡与状态逻辑，再拆体积最大的 `ReviewSitePage` 和 `App`。跨端共享 OpenAPI 生成类型、领域枚举、设计 token 和文案 key；不共享平台 UI 组件。

### 6.5 安全、隐私和可观测性

- 简历、面试记录、评价报告按 tenant/user 强隔离。
- 日志不记录简历原文、完整回答、token 和支付载荷。
- 高风险操作具备审计记录，用户可导出和删除个人数据。
- Prompt injection 扫描覆盖知识导入与外部搜索内容。
- Trace 至少包含 goal/plan/task/run/request/session 关联 ID。
- 指标覆盖命令成功率、验证拒绝率、端到端耗时、模型降级率和回流任务完成率。

## 7. 分阶段施工与验收

### Phase 1：统一任务纵切片（已完成）

交付：任务投影、统一命令、Verifier、EffectReceipt、今日页状态交互、测试和本文档。

DoD：

- 今日接口单次返回任务执行所需字段，不再二次下载整份计划。
- 面试任务没有完成报告时无法勾选完成。
- 通用复习任务可完成、撤销，并留下前后状态 receipt。
- 状态更新同步打卡聚合；旧进度接口仍兼容。
- 服务/API 测试通过，桌面端构建通过。

### Phase 2：目标与正式账本（已完成）

交付：GoalContract、正式 run/evidence/verification/receipt 表、幂等键、版本控制、`/learning/today`、API 路由拆分。

DoD：并发命令可检测冲突；receipt 完整可追溯；迁移前后任务/完成数对账一致；首页只依赖 learning API。

### Phase 3：自适应计划（已完成）

交付：基线诊断、能力快照、RevisionPolicy、计划 diff 审批、任务顺延和过载治理。

DoD：规则回放测试覆盖主要触发器；计划调整可解释、可撤回；锁定任务不被自动修改。

### Phase 4：完整面试官与训练体验（已完成）

交付：面试官工作台、结构化题纲、人工证据、专项训练、间隔复习、跨能力报告。

DoD：两种角色从配置到报告端到端可用；客观/主观题验证准确；报告薄弱项可一键回流且去重。

### Phase 5：多端与上线治理（邀请灰度基线已完成）

交付：OpenAPI SDK、推送、离线缓存、同步冲突、灰度、数据导出删除、SLO 与告警。

DoD：核心链路桌面/Web/移动至少两端 E2E；隐私和支付清单通过；关键 SLO 有仪表盘和告警负责人。

当前已落地：服务端权威增量同步、桌面与微信小程序的租户/用户隔离只读缓存、`expected_version` 冲突恢复、opaque cursor、共享 TypeScript SDK、数据导出、7 天冷静期删除和取消、令牌撤销、Trace 脱敏、Learning 实时指标及运维面板。桌面浏览器关键页面和交互已验收，微信小程序 Today 的缓存、命令和冲突路径有自动化测试；真实 PostgreSQL 16 已完成 `0001 -> 0014 -> 0013 -> 0014` 往返迁移验证。

生产放量边界：微信开发者工具/真机完整 E2E、CI 中持续执行 PostgreSQL 迁移链、集中式多实例指标、外部告警通知和真实支付生产验收仍是上线门禁；不以 Node 小程序测试、本地一次性 PostgreSQL 验证、单进程指标或桌面构建替代。详见 `docs/runbooks/learning-harness-release.md`。

## 8. 不空转检查表

每个功能只有同时满足以下条件才算完成：

- 有明确用户入口和空/错/加载/离线状态。
- 有持久化结果，不依赖前端内存冒充完成。
- 有验收规则和失败后的下一动作。
- 有权限、租户隔离、输入校验和审计边界。
- 有单元/契约测试；关键路径有 E2E。
- 有指标、日志关联 ID 和降级策略。
- 有迁移、兼容和回滚方案。
- 文档中的状态、API 和代码一致。

## 9. 当前已知技术债

- `interfaces/api.py` 已拆出 catalog、operations、review plans/progress/materials/practice、study dashboard 路由，但身份、支付、简历和会话流仍与应用装配耦合。
- `App.jsx` 已拆出账户、会话和侧栏控制器；`ReviewSitePage.jsx` 已拆出数据控制和内容组件，仍可继续拆交互控制器。
- 浏览器 API 客户端部分旧方法吞掉异常，导致 UI 误判成功。
- 多端功能不完全对齐；小程序已覆盖 Today 核心闭环，但面试官、隐私删除和完整训练体验仍以桌面端为主。
- 旧进度 JSON 中仍保留最近 receipt 兼容副本，正式账本已经是权威来源，后续可停止旧双写。
- 测试环境依赖项目虚拟环境；CI 需明确 Python/Node 版本和数据库矩阵。
- `/ops/metrics` 当前是单进程滚动指标，多实例前需接入集中式时序数据库和告警渠道。
- PostgreSQL 16 本地全链迁移已验证；仍需把同一门禁固化进 CI，并在每次发布从上一生产 revision 重跑。

架构、接口、阶段验收和发布细节分别维护在 `docs/architecture/learning-harness-modules.md`、`docs/contracts/learning-privacy-api.md`、`docs/phase-2-5-acceptance.md` 和 `docs/runbooks/learning-harness-release.md`，避免单文件继续膨胀。
