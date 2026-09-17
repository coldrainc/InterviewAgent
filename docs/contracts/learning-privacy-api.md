# Learning 与 Privacy API 契约

## 1. 版本和身份

- Today 契约版本：`learning.today.v1`。
- 同步契约版本：`schema_version: 1`，`authority: server`。
- 所有资源按 `tenant_id + user_id` 隔离；客户端不得传入并信任资源所有者字段。
- 客户端共享类型位于 `packages/shared-types`，调用封装位于 `packages/api-client`。
- 微信小程序 Today 使用相同契约，并按 `tenant_id + user_id` 生成缓存和 cursor key。

## 2. 核心 API

| 方法 | 路径 | 契约 |
| --- | --- | --- |
| `GET` | `/learning/today` | 返回今日任务、下一动作、风险和契约版本 |
| `GET` | `/learning/tasks/{id}` | 返回服务端权威任务投影和当前 `version` |
| `POST` | `/learning/tasks/{id}/commands` | 执行 `start/complete/reopen/verify` |
| `GET` | `/learning/sync` | 按 opaque cursor 拉取 immutable receipts |
| `GET` | `/privacy/export` | 返回按领域分组的 JSON 数据副本 |
| `GET` | `/privacy/deletion` | 返回当前有效删除工单和冷静期 |
| `POST` | `/privacy/deletion` | 精确 `confirmation: DELETE` 后申请删除 |
| `DELETE` | `/privacy/deletion` | 冷静期内取消删除 |

命令请求必须发送：

```http
Idempotency-Key: <client-generated-unique-key>
Content-Type: application/json

{"action":"complete","expected_version":3,"evidence":{}}
```

相同 key、相同任务和动作返回原 receipt，并标记 `idempotent_replay=true`。相同 key 用于不同命令返回幂等冲突。

## 3. 冲突处理

版本冲突返回 HTTP 409，结构化信息在错误 envelope 的 `details`：

```json
{
  "code": 409,
  "error": "REQUEST_FAILED",
  "message": "请求处理失败。",
  "data": null,
  "request_id": "...",
  "details": {
    "code": "version_conflict",
    "expected_version": 3,
    "current_version": 4,
    "current_task": {},
    "resolution": "refresh_and_retry"
  }
}
```

客户端固定流程：停止本地写入，采用 `current_task` 更新 UI，提示状态已变化；只有用户动作仍适用时才用新版本和新幂等键重试。不得自动覆盖服务端状态。

## 4. 离线与同步

- Today 快照按 `tenant_id + user_id` 隔离缓存。
- 离线仅允许浏览；执行、完成、打卡和计划修订全部禁用。
- cursor 为不透明字符串，客户端不得解析、拼接或持久修改。
- `has_more=true` 时继续分页；拉取完成后刷新 `/learning/today`。
- cursor 无效返回 `invalid_sync_cursor`，客户端清空 cursor 后执行一次完整 bootstrap，不删除本地只读快照。
- HTTP 409 时客户端必须直接应用服务端返回的 `current_task`；不得在旧 `version` 上继续乐观更新。

## 5. 隐私生命周期

- 导出不包含密码哈希、刷新令牌、支付凭据和对象存储二进制。
- 删除申请有 7 天冷静期，申请期间账户保持可登录以便取消。
- 到期执行后：删除产品数据和简历对象，账户去标识化，撤销 refresh token，旧 access token 被账户状态门禁拒绝。
- 账务流水、安全审计和删除审计按合规最小化原则保留。
