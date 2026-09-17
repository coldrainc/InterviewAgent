# Interview Agent HarmonyOS

鸿蒙端使用 ArkTS + ArkUI。当前目录已经补齐 DevEco Studio / Hvigor 工程入口，可以直接用 DevEco Studio 打开 `apps/harmony`。

## 本地运行

1. 先启动后端 API：`./interview api`。
2. 用 DevEco Studio 打开 `apps/harmony`。
3. 等待 Hvigor 同步后运行 `entry`。
4. 本地默认 API：`http://127.0.0.1:8020`，配置在 `entry/src/main/ets/config/AppConfig.ets`。

发布前把 `AppConfig.apiBaseUrl` 改为单服务器部署的公网 HTTPS API 地址，
例如 `https://interview.example.com/api`。真机上的 `127.0.0.1` 指向手机本身，不能用于发布包。

## 端侧职责

- 登录、行业选择、面试会话、刷题训练、简历上传、历史记录和设置页。
- 不在端侧运行 RAG、Embedding 或大模型。
- 生产环境使用 HTTPS 后端域名，并配置网络权限和隐私声明。

## 当前能力

- `InterviewApiClient`：健康检查、账户、用户设置、行业列表、刷题题库、答题评分、简历库、历史会话、创建会话、发送消息。
- 正式邮箱登录/注册与本地凭证持久化；未登录时仅展示登录入口。
- `InterviewApiClient.streamMessage`：解析后端 SSE `message.done` / `message.error` 事件，异常时可回退普通消息接口。
- 五个一级入口：今日、面试、刷题、复习、我的；候选人/面试官在面试页内切换。
- 页面、产品状态、认证会话、模型与网络请求按职责拆分，不在单文件堆叠。
- 刷题：按训练类型筛题、初始化样题、提交答案、查看评分、参考答案、解析和复盘建议；互联网技术岗支持“力扣算法”分类。
- 简历：粘贴 Markdown / 文本简历、上传保存、选择当前简历和删除。
- 历史：列出历史会话、恢复上下文继续对话、删除历史。
- 我的：账号概览、简历管理与最近面试；不会展示访问令牌、租户标识或内部模型配置。

## 上线前必须补齐

- 华为账号或自有账号体系，后端校验登录凭证。
- Release 签名、Bundle Name、应用信息、隐私声明和权限弹窗。
- 生产 API 替换为 HTTPS 域名，并按应用市场要求声明网络用途。
- 原生文件选择器、上传进度、失败重试、隐私协议入口和数据删除入口。
- 崩溃采集、性能监控、日志脱敏和用户数据删除入口。
