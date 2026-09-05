
## 1. 回答定位

这份文档按技术深挖准备，目标是在面试中能把问题讲完整：

- 先讲本质判断。
- 再讲系统架构。
- 再讲关键技术链路。
- 再讲风险和治理。
- 最后迁移到证券场景。

你的总定位：

> 我过去做的是实时复杂业务里的大前端基础设施：Hybrid 容器、跨端状态一致性、高频消息渲染、端侧生命周期和 AI Native 研发工程化。这些能力迁移到证券场景，就是财富 H5 / Hybrid 容器、行情高频渲染、交易链路稳定性、跨端一致性和组织级 Agent 研发体系建设。

## 2. 自我介绍

我过去主要做直播大前端和复杂端侧业务架构，经历横跨前端、客户端、跨端和 AI 工程化。

业务上，我做过开播链路、直播回放容器、小窗/画中画、开播 Toolbar、第三行和短触等项目。这些项目不是普通页面开发，背后涉及复杂生命周期、实时消息、组件扩展、配置降级、资源管理和稳定性治理。

技术上，我重点做过 Hybrid 容器化、Lynx 动态化、KMP 跨端和鸿蒙 ArkUI 接入。我的经验不是单纯使用某个框架，而是根据问题性质拆边界：

```text
动态页面 / 活动卡片
  -> Lynx / Hybrid

跨端业务语义 / 状态机 / 消息 / 埋点
  -> KMP

播放器 / 小窗 / 系统生命周期 / 强平台能力
  -> 原生

研发效率 / 知识沉淀 / 流程自动化
  -> AI Agent / RAG / MCP / Skill
```

最近我也在系统建设 AI Native 相关能力，包括 Agent、RAG、MCP、Context、Knowledge、Skill、Sandbox 和评测。我的理解里，AI Native 不是用 AI 写几段代码，而是把需求分析、上下文检索、方案设计、编码、测试、Review 和知识沉淀放进一个可执行、可观测、可评测的 Agentic Workflow。

证券业务我需要继续补充行情、交易、账户和风控领域知识，但工程问题有迁移性。直播有实时消息、高频 UI、复杂端侧生命周期和强稳定性；证券有行情 tick、盘口、K 线、交易链路、账户态和风控。两者都要求实时、稳定、低延迟、强上下文一致。

## 3. 为什么适合证券 AI Native 大前端

这个岗位需要的不是单点前端开发，而是几类能力的组合：

- 移动端 H5 / Hybrid / 容器框架。
- 股票行情和交易场景里的高频数据渲染。
- 大前端性能治理，包括启动、卡顿、内存、网络、功耗。
- 跨前端和客户端的系统架构能力。
- AI Native 研发流程建设能力。

我的匹配点在于，我过去的项目长期处在“复杂业务 + 多端 + 强实时 + 高稳定”的环境中。直播业务和证券业务不是同一个领域，但底层技术挑战可以映射：

| 直播经验 | 证券场景 | 技术共性 |
|---|---|---|
| 公屏、礼物、短触消息 | 行情 tick、盘口、逐笔成交 | 高频数据输入、合批、局部刷新 |
| 播放器首帧和卡顿 | 行情首屏、K 线加载 | 首屏速度、资源预加载、链路耗时 |
| 小窗 / PiP | 行情后台关注、自选股提醒 | 生命周期、功耗、资源降级 |
| Hybrid / Lynx 卡片 | 财富活动、投研卡片、开户引导 | 容器、JSB、通参、安全、白屏 |
| KMP 消息和状态 | 行情模型、交易状态、埋点口径 | 多端一致性、协议和字段治理 |
| AI Agent / RAG / MCP | 证券研发 Agent / Knowledge / Skill | AI Native 工程化、组织资产沉淀 |

所以我的回答重点不是“我做过直播”，而是：

> 我在直播里处理过实时复杂业务的大前端架构问题，并且可以把方法迁移到证券的行情、交易、Hybrid 和 AI Native 研发体系里。

## 4. 大前端跨端架构怎么讲

大前端跨端不是“一套代码跑所有端”，而是按问题性质拆边界。不同技术栈解决的问题不同，不能互相替代。

### 4.1 架构分层

```text
业务入口层
  -> H5 / Lynx / RN / Native / ArkUI / SwiftUI

容器和动态化层
  -> Hybrid Container
  -> WebView / LynxView / Popup
  -> schema / resource / JSB / globalProps

跨端业务逻辑层
  -> KMP commonMain
  -> Model / State / Action / ViewModel / Message parser / Event params

平台能力层
  -> Player / Storage / Router / Account / Auth / Notification / Chart / Trading capability

治理层
  -> Monitor / Trace / Gray / Fallback / Test / Review / AI Agent
```

### 4.2 RN、Lynx、KMP、原生怎么选

| 方案 | 本质 | 适合 | 不适合 |
|---|---|---|---|
| RN | JS 驱动 Native UI | 普通双端业务页面、页面级跨端 | 极高频渲染、强系统能力、重图表 |
| Lynx | 端内动态化模板渲染 | 活动页、运营卡片、投研卡片、财富 H5 动态化 | 长期重状态页面、交易主链路 |
| KMP | Kotlin 业务逻辑跨端 | 状态机、消息解析、埋点、模型、配置 | 强平台 UI、播放器、系统窗口 |
| 原生 | 平台能力直接实现 | 交易主链路、图表绘制、系统能力、安全能力 | 快速动态运营场景 |

