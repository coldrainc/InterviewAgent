# 原生多端上线方案

目标端：

- 微信小程序：原生小程序工程。
- iOS：Swift + SwiftUI。
- Android：Kotlin + Jetpack Compose。
- HarmonyOS：ArkTS + ArkUI。
- Desktop：保留当前 Electron + React。

## 总体原则

Interview Agent 的核心能力放在后端：

- AgentLoop、Harness、RAG、联网搜索、Embedding、Memory。
- 简历解析、对象存储、会话持久化、行业画像。
- 鉴权、限流、审计、脱敏和模型供应商配置。

端侧只负责：

- 登录和授权。
- 简历上传和选择。
- 行业选择、面试模式选择、会话列表。
- 对话输入、流式展示、历史恢复。
- 支付、订阅、通知和设置。

不要在端侧直接调用 LLM API，也不要把模型密钥放进客户端。

## 工程结构

```text
apps/
  desktop/      # Electron + React，现有桌面端
  miniapp/      # 微信原生小程序
  ios/          # Swift + SwiftUI，含最小 Xcode 工程
  android/      # Kotlin + Jetpack Compose，含 Gradle 工程
  harmony/      # ArkTS + ArkUI，含 DevEco/Hvigor 工程
packages/
  shared-types/ # 多端共享 API 类型
  api-client/   # Web/小程序可复用 TS API Client
  design-tokens/# 颜色、字号、间距等设计 token
backend/
  src/interview_agent/
```

## API 协议

当前多端骨架依赖这些接口：

```text
GET    /health
POST   /auth/dev-login
POST   /auth/wechat/login
POST   /auth/apple/login
POST   /auth/phone/login
GET    /me
GET    /metadata/industries?target_role=AI%20应用工程师
GET    /resumes
POST   /resumes
POST   /sessions
GET    /sessions
GET    /sessions/{session_id}
POST   /sessions/{session_id}/messages
POST   /sessions/{session_id}/stream
DELETE /sessions/{session_id}
```

下一阶段建议新增：

```text
POST   /uploads/presign
POST   /feedback
POST   /billing/checkout
GET    /billing/subscription
```

## 流式响应方案

推荐后端新增统一流式协议：

```text
POST /sessions/{session_id}/stream
Content-Type: application/json
Accept: text/event-stream
```

事件类型：

```text
message.delta      # 模型增量文本
message.done       # 完整消息结束
guardrail.notice   # Harness 护栏提示
tool.notice        # 检索、搜索、工具调用状态
error              # 可展示错误
```

平台处理：

- iOS / Android / HarmonyOS：优先 SSE 或 WebSocket。
- 微信小程序：优先验证 `wx.request` 流式能力；不稳定时使用短轮询或 WebSocket 兜底。

## 发布前安全要求

- 所有线上 API 必须 HTTPS。
- 开启 `INTERVIEW_API_AUTH_REQUIRED=true`。
- `/auth/dev-login` 只能用于本地开发，生产环境关闭 `INTERVIEW_AUTH_DEV_LOGIN_ENABLED`。
- `/auth/wechat/login` 已支持配置 AppID/AppSecret 后走微信 code2session；`/auth/apple/login`、`/auth/phone/login` 当前仍是安全占位，上线前必须接入 Apple identityToken 校验和短信验证码服务。
- 客户端不保存模型密钥、不保存完整简历明文。
- 简历、会话、报告都必须按用户或租户隔离。
- 日志默认脱敏：手机号、邮箱、token、简历正文、模型原始 prompt。
- 增加用户数据删除、导出和隐私协议。
- 对上传文件做大小、类型、病毒扫描和解析沙箱。
- 对模型输出做敏感内容、隐私泄露和越权引用检查。

## 各端落地步骤

### 微信小程序

1. 用微信开发者工具打开 `apps/miniapp`。
2. 替换 `project.config.json` 的 `appid`。
3. 把 `utils/config.js` 的 API 地址改成 HTTPS 域名。
4. 后端配置 `WECHAT_MINIAPP_APP_ID` 和 `WECHAT_MINIAPP_APP_SECRET`。
5. 关闭生产环境 `INTERVIEW_AUTH_DEV_LOGIN_ENABLED`。
6. 验证简历上传、历史会话、隐私页和合法域名。
7. 如需提醒或商业化，补订阅消息和微信支付。

### iOS

1. 用 Xcode 打开 `apps/ios/InterviewAgent.xcodeproj`。
2. 本地 API 配置在 `apps/ios/InterviewAgent/Info.plist` 的 `InterviewApiBaseURL`。
3. 配置 Bundle ID、Signing、Capabilities。
4. 生产 API 必须走 HTTPS；当前 ATS 只给本地调试地址做例外。
5. 补 Apple 登录、文件选择器、推送、内购或外部支付策略。

### Android

1. 用 Android Studio 打开 `apps/android`。
2. 本地 API 配置在 `apps/android/app/build.gradle.kts` 的 `INTERVIEW_API_BASE_URL`。
3. 工程已提交 Gradle wrapper，命令行可用 `cd apps/android && ./gradlew tasks` 验证。
4. 使用 Retrofit/OkHttp 替换当前无依赖 `HttpURLConnection` 骨架。
5. 配置 Release 签名、应用市场渠道、隐私合规和崩溃监控。
6. 补文件选择器、推送、支付和本地缓存。

### HarmonyOS

1. 用 DevEco Studio 打开 `apps/harmony`。
2. 本地 API 配置在 `apps/harmony/entry/src/main/ets/config/AppConfig.ets`。
3. 配置网络权限、Release 签名和应用信息。
4. 生产 API 使用 HTTPS 域名。
5. 补华为账号、文件选择器、推送和支付。

## 里程碑

第一阶段：多端可用 MVP

- 登录。
- 行业选择。
- 简历上传和选择。
- 新建面试。
- 发送消息。
- 会话历史。

第二阶段：生产体验

- 流式输出。
- 语音输入和语音面试。
- 面试报告。
- 用户反馈和 badcase 回流。
- 端侧崩溃、性能、埋点监控。

第三阶段：商业化

- 会员订阅。
- 行业题库套餐。
- 简历多版本管理。
- 企业空间和团队管理。
- 管理后台和运营看板。
