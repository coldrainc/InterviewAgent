# Learning Harness 发布与回滚 Runbook

## 1. 发布门禁

1. PostgreSQL CI 从上一生产 revision 执行 `alembic upgrade head`，再回滚一个 revision 并重新升级。
2. 后端全量测试、桌面构建和共享 TypeScript 契约检查通过。
3. 使用测试租户验证 Today、命令幂等/冲突、面试官题纲、训练、间隔复习、导出、删除申请和取消。
4. 检查 `/ops/metrics`，确认 Learning 指标可见且 Trace 不包含简历、回答、token 或支付字段。
5. 数据库快照和对象存储版本/备份策略已生效；确认值班负责人。
6. 微信小程序先跑 Node 契约检查，再在开发者工具和至少一台真机验证 Today 启动、409 冲突恢复、离线只读和重新联网同步。

SQLite 只用于单元测试和局部迁移验证。历史 `20260704_0001` 使用 PostgreSQL `JSONB`，空 SQLite 无法证明全链迁移；生产迁移结论必须来自 PostgreSQL CI。

2026-09-05 本地 PostgreSQL 16 证据：空库成功执行 `0001 -> 0014`，随后 `0014 -> 0013 -> 0014` 往返；最终 revision 为 `20260905_0014`，并核对 `learning_ability_snapshots`、`learning_effect_receipts`、`interviewer_kits`、`training_drills`、`data_deletion_requests` 和 owner/idempotency 唯一索引。该证据证明当前迁移链可运行，不替代发布 CI 和生产备份演练。

## 2. 灰度步骤

| 阶段 | 流量 | 时长 | 放量条件 |
| --- | ---: | ---: | --- |
| 内部租户 | 0% 外部 | 1 个工作日 | 无数据隔离/删除/账务事故 |
| 邀请灰度 | 5% | 24 小时 | 命令成功率和 P95 达标，无错误率突增 |
| 扩大灰度 | 25% | 48 小时 | 冲突率稳定，验证拒绝可解释，客服无阻断问题 |
| 全量 | 100% | 持续 | SLO 和隐私检查持续通过 |

功能开关应按租户控制 Today 新入口、自适应修订、离线缓存和隐私入口。数据库迁移先行且向后兼容；旧客户端必须能继续使用旧进度 API。

## 3. SLO 与告警

| SLI | 目标 | 告警阈值 | 负责人 |
| --- | --- | --- | --- |
| 学习命令成功率 | 28 天 `>=99.5%` | 15 分钟、至少 20 次请求且 `<98%` | Backend on-call |
| 学习命令 P95 | `<750ms`，不含模型任务 | 15 分钟 `>1500ms` | Backend on-call |
| 版本+幂等冲突率 | 基线 `<5%` | 15 分钟 `>10%` | Client + Backend |
| 验证拒绝率 | 产品基线 `<25%` | 1 小时 `>35%`，检查规则/证据 UX | Learning product |
| 删除工单逾期 | `0` | 超过 `execute_after` 30 分钟仍未执行 | Privacy owner |
| 同步游标错误率 | `<1%` | 15 分钟 `>5%` | Client owner |

当前 `/ops/metrics` 为单进程滚动指标，适用于单实例邀请灰度。多实例上线前必须接入集中式指标后端并配置实际通知渠道；未完成时不得宣称全局 SLO 已建立。

## 4. 回滚

- UI/行为异常：关闭对应租户功能开关，客户端回退到旧 Dashboard/进度 API，保留 receipts。
- 命令错误率升高：停止写命令入口，Today 降级只读；不得删除或重写 receipt。
- 迁移异常：停止应用写入，使用数据库快照恢复；只有确认 0014 无删除工单数据时才允许 schema downgrade。
- 删除 worker 异常：先停止 worker，不撤销用户申请；修复后按 `request_id` 幂等重跑。已经执行的数据删除不可通过应用回滚恢复。
- 同步异常：客户端清 cursor 后 bootstrap；服务端仍以 ledger 为权威。

## 5. 日志与隐私检查

禁止记录简历正文、完整回答、题目/参考答案、模型原始输出、token、密码、支付 payload 和删除原因。Trace 入口统一经过 `telemetry_privacy.sanitize_telemetry`；访问日志只记录 request id、方法、路径、状态、耗时、IP 和 user agent。生产抽样检查需搜索敏感字段名和测试水印，发现泄漏立即停止放量并清理日志保留副本。