### 4.3 证券里的选型

证券 App 可以这样拆：

```text
财富活动 / 投研内容 / 运营卡片
  -> Lynx / H5 / Hybrid

普通业务页面
  -> RN 或原生，取决于团队技术栈和性能要求

行情字段、交易状态、埋点口径
  -> KMP 或共享领域层

K 线、分时、盘口深度图
  -> Canvas / Skia / Native 图表

交易下单、账户、风控
  -> 原生 + 服务端强校验
```

### 4.4 为什么不能只用一种跨端方案

如果全部用 Hybrid，交易和行情核心链路性能、稳定性、安全边界会很难保证。

如果全部用原生，活动、投研、机构服务和运营页面迭代效率会低。

如果全部用 RN，动态下发、强端能力和高频行情图表仍会有边界。

如果全部用 KMP，UI 动态化和平台差异处理会变复杂。

所以成熟的大前端架构不是追求技术栈统一，而是追求边界清晰：

> 动态化归动态化，业务一致性归共享逻辑，强平台能力归原生，工程效率归 AI Native 和工具链。

## 5. Hybrid 容器设计

Hybrid 容器不是简单打开 WebView 或 LynxView。一个可用于证券业务的 Hybrid 容器必须同时解决路由、资源、上下文、通信、权限、生命周期、监控和降级。

### 5.1 总体架构

```text
schema / url / business entry
  -> Route Resolver
       解析 bid / host / path / query / scene
  -> Container Factory
       创建 WebView / LynxView / Popup / Native fallback
  -> Resource Loader
       离线包 / 缓存 / 在线资源 / fallback
  -> Context Injector
       user / account / market / stock / scene / app version
  -> JSB Registry
       common JSB / securities JSB / risk JSB
  -> Permission Guard
       login / account / trade / risk / schema whitelist
  -> Lifecycle Dispatcher
       create / load / show / hide / destroy / foreground / background
  -> Monitor
       load time / blank screen / JS error / JSB error / resource hit
```

### 5.2 路由层

路由层要解决：

- 这个 schema 属于哪个业务域。
- 应该用 WebView、Lynx、Popup 还是原生。
- 当前页面是否允许打开。
- 参数是否合法。
- 是否需要登录或账户态。
- 是否命中降级。

证券里要特别注意：

- 交易相关 schema 不能被任意 H5 调起。
- 账户相关页面要检查登录和账户态。
- 行情页面要校验 market / symbol。
- 投研和机构服务页面要处理权限差异。

### 5.3 资源层

资源加载要有明确优先级：

```text
memory cache
  -> disk offline package
  -> built-in fallback
  -> network
  -> native fallback
```

需要监控：

- 离线包命中率。
- 资源解析耗时。
- 模板加载耗时。
- 首屏耗时。
- 白屏率。
- JS runtime error。

如果资源加载失败，不能让用户停在白屏，需要：

- 展示 skeleton。
- 回退到本地兜底。
- 回退到 Native 页面。
- 给出可重试入口。

### 5.4 上下文注入

证券 Hybrid 页面需要的上下文通常包括：

- 用户态。
- 账户态。
- 交易权限。
- market。
- symbol。
- 页面来源。
- 风控状态。
- 设备和版本。
- AB / setting。

上下文不能只靠 schema 拼接，因为容器复用、页面切换、异步加载、登录态变化、账户切换都会导致参数过期。

更稳的方式：

```text
schema params
  -> route params
  -> container context
  -> current account / market / stock context correction
  -> globalProps
  -> JSB runtime context
```

### 5.5 JSB 设计

JSB 要按业务域分层：

```text
CommonJSB
  -> navigation / toast / logger / device

MarketJSB
  -> subscribeQuote / getSnapshot / openStockDetail

AccountJSB
  -> getAccountStatus / getRiskStatus

TradeJSB
  -> preCheckOrder / openTradePanel

ContentJSB
  -> openResearch / share / favorite
```

每个 JSB 都要定义：

- 入参 schema。
- 返回 schema。
- 是否需要登录。
- 是否需要账户态。
- 是否涉及交易权限。
- 是否允许在后台调用。
- 是否允许 H5 / Lynx 调用。
- 错误码。
- 监控事件。

### 5.6 权限和安全

证券容器比普通业务容器更强调安全。

JSB 调用链应该是：

```text
JSB call
  -> channel whitelist
  -> payload schema validation
  -> bid / host validation
  -> login check
  -> account check
  -> trade permission check
  -> risk control check
  -> execute native service
  -> structured result
```

不要把 token、完整账户信息、交易凭证暴露给 H5。前端只能表达意图，交易、账户、风控相关能力必须由端侧和服务端共同校验。

### 5.7 生命周期治理

容器生命周期：

```text
create
  -> load
  -> first screen
  -> show
  -> hide
  -> destroy
```

证券业务生命周期：

```text
login
  -> account selected
  -> market / symbol changed
  -> foreground / background
  -> trade permission changed
  -> logout
```

风险：

- 容器复用导致串账户。
- 异步 callback 回来时页面已销毁。
- H5 仍持有旧 symbol。
- 账户切换后页面继续显示旧资产。
- listener 未释放导致重复回调。

治理：

