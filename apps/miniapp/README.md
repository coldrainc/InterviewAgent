# Interview Agent Mini Program

微信小程序端使用原生小程序工程，核心 Agent/RAG/简历解析逻辑全部走后端 API。

## 本地预览

1. 用微信开发者工具打开 `apps/miniapp`。
2. 把 `miniprogram/utils/config.js` 里的 `apiBaseUrl` 改成可被手机或模拟器访问的后端地址。
3. 本地开发可临时关闭微信域名校验；上线前必须配置合法 HTTPS 域名。

发布包必须把 `config.apiBaseUrl` 改为单服务器部署的公网 HTTPS API 地址，
例如 `https://interview.example.com/api`；不要把 `127.0.0.1` 带入真机包。

## 当前能力

- 今日驾驶舱：服务端权威 Today、任务命令、幂等键、版本冲突恢复和离线只读缓存。
- 健康检查。
- 支持微信快捷登录和邮箱登录/注册，凭证只保存在小程序安全存储中。
- 拉取行业选项。
- 独立配置页：统一设置面试模式、行业、目标岗位、级别、面试目标和当前简历。
- 创建离线面试会话。
- 发送回答并展示 Agent 回复。
- 面试官工作台：按岗位生成结构化题单，覆盖技术、系统设计与表达协作维度。
- 刷题训练：按训练类型筛题、初始化样题、选择题/开放题作答、查看评分、解析和复盘建议；互联网技术岗支持“力扣算法”分类。
- 简历库：从微信聊天文件选择 PDF / Markdown，上传到后端保存，支持选择当前简历和删除。
- 历史会话：列表、恢复、删除。
- 复习计划：个性化计划生成、计划选择与每日打卡。
- 我的：账号、权益、简历、面试历史、隐私说明与安全退出。
- 隐私说明页：用于端内展示，正式上线仍需配置微信后台隐私协议。

一级导航以“今日”为默认入口；简历库保留为面试配置中的二级工作流，避免五个 Tab 分散日常执行路径。

## 上线前必须替换

正式上线必须关闭服务端开发登录：

```text
INTERVIEW_AUTH_DEV_LOGIN_ENABLED=false
```

还需要在微信公众平台完成：

- 设置正式 `appid`。
- 配置 request/uploadFile 合法 HTTPS 域名。
- 配置用户隐私保护指引。
- 配置小程序类目和服务内容。
- 如果做会员订阅或付费服务，接入微信支付并补充支付协议。

后端需要配置：

```text
WECHAT_MINIAPP_APP_ID=你的 appid
WECHAT_MINIAPP_APP_SECRET=你的 app secret
INTERVIEW_AUTH_TOKEN_SECRET=生产强随机密钥
INTERVIEW_API_AUTH_REQUIRED=true
```
