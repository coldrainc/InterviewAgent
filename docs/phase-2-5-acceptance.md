# Phase 2-5 验收记录

> 验收日期：2026-09-05
> 结论：本地邀请灰度基线通过；生产全量放量仍受第 6 节门禁约束。

## 1. Phase 2：正式账本与并发契约

- Goal、plan version、task run、evidence、verification、effect receipt 和 revision 已进入正式表。
- 命令支持 `expected_version`、幂等键、409 `current_task` 恢复和 tenant/user 所有权校验。
- `/learning/today`、任务命令和 opaque cursor 同步已覆盖 API、服务和真实 HTTP 链路。
- Alembic 在 PostgreSQL 16 完成 `0001 -> 0014 -> 0013 -> 0014` 往返。

## 2. Phase 3：自适应计划

- 能力快照、规则触发器、计划 revision diff、接受/撤回和任务锁定已落地。
- 连续失败、低完成率、能力提升和过载场景有回放测试。
- Revision 保留原因、前后版本和 receipt，不直接重写历史计划。

## 3. Phase 4：面试官与训练体验

- 面试者和面试官入口、结构化题纲、人工证据、训练、间隔复习和报告回流已接通。
- 客观题规则判定、主观题 LLM/规则降级、错题与专项训练有后端测试。
- 浏览器完成面试官题纲创建、训练四视图、复习七视图、配置、账户与隐私入口验收。

## 4. Phase 5：第二客户端与治理基线

- 微信小程序 Today 使用服务端权威快照、隔离缓存、幂等命令、版本冲突恢复和同步 cursor。
- 数据导出、7 天删除冷静期、取消、执行 worker、令牌撤销和遥测脱敏已落地。
- 桌面 `390x844` 验证侧栏抽屉、导航关闭、复习站布局和零横向溢出。
- OpenAPI 保持 `102 paths / 73 schemas`，无重复 method/path。

## 5. 自动化证据

```text
Backend: 152 passed
Desktop: Vite production build passed
Shared packages: strict tsc --noEmit passed
Miniapp: 6 tests passed + structure/navigation checks passed
PostgreSQL: 0001 -> 0014 -> 0013 -> 0014 passed
Browser: desktop and 390x844 responsive flows passed, fresh console clean
```

## 6. 生产放量门禁

- 将 PostgreSQL 全链迁移和往返检查固化进 CI，并从上一生产 revision 验证。
- 微信开发者工具及真机完成登录、离线、冲突、重连和弱网 E2E。
- 单进程 `/ops/metrics` 接入集中式多实例指标和真实外部通知渠道。
- 支付宝、微信真实商户环境完成签名、异步回调、重复通知和退款对账验收。
- 身份、支付、简历和流式会话兼容路由继续从 `interfaces/api.py` 迁移，但不得与业务行为修改同批进行。