- show 时校正上下文。
- hide 时暂停高频订阅。
- destroy 时清理 listener、timer、callback。
- callback 返回时检查 alive 和 context version。
- 账户切换时刷新或重建上下文。

### 5.8 白屏排查

白屏要分阶段定位：

```text
schema parse
  -> route resolve
  -> container create
  -> resource load
  -> template decode
  -> JS execute
  -> context inject
  -> data request
  -> first render
  -> JSB callback
```

线上必须有：

- 分阶段耗时。
- 错误码。
- 页面 bid。
- resource version。
- user/account context 摘要。
- JS error。
- native container error。
- fallback 是否触发。

## 6. 行情高频数据渲染

行情不是普通列表数据。它有几个关键特征：

- 高频。
- 实时。
- 数据准确性要求高。
- 局部变化多。
- 弱网和重连复杂。
- UI 表现同时包含列表和图表。

### 6.1 总体链路

```text
Network
  -> WebSocket / 长连接 / SSE
  -> snapshot + incremental update
  -> sequence / timestamp check
  -> local quote store
  -> merge / dedupe / batch
  -> schedule UI update
  -> list / chart partial render
  -> monitor / fallback
```

### 6.2 快照 + 增量

行情页面不能只靠增量，也不能只靠轮询。

典型方式：

```text
initial snapshot
  -> 建立完整初始状态

incremental update
  -> 按 sequence 合并变化字段

reconnect snapshot
  -> 断线后重新校准
```

数据模型：

```text
QuoteSnapshot
  symbol
  price
  change
  changeRate
  volume
  amount
  bidAsk
  timestamp

QuoteDelta
  symbol
  changedFields
  sequence
  timestamp
```

### 6.3 合批和节流

错误方式：

```text
每条 tick
  -> setState
  -> render list
  -> draw chart
```

正确方式：

```text
tick stream
  -> buffer by symbol
  -> merge latest value
  -> flush by frame / interval
  -> update visible rows
  -> append chart point
```

关键判断：

- 数据接收频率可以高于 UI 刷新频率。
- 同一股票短时间多次更新，UI 只需要最终值。
- 不可见 item 只更新 store，不触发渲染。
- 图表只重绘变化区域或可视窗口。

### 6.4 自选股和榜单列表

列表优化：

- 虚拟列表。
- 稳定 key。
- item memo。
- 行内局部更新。
- 不可见 item 不渲染。
- 涨跌色轻量动画。
- 曝光批量上报。

RN 方案：

```text
FlatList / VirtualizedList
  -> initialNumToRender
  -> windowSize
  -> maxToRenderPerBatch
  -> getItemLayout
  -> React.memo item
  -> onViewableItemsChanged
```

Lynx 方案：

```text
first screen window
  -> cell reuse
  -> data chunk append
  -> itemMap by id
  -> partial update visible item
  -> native aggregate high-frequency events
```

### 6.5 K 线和分时图

K 线和分时图本质是高密度绘图，不适合用大量 DOM / View 节点。

推荐：

- Canvas。
- Native Canvas。
- Skia。
- WebGL。
- 平台原生图表。

拆层：

```text
Data Layer
  -> raw points
  -> sampling
  -> visible window

Coordinate Layer
  -> price -> y
  -> time -> x

Render Layer
  -> candle
  -> line
  -> volume
  -> grid
  -> crosshair

Interaction Layer
  -> pan
  -> pinch
  -> long press
  -> tooltip
```

优化：

- 只渲染可视窗口。
- 大数据降采样。
- 背景网格缓存。
- 十字光标独立图层。
- 缩放时只改变 viewport。
- 新点位增量绘制。
- 手势和绘制解耦。

### 6.6 网络稳定性

行情网络要处理：

- 心跳。
- 断线重连。
- 订阅恢复。
- 快照校准。
- 增量乱序。
- 数据过期。
- 弱网降级。

面试表达：

> 行情数据不能只追求刷新快，还要保证准确和可解释。断线后要用快照校准，增量要用 sequence 或 timestamp 处理乱序，弱网时要标注数据延迟，不能让用户误以为看到的是实时价格。

## 7. 长列表优化

长列表不是简单“少渲染”。它要处理窗口、复用、数据更新、资源加载、曝光、动态高度和生命周期。

### 7.1 RN 长列表

基础选型：

```text
ScrollView
  -> 少量内容

FlatList / VirtualizedList
  -> 普通长列表

SectionList
  -> 分组列表

FlashList / RecyclerListView / Native list
  -> 超大数据、复杂 item、高性能要求
```

关键参数：

- `initialNumToRender`。
- `windowSize`。
- `maxToRenderPerBatch`。
- `updateCellsBatchingPeriod`。
- `removeClippedSubviews`。
- `getItemLayout`。

item 层优化：

- `keyExtractor` 稳定。
- `renderItem` 稳定。
- item 组件 `React.memo`。
- 不在 `renderItem` 里创建复杂对象。
- item 只订阅局部状态。
- 图片固定尺寸。
- 动态高度缓存。

曝光：

- `onViewableItemsChanged`。
- viewability config。
- 批量上报。
- 去重。
- 不驱动 UI 大范围刷新。

什么时候下沉原生：

- item 内有播放器。
- 强手势。
- 极高帧率滚动。
- Surface / 图表 / 原生 SDK。
- RN 调参后仍不满足性能。

