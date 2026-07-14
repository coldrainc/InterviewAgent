# Interview Agent Android

Android 端使用 Kotlin + Jetpack Compose。当前目录已经补齐 Gradle 工程，可以直接用 Android Studio 打开 `apps/android`。

## 本地运行

1. 先启动后端 API：`./interview api`。
2. 用 Android Studio 打开 `apps/android`。
3. 等待 Gradle Sync 完成后运行 `app`。
4. 模拟器默认 API：`http://10.0.2.2:8020`，配置在 `app/build.gradle.kts` 的 `INTERVIEW_API_BASE_URL`。

命令行验证：

```bash
./gradlew --version
./gradlew tasks
```

首次同步需要访问 Google Maven、Maven Central 和 Gradle Plugin Portal。当前工程已提交 Gradle wrapper；如果离线执行 `./gradlew tasks --offline`，本机没有 Kotlin / Android Gradle Plugin 缓存时会失败。

## 工程配置

- minSdk：26+
- compileSdk / targetSdk：35
- UI：Jetpack Compose
- Network：生产使用 HTTPS；当前骨架用 `HttpURLConnection` 减少依赖，后续可替换为 Retrofit/OkHttp。
- Release API 占位：`https://api.example.com`，上线前必须替换为真实 HTTPS 域名。

## 当前能力

- `InterviewApiClient`：健康检查、行业列表、创建会话、发送消息。
- `InterviewApiClient.devLogin`：本地开发签名 token；生产需替换为手机号/第三方登录。
- `InterviewApiClient.streamMessage`：解析后端 SSE `message.done` 事件。
- `ChatViewModel`：最小聊天状态机。
- `ChatScreen`：Compose 对话页。

## 上线前必须补齐

- 生产登录：手机号验证码、微信/Google/OAuth，后端校验 token。
- Release 签名、应用市场渠道配置、隐私合规弹窗。
- 简历文件选择器、上传进度、失败重试和本地缓存。
- 会话历史、当前简历选择、设置页和数据删除入口。
- 崩溃采集、性能监控、埋点和日志脱敏。
- Retrofit/OkHttp、证书固定或域名白名单策略按安全要求补齐。
