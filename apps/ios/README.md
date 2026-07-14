# Interview Agent iOS

iOS 端使用 Swift + SwiftUI。当前目录已经补齐最小 Xcode 工程，可以直接用 Xcode 打开 `InterviewAgent.xcodeproj` 进行本地调试和继续开发。

## 端侧职责

- 登录、简历上传、行业选择、面试会话、历史记录和设置页。
- 不在端侧调用大模型，不保存完整简历明文。
- 所有 AgentLoop、RAG、Embedding、Memory、Search 逻辑都走后端。

## 本地运行

1. 先启动后端 API：`./interview api`。
2. 用 Xcode 打开 `apps/ios/InterviewAgent.xcodeproj`。
3. 选择 iPhone 模拟器运行 `InterviewAgent` target。
4. 本地默认 API：`http://127.0.0.1:8020`，配置在 `InterviewAgent/Info.plist` 的 `InterviewApiBaseURL`。

## Xcode 配置

- iOS Deployment Target：17.0+
- Bundle Identifier：当前是 `com.example.interviewagent`，上线前按 Apple Developer 账号修改。
- Signing：上线前配置 Team、证书、Provisioning Profile。
- Network：生产环境只允许 HTTPS API 域名；当前 ATS 只给 `127.0.0.1/localhost` 做本地调试例外。

## 当前能力

- `InterviewApiClient`：健康检查、行业列表、创建会话、发送消息。
- `InterviewApiClient.devLogin`：本地开发签名 token；生产需替换为 Apple 登录或自有账号登录。
- `InterviewApiClient.streamMessage`：解析后端 SSE `message.done` 事件。
- `ChatViewModel`：最小聊天状态机。
- `ChatView`：SwiftUI 对话页。

## 上线前必须补齐

- Apple 登录 identity token 校验，或接入自有账号体系。
- 简历文件选择器、上传进度、失败重试、大小和类型限制提示。
- 会话历史、当前简历选择、用户设置和隐私协议入口。
- 崩溃采集、埋点、日志脱敏、数据删除入口。
- App Store 隐私清单、加密合规和审核说明。