### 7.2 Lynx 长列表

核心原则：

```text
首屏少建节点
  -> 可见窗口
  -> cell 复用
  -> 数据分片
  -> 按 id 局部更新
  -> 图片延迟加载
  -> 曝光批量上报
```

不能做：

```text
setData({
  list: fullNewList
})
```

应该做：

```text
listIds
itemMap
changedItemIds
visibleWindow
```

直播或行情高频场景：

```text
native message
  -> filter
  -> aggregate
  -> batch event
  -> Lynx merge local data
  -> visible item partial update
```

复用风险：

- 旧图片残留。
- 旧动画继续跑。
- 旧点击 id 残留。
- 曝光按 cell 而不是业务 id 统计。
- 切账户 / 切股票后缓存未清。

## 8. AI Native 研发工程体系

AI Native 不是“用 AI 写代码”。它是把研发流程变成 Agent 可以参与的工程系统。

### 8.1 总体架构

```text
Requirement / User Goal
  -> Context Retriever
  -> Knowledge / RAG
  -> Planner
  -> Tool Registry / MCP
  -> Executor
  -> Sandbox
  -> Test / Review
  -> Trace / Evaluation
  -> Knowledge Update
```

### 8.2 Agent 状态机

```text
created
  -> planning
  -> retrieving
  -> tool_calling
  -> observing
  -> reflecting
  -> editing
  -> validating
  -> waiting_user
  -> completed / failed
```

关键点：

- 每一步有明确输入输出。
- 工具调用有 schema。
- 高风险动作要确认。
- 失败能归因。
- trace 可回放。
- benchmark 可评测。

### 8.3 Context / Knowledge / Skill

Context：

- 当前代码库。
- 项目规范。
- 业务背景。
- 历史决策。
- 当前任务状态。

Knowledge：

- 文档。
- 代码索引。
- FAQ。
- 需求说明。
- 排障经验。

Skill：

- 可复用流程。
- 固定任务模板。
- 工具调用规范。
- 领域约束。

证券里可以沉淀：

- 行情模块 Context。
- 交易链路 Context。
- Hybrid 容器 Skill。
- 性能排查 Skill。
- JSB 权限 Review Skill。
- K 线图表开发 Skill。

### 8.4 RAG 防幻觉

RAG 需要完整链路：

```text
query rewrite
  -> hybrid search
  -> rerank
  -> context packing
  -> answer generation
  -> citation
  -> claim verification
```

关键治理：

- 文档来源。
- 更新时间。
- owner。
- 版本。
- 权限。
- chunk 粒度。
- 引用。
- 不确定拒答。

### 8.5 MCP 和 Tool

MCP 可以理解成 Agent 连接外部系统的标准接口。

```text
Agent
  -> MCP Server
  -> Tools / Resources / Prompts
  -> Code / Docs / DB / Browser / CI
```

Tool：

- 执行动作。
- 有参数 schema。
- 有错误码。
- 有权限。
- 有 side effect 标记。

Resource：

- 读取上下文。
- 只读。
- 可引用。

Prompt：

- 固定任务模板。
- 沉淀经验。

### 8.6 安全和评测

Agent 安全：

- sandbox。
- tool allowlist。
- 文件读写权限。
- 高风险动作人工确认。
- token 最小权限。
- 审计日志。

评测指标：

- 任务完成率。
- 工具选择准确率。
- 参数正确率。
- 检索命中率。
- 引用支持率。
- 幻觉率。
- 测试通过率。
- 平均步数。
- 失败恢复率。

## 9. AI Native 业务落地与组织级推广

这个岗位更想要的 AI Native，不是“会使用 AI 工具”，而是能把 AI 能力做成业务研发体系的一部分，并且能在团队内大范围推广。你需要准备的重点是：

```text
AI Native = 场景选择 + 上下文工程 + Agent Workflow + Tool/Skill + Harness/Eval + 权限安全 + 推广运营
```

如果面试官问“你怎么理解 AI Native”，你应该回答：

> 我理解的 AI Native 是把 AI 从个人提效工具升级成组织级研发能力。它不是让每个人随便问模型，而是围绕真实业务流程建设 Context、Knowledge、Skill、Tool、Workflow、Harness 和评测体系，让 Agent 能在需求分析、方案设计、编码、测试、Review、上线检查和知识沉淀中稳定产生价值。最终目标不是 demo，而是可复制、可评测、可治理、可推广。

### 9.1 你需要学习什么

你需要补的不是单点模型知识，而是一套 AI 工程化能力。

#### 方向一：LLM 和 Agent 基础

必须理解：

- Prompt engineering。
- Function calling / tool calling。
- ReAct。
- Plan-and-Execute。
- Reflection。
- Multi-Agent。
- Agent 状态机。
- Tool Schema。
- Memory。
- 上下文窗口管理。
- 幻觉和不确定性。

需要能讲清楚：

```text
LLM
  -> 负责推理、生成、选择工具

Agent
  -> 负责带状态地规划、调用工具、观察结果、继续执行

Workflow
  -> 负责把复杂任务拆成稳定流程

Tool
  -> 负责连接真实系统

Evaluation
  -> 负责判断这个系统是否真的有效
```

#### 方向二：RAG 和 Context Engineering

组织级 AI Native 最重要的是上下文，不是 prompt。

要学习：

