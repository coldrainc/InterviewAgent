# 账户、试用、积分和模型计费方案

## 目标

Interview Agent 面向真实用户上线时，需要从“本地工具”升级成“可运营服务”：

- 用户可以注册和登录。
- 新账号默认获得 2 次 Agent 生成试用机会。
- 试用用完后，用户通过充值获得积分。
- 每次 Agent 生成回复后统计 token，并按所选模型价格扣积分。
- 支持用户选择不同模型，后端按模型目录路由和计费。

## 已实现接口

```text
POST /auth/register          # 邮箱注册，默认发放 2 次试用
POST /auth/login             # 邮箱密码登录
POST /auth/dev-login         # 本地开发登录，也会创建账户
GET  /me                     # 当前用户和权益
GET  /account                # 当前账户余额
POST /account/recharge       # 开发/管理员人工入账，生产不允许用户直充
POST /payments/orders        # 创建待支付订单
POST /payments/webhook       # 已签名支付回调入账
GET  /metadata/models        # 可选模型和价格目录
POST /sessions               # 创建面试会话，支持 model_id
POST /sessions/{id}/messages # 正常扣试用/积分
POST /sessions/{id}/stream   # 流式接口也返回 usage
```

## 数据表

```text
user_accounts
  用户账户、邮箱、密码 hash、试用次数、积分余额

credit_ledger
  积分流水：充值为正数，消费为负数

recharge_orders
  充值订单：支付成功或管理员人工入账后写入，external_order_id 保证幂等

usage_records
  每次模型生成的 token、模型、成本、是否使用试用、idempotency_key
```

数据库迁移：

```bash
make migrate
```

## 积分计算

当前约定：

```text
1 USD 成本 = 100 积分
1 积分 = 1_000_000 micros
```

模型目录中保存：

```text
input_usd_per_1m
output_usd_per_1m
```

扣费公式：

```text
input_cost  = input_tokens  * input_usd_per_1m  * 100 / 1_000_000
output_cost = output_tokens * output_usd_per_1m * 100 / 1_000_000
total       = input_cost + output_cost
```

为了避免小数精度问题，数据库只存 `credit_balance_micros` 和 `cost_credits_micros`。

## Token 统计

优先级：

1. 如果模型供应商返回 usage metadata，使用真实 `input_tokens/output_tokens`。
2. 如果没有 usage metadata，使用本地估算器：
   - 中文按近似 1 字符 1 token；
   - 英文按约 4 字符 1 token；
   - 符号折算少量 token。

生产建议：

- OpenAI-compatible SDK 返回 usage 时直接入库。
- Anthropic/Gemini 等非 OpenAI-compatible provider 接入对应 SDK 后，把真实 usage 映射到 `TokenUsage`。
- 每月抽样对账 provider 账单和本地 `usage_records`，校准估算误差。

## 模型选择

`/metadata/models` 返回模型目录。`POST /sessions` 可以传：

```json
{
  "model_id": "gpt-5.5",
  "offline": false
}
```

当前公开模型目录不做“全厂商型号枚举”，只保留各能力类型的先进代表模型：

```text
默认通用：          gpt-5.5
最高质量：          gpt-5.5-pro
高性价比：          gpt-5.4-mini
长上下文深度分析：  claude-fable-5
多模态低延迟：      gemini-3.5-flash
高性价比推理：      deepseek-v4-pro
中文企业旗舰：      qwen3.7-max
代码与 Agent：      kimi-k2.7-code
```

旧模型和供应商备选模型仍保留在后端 `default_model_catalog()` 中，用于历史会话、账单回放、灰度和后台开关，但默认 `enabled=false`，不会出现在用户模型下拉框。

运行时支持分两层：

```text
OpenAI-compatible:
  openai, google(Gemini OpenAI-compatible endpoint), deepseek,
  alibaba(DashScope compatible-mode), volcengine(Ark), moonshot, xai, custom

Native LangChain:
  anthropic(langchain-anthropic)
```

可用环境变量：

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
GEMINI_API_KEY / GOOGLE_API_KEY
DEEPSEEK_API_KEY
DASHSCOPE_API_KEY
ARK_API_KEY
MOONSHOT_API_KEY
XAI_API_KEY
GATEWAY_API_KEY
```

没有 API key、依赖未安装或 provider 不支持时，后端会降级到 `ScriptedInterviewHarness`，仍会记录 usage。`GET /metadata/models` 会返回 `runtime_supported` 和 `runtime_integration`，前端可以据此展示“可调用 / 需配置 / 需开通”的状态。

生产建议把内置目录迁移成数据库表：

```text
model_pricing
  provider, model_id, display_name, category, runtime_integration
  input_price, output_price, currency, context_window
  enabled, visible, priority, notes
  effective_from, effective_to, price_version
