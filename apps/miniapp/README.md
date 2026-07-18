# Interview Agent Mini Program

微信小程序端使用原生小程序工程，核心 Agent/RAG/简历解析逻辑全部走后端 API。

## 本地预览

1. 用微信开发者工具打开 `apps/miniapp`。
2. 把 `miniprogram/utils/config.js` 里的 `apiBaseUrl` 改成可被手机或模拟器访问的后端地址。
3. 本地开发可临时关闭微信域名校验；上线前必须配置合法 HTTPS 域名。

## 当前能力

- 健康检查。
- 微信登录优先：`wx.login -> /auth/wechat/login`；本地开发失败时回退 `devLogin`。
- 拉取行业选项。
- 独立配置页：统一设置面试模式、行业、目标岗位、级别、面试目标和当前简历。
- 创建离线面试会话。
- 发送回答并展示 Agent 回复。
- 简历库：从微信聊天文件选择 PDF / Markdown，上传到后端保存，支持选择当前简历和删除。
- 历史会话：列表、恢复、删除。
- 我的：登录状态、服务状态、隐私说明入口、清除本地登录。
- 隐私说明页：用于端内展示，正式上线仍需配置微信后台隐私协议。

## 上线前必须替换

当前 `devLogin` 只适合本地开发。正式上线应关闭：

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