- 文档切分 chunking。
- embedding。
- BM25。
- hybrid search。
- rerank。
- context packing。
- citation。
- claim verification。
- 权限过滤。
- 版本和 owner。
- 知识过期治理。

面试表达：

> AI Coding 失败很多时候不是模型不够强，而是上下文不对。组织级 AI 能力的第一步是 Context Engineering：让 Agent 知道当前业务、代码结构、规范、历史决策、owner、测试方式和上线风险。

#### 方向三：MCP / Tool / Skill 体系

要学习：

- MCP Tool / Resource / Prompt 的区别。
- Tool 输入输出 schema。
- 错误码。
- side effect 标记。
- dry-run / execute 双阶段。
- 权限和审计。
- Skill 的触发条件、执行流程、边界约束。
- Tool Registry 和工具选择。

你要能讲：

```text
Resource
  -> 读取上下文，比如代码、文档、需求

Tool
  -> 执行动作，比如跑测试、创建文档、查接口

Prompt / Skill
  -> 固定经验和流程，比如代码评审、性能排查、Hybrid 接入
```

#### 方向四：Harness / Evaluation

这里的 harness 可以理解成：**用来驱动、复现、评测 Agent 或 AI Workflow 的测试执行框架**。

它不是单测那么简单，而是把一批真实任务变成可重复执行的 benchmark。

需要学习：

- benchmark dataset。
- golden answer。
- task fixture。
- trace replay。
- assertion。
- scoring。
- regression test。
- human review。
- A/B 对比。
- 自动聚合报告。

Harness 的目标：

```text
同一批任务
  -> 不同模型 / prompt / skill / workflow
  -> 自动执行
  -> 收集 trace
  -> 计算指标
  -> 输出质量报告
```

面试表达：

> 没有 harness，AI Native 很容易停留在“这次看起来效果不错”。有了 harness，才能评估某个 Agent、某个 Skill、某个 prompt 改动到底有没有提升，是否引入回归，是否能稳定覆盖真实研发任务。

#### 方向五：业务落地和推广

AI Native 能不能落地，核心看真实业务流程里有没有闭环。

要学习：

- 需求分析流程。
- 技术方案流程。
- 代码生成流程。
- 测试验证流程。
- Code Review 流程。
- 上线检查流程。
- 故障排查流程。
- 团队知识沉淀流程。

还要学习：

- 怎么选试点团队。
- 怎么定义 success metric。
- 怎么做灰度推广。
- 怎么收集反馈。
- 怎么把个体经验沉淀成 Skill。
- 怎么做培训和文档。
- 怎么避免大家把 AI 当玩具而不是流程工具。

### 9.2 怎么做一个 AI Native 业务落地系统

可以按六层建设。

#### 第一层：场景选择

不要一上来做大而全平台，要先选高频、低风险、可评测的场景。

优先场景：

- 需求理解和澄清。
- 技术方案初稿。
- 模块代码定位。
- 单测生成。
- Code Review checklist。
- Hybrid 页面接入模板。
- 性能排查信息收集。
- 上线风险检查。

不建议一开始做：

- 自动合并代码。
- 自动操作生产配置。
- 自动处理交易相关逻辑。
- 无人工确认的高风险发布。

证券团队里可以选：

```text
行情模块问题定位
Hybrid 容器接入
JSB 权限审查
K 线性能排查
交易页面上线 checklist
需求 PRD -> 技术方案
```

#### 第二层：Context 建设

给 Agent 准备上下文资产。

```text
业务 Context
  -> 行情、交易、账户、风控、财富活动

技术 Context
  -> Hybrid 容器、JSB、RN/Lynx/KMP、图表、性能规范

工程 Context
  -> 代码目录、构建命令、测试命令、owner、发布流程

历史 Context
  -> 常见故障、历史方案、Review 规则、线上事故
```

Context 要结构化：

- 适用范围。
- owner。
- 更新时间。
- 证据来源。
- 示例。
- 禁止项。
- 验证方式。

#### 第三层：Tool / Skill 建设

把高频动作做成工具，把高频流程做成 Skill。

工具例子：

- 搜索代码。
- 读取文档。
- 跑单测。
- 查构建结果。
- 生成测试用例。
- 查询接口定义。
- 拉取性能日志。
- 生成 Review 报告。

Skill 例子：

- Hybrid JSB 接入 Skill。
- 行情高频渲染排查 Skill。
- K 线性能优化 Skill。
- 交易安全 Review Skill。
- AI 生成技术方案 Skill。
- 上线 checklist Skill。

Skill 里要写清楚：

- 什么时候触发。
- 必须读取哪些上下文。
- 执行步骤。
- 禁止做什么。
- 需要什么验证。
- 产出格式。

#### 第四层：Agentic Workflow

把工具和 Skill 串成工作流。

示例：需求到技术方案。

```text
输入 PRD
  -> 识别业务域
  -> 检索相关 Context
  -> 读取历史方案
  -> 定位代码入口
  -> 生成技术方案
  -> 生成风险清单
  -> 生成测试建议
  -> 等待人工确认
```

示例：Hybrid 页面接入。

```text
输入页面需求
  -> 判断容器类型
  -> 生成 schema 设计
  -> 设计 globalProps
  -> 设计 JSB 权限
  -> 生成接入代码
  -> 生成白屏监控
  -> 生成测试用例
  -> Review checklist
```