```

上线后模型价格、可见性和默认模型应通过后台配置，不应依赖发版。

## 充值

当前 `POST /account/recharge` 只用于开发环境 mock 充值或管理员人工入账：

```json
{
  "amount_credits": "100",
  "payment_provider": "mock",
  "external_order_id": "order-001",
  "target_user_id": "email:candidate@example.com",
  "metadata": {
    "reason": "customer_support_adjustment"
  }
}
```

生产用户充值必须走支付平台回调：

- 前端调用 `POST /payments/orders` 创建 `pending` 订单，拿到 `external_order_id`。
- `payment_provider=alipay` 时，后端返回支付宝网页支付 `pay_url`，前端打开收银台。
- `payment_provider=wechat` 时，后端返回微信 Native 支付 `code_url`，前端在本地生成二维码。
- 支付平台完成支付后回调后端，后端验签/解密后把订单置为 `paid` 并入账。
- 通用支付回调 `/payments/webhook` 使用 `INTERVIEW_PAYMENT_WEBHOOK_SECRET` 校验 `X-Payment-Signature`，签名算法为 `HMAC-SHA256(raw_body)`，可传纯 hex 或 `sha256=<hex>`。
- 支付宝回调使用 `ALIPAY_PUBLIC_KEY` 验签；微信支付回调使用 `WECHAT_PAY_PLATFORM_CERT_PEM` 验签，并使用 `WECHAT_PAY_API_V3_KEY` 解密资源。
- 后端校验租户、用户、金额上限、订单状态、支付渠道和订单号格式。
- `recharge_orders(tenant_id, external_order_id)` 保证重复回调不会重复加余额。
- 只有支付成功的回调或管理员 token 能写 `recharge_orders` 和 `credit_ledger`。
- 客户端不能直接调用“加余额”的接口。

正式接入支付宝和微信支付前，需要分别在开放平台创建应用、完成商户进件，并配置 HTTPS 回调地址：

```text
支付宝异步通知：https://api.aivago.cn/payments/alipay/notify
支付宝同步返回：https://www.aivago.cn/
微信支付通知：https://api.aivago.cn/payments/wechat/notify
```

生产环境必须设置：

```text
INTERVIEW_ENV=production
INTERVIEW_API_AUTH_REQUIRED=true
INTERVIEW_AUTH_DEV_LOGIN_ENABLED=false
INTERVIEW_AUTH_MOCK_PROVIDER_LOGIN_ENABLED=false
INTERVIEW_ALLOW_MOCK_RECHARGE=false
INTERVIEW_PAYMENT_WEBHOOK_SECRET=<至少 24 字符强随机密钥>
INTERVIEW_AUTH_TOKEN_SECRET=<至少 32 字符强随机密钥>
INTERVIEW_ALLOWED_ORIGINS=https://your-domain.example
PUBLIC_WEB_BASE_URL=https://www.aivago.cn
PUBLIC_API_BASE_URL=https://api.aivago.cn

ALIPAY_APP_ID=<支付宝应用 app_id>
ALIPAY_PRIVATE_KEY=<应用私钥，支持 PEM 或去掉头尾后的 base64 文本>
ALIPAY_PUBLIC_KEY=<支付宝公钥，支持 PEM 或去掉头尾后的 base64 文本>
ALIPAY_GATEWAY=https://openapi.alipay.com/gateway.do
ALIPAY_NOTIFY_URL=https://api.aivago.cn/payments/alipay/notify
ALIPAY_RETURN_URL=https://www.aivago.cn/

WECHAT_PAY_APP_ID=<微信支付 appid>
WECHAT_PAY_MCH_ID=<微信支付商户号>
WECHAT_PAY_API_V3_KEY=<API v3 密钥，32 字节>
WECHAT_PAY_PRIVATE_KEY=<商户 API 证书私钥，支持 PEM 或去掉头尾后的 base64 文本>
WECHAT_PAY_CERT_SERIAL_NO=<商户 API 证书序列号>
WECHAT_PAY_PLATFORM_CERT_PEM=<微信支付平台证书 PEM，支持把换行写成 \n>
WECHAT_PAY_NOTIFY_URL=https://api.aivago.cn/payments/wechat/notify
```

部署后验证：

```bash
cd /opt/aivago/InterviewAgent
git pull
./scripts/deploy_server.sh all
curl https://www.aivago.cn/api/health
```

登录网页后进入账户中心，点击“支付宝”会打开收银台，点击“微信”会显示扫码二维码。支付完成后前端轮询 `GET /payments/orders/{external_order_id}`，订单变为 `paid` 后自动刷新积分。

## 扣费幂等

每次生成回复都会写 `usage_records`。后端会基于 `X-Request-ID`、会话 ID、事件类型、轮次和内容生成 `idempotency_key`，数据库唯一约束为：

```text
usage_records(tenant_id, idempotency_key)
```

客户端或网关重试同一个请求时应复用同一个 `X-Request-ID`，这样不会重复消耗试用次数或积分。

## 安全要求

- 生产开启 `INTERVIEW_API_AUTH_REQUIRED=true`。
- 密码使用 PBKDF2 hash 存储，后续可以替换为 Argon2/bcrypt。
- 充值必须走服务端支付回调，不能信任客户端上报金额。
- 所有扣费和余额变动必须写流水。
- 简历、会话、memory 都按 `tenant_id + user_id` 隔离，同租户不同用户不能互相读取。
- 对高价值模型设置单次最大 token、单日消费限额、异常消费告警。
- 管理后台才能调整余额，并必须审计操作者、原因和工单。

## 价格来源和维护

内置价格是工程默认运营目录，方便本地学习和端到端验证。上线前必须重新核对各供应商官方价格，并建议把价格表迁移成数据库配置或后台配置：

- OpenAI pricing
- Anthropic pricing
- Google Gemini pricing
- DeepSeek pricing
- 阿里云百炼 / DashScope pricing
- 火山方舟 / Doubao pricing
- Moonshot / Kimi pricing
- xAI pricing

价格变化不应发版才能生效；推荐后台维护 `model_pricing` 表，并记录价格版本。
