# 客户端请求来源与服务端审计契约

## 请求头

所有用户端请求必须携带以下请求头：

- `X-Client-Platform`: `web`、`desktop`、`android`、`ios`、`harmony` 或 `miniapp`
- `X-Client-Version`: 客户端发布版本，例如 `0.1.0`
- `X-Client-Request-Id`: 客户端生成的单次请求 ID
- `X-Request-ID`: 与 `X-Client-Request-Id` 使用相同值，兼容现有链路追踪

平台和版本头只描述请求来源，不参与认证与数据归属判定。租户、用户、角色和认证平台始终以服务端验证后的 Token 为准。

## 服务端记录

`client_request_logs` 仅记录以下最小元数据：

- Token 解析出的租户、用户和认证平台
- 客户端平台与版本
- 请求 ID、HTTP 方法、路由模板、状态码和耗时
- 认证平台与客户端平台是否一致

禁止记录请求正文、查询参数、Token、Cookie、简历、回答、对话和模型提示词。无法识别的平台或不符合白名单格式的版本统一记录为 `unknown`。

认证平台与客户端平台不一致时，服务端额外写入 `platform_mismatch` 安全事件，但不得使用客户端请求头覆盖 Token 身份。审计写入失败只写服务端错误日志，不得改变产品请求响应。

## 部署与运维

单服务器部署入口会在 API 启动前执行 `alembic upgrade head`，自动创建审计表及索引。生产环境应按数据治理周期清理过期记录，并在备份、导出和排障时继续遵循租户隔离。