示例：行情性能排查。

```text
输入卡顿问题
  -> 收集日志 / trace
  -> 判断数据频率
  -> 检查渲染范围
  -> 检查列表窗口
  -> 检查图表绘制
  -> 输出瓶颈归因
  -> 给出优化 patch / 方案
```

#### 第五层：Harness / Eval

建立评测框架，保证 Agent 能大范围推广。

Harness 结构：

```text
cases/
  hybrid_jsb_case_001
  market_render_case_002
  review_security_case_003

runner/
  run workflow
  collect trace
  collect artifacts

assertions/
  must read context
  must produce plan
  must not call dangerous tool
  must include tests
  must cite evidence

report/
  pass rate
  tool accuracy
  hallucination
  regression
```

评测指标：

- 任务完成率。
- 人工修改率。
- 工具调用准确率。
- 关键上下文命中率。
- 代码编译 / 测试通过率。
- Review 缺陷率。
- 平均耗时。
- 回归率。
- 安全违规率。

面试表达：

> 我会把 AI Native 的推广建立在 harness 上。每次改 prompt、改 skill、换模型，都必须跑同一批 benchmark，看任务完成率、测试通过率、Review 问题数、工具调用错误和安全违规是否变化。这样才能从“感觉有用”变成“可量化有用”。

#### 第六层：推广和运营

组织级推广不是发一个工具链接就结束。

推广路径：

```text
选 1 个高频场景
  -> 找 1 个试点团队
  -> 做 10-20 个真实 case
  -> 建 harness
  -> 做效果数据
  -> 沉淀 Skill
  -> 培训和文档
  -> 扩到更多团队
```

推广指标：

- 使用人数。
- 周活。
- 覆盖需求数。
- 节省时间。
- 生成方案采纳率。
- 代码采纳率。
- 测试生成采纳率。
- Review 问题下降。
- 线上问题下降。

### 9.3 类似 harness / Hermes 你应该怎么理解

如果面试官提到 harness，你可以按“评测执行框架”理解：

> harness 是把真实任务标准化、自动执行和评测的框架。它负责喂 case、跑 Agent、收 trace、验产物、打分和生成报告。没有 harness，就没法知道 Agent 是否稳定，也没法支撑组织级推广。

如果面试官提到类似 Hermes 这类平台化名字，不要强行假装知道内部实现，可以按“AI Native 平台 / Agent Runtime / Workflow 平台”来回答：

> 如果 Hermes 指的是类似 Agent Runtime 或 AI Workflow 平台，我会重点关注它解决了哪些问题：任务编排、上下文注入、工具调用、权限控制、执行沙箱、trace 记录、评测回放和团队级 Skill 分发。一个平台真正有价值，不是能不能调模型，而是能不能让不同业务线把自己的 Context、Tool、Skill 接进来，并用统一 harness 评测质量。

你可以补一句：

> 我没有必要把某个平台名字讲得很玄，我会从通用架构看：它是不是有 Runtime、Context、Tool、Workflow、Sandbox、Evaluation、Observability 和 Distribution。如果这些都有，就能支撑 AI Native 的规模化落地。

### 9.4 你需要怎么学习

建议按四周补齐。

#### 第一周：AI Agent 基础和工具调用

学习目标：

- ReAct。
- Plan-and-Execute。
- Function Calling。
- Tool Schema。
- Agent Loop。
- Memory。
- Error recovery。

实践任务：

```text
做一个小 Agent
  -> 输入需求
  -> 读取本地文档
  -> 生成方案
  -> 调工具检查文件
  -> 输出报告
```

#### 第二周：RAG / Context

学习目标：

- chunking。
- embedding。
- BM25。
- hybrid search。
- rerank。
- citation。
- claim verification。

实践任务：

```text
把 interview 文档做成知识库
  -> 切 chunk
  -> 建索引
  -> query 检索
  -> rerank
  -> 生成带引用回答
```

#### 第三周：Workflow / Skill

学习目标：

- workflow 编排。
- skill 设计。
- 多步骤任务状态机。
- dry-run / execute。
- 权限和审计。

实践任务：

```text
设计 3 个 Skill
  -> Hybrid 接入 Skill
  -> 高频渲染排查 Skill
  -> 技术方案生成 Skill
```

每个 Skill 要包含：

- 触发条件。
- 输入。
- 读取上下文。
- 执行步骤。
- 输出。
- 验证。
- 禁止项。

#### 第四周：Harness / 推广

学习目标：

- benchmark。
- case 设计。
- trace replay。
- scoring。
- regression。
- report。
- rollout。

实践任务：

```text
给 3 个 Skill 各设计 5 个 case
  -> 跑一次 baseline
  -> 改 prompt / 改流程
  -> 再跑一次
  -> 对比指标
  -> 生成报告
```

### 9.5 你可以怎么讲“我会怎么做”

完整回答：

> 如果我来做证券大前端 AI Native 落地，我不会先做一个泛用聊天机器人。我会先选一个高频、可控、可评测的研发场景，比如 Hybrid 页面接入、行情性能排查、交易页面 Review checklist。  
> 第一阶段做 Context，把行情、交易、Hybrid 容器、JSB 权限、性能规范和历史问题整理成结构化知识。  
> 第二阶段做 Tool 和 Skill，把查代码、读文档、跑测试、生成方案、做 Review 这些动作标准化。  
> 第三阶段做 Workflow，把需求分析、方案生成、编码、测试、Review 串起来，关键节点保留人工确认。  
> 第四阶段做 harness，把真实 case 变成 benchmark，每次改模型、prompt 或 Skill 都能评测任务完成率、上下文命中率、测试通过率、Review 缺陷率和安全违规率。  
> 第五阶段再推广，从一个团队一个场景开始，用数据证明有效，再沉淀成组织级 Knowledge 和 Skill。

### 9.6 面试官可能追问的问题

#### Q：AI Coding 很多时候生成代码不可用，你怎么保证质量？

回答：

> 我不会只看生成结果，而是把质量控制前移和后移。前移是 Context 和约束，让 Agent 先读业务规范、代码结构、接口和测试方式；后移是验证和 Review，生成后必须跑编译、单测、lint、静态检查和 checklist。中间还要有 trace，知道它用了什么证据、调了什么工具、为什么做这个改动。

#### Q：怎么把个人 AI 经验推广到团队？

回答：

> 个人经验要变成团队能力，必须沉淀成 Skill、Context 和 Harness。比如某个同学很会排查 Hybrid 白屏，就把他的排查路径拆成步骤，写成 Skill；把相关代码、日志、错误码做成 Context；再设计一批历史白屏 case 做 harness。这样别人不是学习他的口头经验，而是直接复用一套可执行流程。

#### Q：如何判断 AI Native 真正产生业务价值？

回答：

> 要看业务和工程指标。业务侧看需求交付周期、问题响应时间、线上故障恢复时间；工程侧看方案生成采纳率、代码采纳率、测试通过率、Review 问题数、返工率、工具调用成功率。只看调用次数没有意义，必须看产物是否被采纳，质量是否稳定，风险是否下降。

#### Q：AI Agent 做交易相关代码会不会有风险？

回答：

> 会有，所以交易相关不能直接让 Agent 自动执行高风险动作。Agent 可以参与需求理解、代码定位、测试生成、Review checklist 和风险分析，但涉及交易逻辑、风控、生产配置和发布动作，必须有权限控制、人工确认、审计和回滚。AI Native 不是放大权限，而是在可控边界里提效。

#### Q：证券大前端最适合先落地哪个 AI 场景？

回答：

> 我会优先选低风险但高频的研发场景，比如 Hybrid 容器接入、JSB 权限 Review、行情性能排查、技术方案生成和测试用例生成。这些场景上下文相对明确，产物容易验证，也容易沉淀成 Skill。交易主链路自动改代码这种高风险场景应该后置。

### 9.7 你要形成的核心认知

你最后要把 AI Native 讲成这句话：

> AI Native 的难点不是调模型，而是把模型、上下文、工具、流程、评测和权限治理接到真实业务研发链路里。真正能规模化推广的能力，一定是有 Context、有 Skill、有 Workflow、有 Harness、有指标、有安全边界的工程系统。

## 10. KMP 在 iOS / HarmonyOS 怎么运行

KMP 在非 Android 平台不是跑 JVM，也不是 JS 解释执行，而是编译成目标平台 native 产物。

### 9.1 iOS

```text
commonMain + iosMain
  -> Kotlin/Native
  -> framework / xcframework
  -> Xcode 引入
  -> Swift / OC wrapper
  -> SwiftUI / UIKit 消费
```

逻辑共享：

```text
KMP ViewModel
  -> StateFlow / callback
  -> Swift wrapper
  -> ObservableObject / async sequence
  -> SwiftUI / UIKit render
```

Compose 共享 UI：

```text
KMP @Composable
  -> ComposeUIViewController
  -> iOS UIViewController 层级承载
```

UIKitView 的方向：

```text
KMP @Composable
  -> UIKitView(factory = { UIView() })
  -> Compose 布局
  -> UIView 按 UIKit 机制绘制
```

### 9.2 HarmonyOS

```text
commonMain + ohosArm64Main
  -> Kotlin/Native
  -> HarmonyOS native 产物
  -> ArkTS bridge / service
  -> ArkUI 消费 State / Effect
```

逻辑共享：

```text
KMP ViewModel
  -> RenderState
  -> ArkTS adapter
  -> ArkUI @State
  -> build() render
```

Compose 共享 UI：

```text
KMP @Composable
  -> Compose Runtime
  -> ArkTS service 创建 ComponentContent
  -> ArkUIViewTopLayer / ArkUIComponentContent
  -> ArkUI 页面承载
```

重点：

- KMP 负责业务语义。
- ArkUI / UIKit 负责最终 UI。
- wrapper 负责类型、生命周期、线程和平台能力。

## 11. React / Vue / Web 基础

JD 明确要求 JS/CSS/HTML/DOM、React/Vue、Webpack/Vite，所以这部分不能只停留在会用。

### 10.1 React

需要能讲：

- JSX 本质是 `React.createElement` 或编译后的 element 描述。
- Fiber 是可中断的虚拟栈帧和任务单元。
- Reconciler 负责 diff。
- Commit 阶段执行 DOM / Native 更新。
- hooks 通过 fiber 链表记录状态。
- setState 会调度更新，不一定同步执行。

性能优化：

- 状态局部化。
- memo。
- useMemo / useCallback。
- key 稳定。
- 避免大组件重渲染。
- 虚拟列表。

### 10.2 Vue

需要能讲：

- 响应式系统。
- dependency tracking。
- effect。
- scheduler。
- template compile。
- virtual DOM。
- patch。

Vue 性能优化：

- 合理拆组件。
- 避免大对象响应式。
- computed 缓存。
- keep-alive。
- v-memo / v-once。
- 虚拟列表。

### 10.3 Webpack / Vite

Webpack：

- dependency graph。
- loader。
- plugin。
- chunk。
- tree shaking。
- code splitting。

Vite：

- dev 阶段利用 ESM。
- 依赖预构建。
- esbuild。
- production 用 Rollup。
- HMR 更轻。

证券场景：

- 页面首屏资源拆包。
- 投研 / 活动低优先级资源懒加载。
- 行情核心资源优先加载。
- 大图表库按需加载。
- 监控 bundle size。

## 12. 安全和权限

证券业务的安全优先级高于普通内容业务。

### 11.1 Hybrid 安全

必须做：

- schema 白名单。
- host / bid 校验。
- JSB 白名单。
- 参数 schema 校验。
- 登录态校验。
- 账户态校验。
- 交易权限校验。
- 风控校验。
- 敏感数据脱敏。
- 调用审计。

交易类能力不能让 H5 直接拿底层能力，只能表达意图：

```text
H5 intention
  -> JSB request
  -> native permission check
  -> server risk check
  -> user confirmation
  -> execute
```

### 11.2 前端安全

需要准备：

- XSS。
- CSRF。
- CSP。
- URL 校验。
- open redirect。
- token 存储。
- WebView 注入风险。
- JSB 滥用风险。

### 11.3 AI Agent 安全

- 工具权限最小化。
- 高风险工具确认。
- 读写分离。
- sandbox。
- token 不进 prompt。
- 审计 trace。
- 输出敏感信息过滤。

## 13. 性能优化完整框架

性能优化不是少渲染，而是全链路治理。

```text
数据层
  -> 去重 / 合批 / 快照增量 / 缓存

调度层
  -> 节流 / 防抖 / 按帧刷新 / 优先级

状态层
  -> 局部状态 / selector / 避免大 store

渲染层
  -> 虚拟列表 / 局部 diff / Canvas / Native

资源层
  -> 图片缓存 / 预加载 / 懒加载 / 释放

网络层
  -> 长连接 / 重试 / 弱网 / 降级

生命周期层
  -> 前后台 / 页面销毁 / listener 清理

监控层
  -> 首屏 / 卡顿 / 内存 / 白屏 / 错误码 / 耗电
```

结合你的项目：

- 小窗：播放器资源复用、前后台、功耗、video 降级 audio。
- 回放容器：Hybrid 按需加载、状态一致性、JSB 收口、退出清理。
- 短触：消息聚合、队列、临态、曝光节流、降级。
- KMP：状态机共享、消息解析一致、埋点字段统一。

## 14. 项目难点回答

### 13.1 Hybrid 容器难点

难点不是打开页面，而是统一上下文、JSB、生命周期和安全。

直播里容器复用或切房处理不好会串房；证券里同样可能串账户、串股票、串交易上下文。所以方案应该是：

```text
container context
  -> show 时校正
  -> JSB 从 context 取能力
  -> async callback 检查 alive
  -> destroy 清 listener
```

### 13.2 KMP 难点

难点不是把代码放到 commonMain，而是判断边界。

适合：

- 状态机。
- 消息解析。
- 埋点。
- Model。
- Setting。

不适合：

- 播放器。
- 小窗。
- 系统权限。
- 强平台 UI。

### 13.3 高频渲染难点

难点是数据频率和 UI 承载能力不一致。

```text
high-frequency data
  -> filter
  -> aggregate
  -> dedupe
  -> schedule
  -> partial render
```

### 13.4 AI Native 难点

难点是可靠性和可控性。

```text
LLM output
  -> evidence
  -> tool execution
  -> sandbox
  -> test
  -> review
  -> trace
  -> evaluation
```

## 15. 反问问题

可以反问：

1. 证券大前端目前 Hybrid 容器主要承载哪些页面，财富活动、投研内容还是交易辅助更多？
2. 行情核心模块目前更多是 Web、Native 还是混合渲染？K 线和分时图的性能瓶颈在哪里？
3. 团队的 AI Native 研发体系目前是个人 AI Coding 为主，还是已经有组织级 Agent / Knowledge / Skill 平台？
4. Agent 在研发流程里最希望先解决需求分析、代码生成、测试、Review 还是上线检查？
5. JSB 权限和交易安全现在是怎么治理的？
6. 这个岗位更希望先解决业务交付问题，还是先建设基础设施？

## 16. 最终收束

如果面试官问“你最大的匹配点是什么”，可以这样回答：

> 我最大的匹配点是横跨业务复杂度、大前端跨端和 AI Native 工程化。证券场景需要的不只是写页面，而是把财富 H5、Hybrid 容器、行情高频渲染、交易稳定性和 AI 研发提效放在一个架构体系里看。  
> 我过去在直播里处理过实时消息、复杂生命周期、跨端一致性、Hybrid 容器和性能治理，也系统准备了 Agent、RAG、MCP、Context、Skill 这些 AI Native 方向。证券业务我会继续补领域知识，但从工程方法上，我能比较快进入状态并承担复杂问题的端到端解决。
