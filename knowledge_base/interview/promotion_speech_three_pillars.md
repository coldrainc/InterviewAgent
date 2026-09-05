# 项目技术总览 · 四个方向

本文档汇总四个技术方向的项目内容：开播链路架构、Hybrid 容器化基础、KMP 跨端、StockAgent（AI Agent + RAG）。每个方向按「背景问题 → 架构设计 → 关键技术决策 → 技术要点」组织，聚焦工程实现本身。

---

# 方向一：开播 —— 复杂业务链路的架构编排

## 背景问题

开播不是一个单一功能，而是一条**强状态、强生命周期、多业务并发**的复杂链路：从相机预览、网络测速、美颜贴纸，到点击开播、推流、直播中的礼物/连麦/小游戏互动，再到关播页——每个阶段的组件、权限、资源都不同。若逻辑散落，会迅速演变成不可维护的巨石代码。

核心目标：用一套统一的编排框架，让所有开播业务能力「可插拔」接入。

## 三层架构设计

### ① 编排中枢层 —— BroadcastCoreController
整条链路唯一的 owner，持有会话状态机 `BroadcastSession` 与四个子控制器：
- `PreviewController`（预览）/ `LiveController`（开播中）/ `CloseController`（关播）——对应三个阶段
- `StreamController`（推流/相机）——横切能力
- 所有控制器通过 `context.bindController()` 注册进统一的 **LiveContext 控制器总线**，实现跨组件按需取用、避免层层传参。

### ② 生命周期任务框架 —— BroadcastLifecycleTaskManager
把「开播过程中要跟随生命周期跑的逻辑」抽象成 `IBroadcastLifecycleTask`，框架统一分发时机：
`aboutToAppear / onShow / onHide / onForeground / onBackground / onPageChange / onDestroy`。
- 任务**按 priority 有序注册**、**按 scene 过滤**，退场时统一 `onDestroy` 清理。
- 价值：新增一个跟随生命周期的能力（耳返、录制、状态面板），只要实现一个 Task 注册进来，**核心控制器零改动**。

### ③ 组件化布局层 —— BroadcastElementManager + Tetris
UI 不写死，而是把每个功能做成一个 **Element**（相机、手势、公屏、toolbar、贴纸、礼物盘、连麦坑位、小游戏背景……），注册到 **Tetris 分层布局引擎**，按竖屏/横屏、预览/开播/关播 scene 动态挂载卸载。
- 大量 Element 通过 `serviceManager` 从**其它业务线服务**（礼物、小游戏、连麦、互动）注入——开播模块只负责编排坑位，不侵入各业务实现。

## 关键设计决策

- **状态机驱动而非布尔标志**：用 `BroadcastSession` + `LiveLifecycleState` 管理阶段流转，`launchPreview → launchLive → onLiveEnd` 每步都有明确准入校验（权限、媒体房拦截、重复启动拦截）。
- **主动关闭组件复用**：开播页 `TetrisConfig.reusedConfig.enable = false`——开播页场景复杂且复用外层 context，主动关掉复用池，避免难查的状态污染。
- **稳定模式 + 开关灰度**：新能力（如飘赞动画 `broadcastLikeTetrisEnable`）都用 setting 开关包裹，线上出问题可秒级回滚，不需要发版。
- **对齐 Android 语义 + 防御性容错**：异常关播（杀进程退出）重进预览页先清理变声选中态；返回键在直播中拦截、录制中提示——对齐 Android 行为并补齐鸿蒙侧边界。

## 技术要点小结

一套让所有开播业务可插拔接入、可灰度回滚、可跨端对齐的编排框架，承载了相机、推流、美颜贴纸、连麦、小游戏、礼物、公屏等十几条业务线的接入。

## 深入追问准备

**Q：三个阶段（预览/开播/关播）之间是怎么切换的？切换时组件怎么处理？**
阶段切换由 `BroadcastCoreController` 驱动，核心是 scene 变更 + 布局重挂载。`launchPreview()` 里 `executeStage(BroadcastPageStage.PREVIEW)` + `onPageChange(scene)`，`launchLive()` 做准入校验后切到 LIVE scene。Element 层按 scene 过滤挂载：预览 Element（背景/toolbar/startLive/tab）在 LIVE scene 卸载，开播 Element（公屏/礼物盘/连麦/贴纸）挂载。生命周期任务同样按 scene 过滤（`getTasks()` 用 `supportInScene` 筛选），不属于当前 scene 的任务 `destroyTask` 清理。

**Q：LifecycleTask 和 Element 有什么区别？为什么要分成两套？**
Element 是「有 UI 的组件」（挂到 Tetris 布局树，有视图节点）；LifecycleTask 是「无 UI 的逻辑单元」（耳返控制、录制状态、状态面板轮询等，只需要跟随生命周期跑）。分开是职责分离：UI 归布局引擎管理挂载/复用，纯逻辑归任务框架管理时机分发。一个功能可以只有 Task（如耳返）、只有 Element（如纯展示背景），或两者都有。

**Q：controllers 总线（LiveContext.bindController）会不会导致全局耦合、难以测试？**
不会。它是「按接口 key 注册 + 按需取用」的服务定位模式，不是全局单例。key 是强类型的 `liveBroadcastControllers.XXX`，取用方拿到的是接口而非实现；controller 的生命周期绑定在 context 上，context 销毁时统一释放。相比构造函数层层传参，它解决的是「深层组件要用顶层能力」的传递问题，且每个 controller 可单独 mock 注入做测试。

**Q：为什么开播页要主动关闭 Tetris 组件复用？复用不是性能更好吗？**
复用池的收益在「同类组件大量重复创建」（如列表 item）。开播页是单例长驻页面、组件种类多但每种通常 1 个实例，复用收益极低；反而复用池会缓存并重挂载组件，在开播页「复用外层 context + 阶段切换频繁挂卸」的场景下，容易把上一场/上一阶段的残留状态带到新实例，引入难查的状态污染。这是拿「基本可忽略的性能」换「确定性和可维护性」的取舍。

**Q：并发/异常场景怎么保证不出问题？比如快速开播又关闭、杀进程恢复。**
几个防线：① `session.launchLiving` 标志位拦重复 `launchLive`；② 媒体房 `createInfo.isMedia` 直接拦截不允许开播；③ 权限未就绪时走 `requestPermission` 而非硬开；④ 异常关播（杀进程退出）重进预览页先 `clearSoundEffectSelection` 清理残留；⑤ 返回键在 LIVE scene 拦截并走 `onLiveEnd`，录制中额外 toast 阻断。

---

# 方向二：Hybrid 容器化基础 —— 跨技术栈的统一基础设施

## 背景问题

直播间大量活动、玩法、营收页面由前端（Lynx / H5）动态下发，而非 Native 写死。这要求客户端提供一套**稳定、统一、可复用的 Hybrid 容器**：
- 同时承载 **Lynx 卡片**和 **Web 卡片**两种技术栈；
- 打通 Native ↔ 前端的**双向通信**（JSB 能力调用、事件收发）；
- 保证容器**生命周期正确、无内存泄漏**——这是历史上最容易出问题的地方。

## 架构设计

### ① 统一容器抽象（跨端一致的对外接口）
把 Lynx/Web 容器统一抽象为 `KmpAnniexLynxCard` / `KmpAnniexWebCard` 两个组件，对外暴露一致的参数模型（schema、initialData、globalProps、lifecycleListener、bridgeRegistryList）和统一的加载状态机（`LOADING / SUCCESS / ERROR / FORBIDDEN / RUNTIME_READY`）。业务方接入时只关心 schema 和数据，不关心底层是 Lynx 还是 Web。

### ② Controller-Delegate 双向通信解耦
容器通信采用 **Controller + Delegate** 模式：
- 业务侧持有 `Controller`（`sendEvent` / `sendEventBroadcast` / `updateGlobalProps` / `registerEvent` 等稳定 API）；
- 容器侧实现 `Delegate`，把这些调用翻译成具体容器能力（如 Lynx 的 `sendJsEvent`、Web 的 `load`）；
- 中间用 **EventSubscriptionRegistry** 管理事件订阅，`onBind` 时 sync、`onUnbind` 时 clear。
- 价值：业务代码与容器实现彻底解耦，未来换容器实现，业务侧无感知。

### ③ JSB 能力矩阵（Native 能力下沉给前端）
围绕容器，沉淀了一整套 **JSB Method 能力矩阵**（分享、登录、用户信息、礼物、评论、上传、埋点、状态订阅等上百个 Method），以及 **StateProvider 状态桥**（Room / User / Setting / Message 等实时状态推给前端）。前端页面因此能像 Native 一样消费直播间的完整能力与实时状态。

## 关键设计决策

- **加载时机收口，对齐时序**：首次 `load` 必须推迟到 view 真正 attach 到父容器之后才触发——否则 AnnieX 的 `onPageEnd` / `firstScreen` 等生命周期回调会因 view 还在构造期就被触发而丢失。对齐旧 Widget「先 addView 再 loadUrl」的行为。
- **内存泄漏根治（DisposableEffect 清理顺序）**：容器销毁时严格按 **先 unbindController（解绑 delegate）→ 再 release 卡片 → 最后 removeView** 的顺序清理。先解绑确保 release 引发的回调不会再投递到已释放的 card，也避免 controller 残留 delegate/registry/listener 引用链导致泄漏。
- **去重防重复 load**：用进程级 `WeakHashMap` 对已 load 的卡片去重，且刻意不用 `View.setTag(int)`——该 API 要求 key 是 application 资源 id，随手用 hashCode 会直接 crash。
- **全链路防御性容错**：所有容器调用用 `runCatching` 包裹并打 warn 日志，静默失败可观测；空 `bridgeRegistryList` 场景做兜底，避免 NPE crash。

## 技术要点小结

一套技术栈无关、通信解耦、生命周期安全的容器基础设施，支撑了活动 Banner、营收玩法、连麦动态框等大量业务，并系统性根治了历史上最难缠的容器内存泄漏问题。

## 深入追问准备

**Q：Controller-Delegate 模式具体怎么解耦？业务侧调 sendEvent 到前端收到，中间发生了什么？**
业务侧只持有 `Controller`（稳定 API：`sendEvent`/`sendEventBroadcast`/`updateGlobalProps`/`registerEvent`）。`Controller` 内部持有一个可替换的 `Delegate`——容器创建时 `bindDelegate`，销毁时 `resetDelegate`。以 Lynx 为例：`Controller.sendEventBroadcast(name, params)` → `Delegate.sendEventInternal` → `JSONObject(params)` → `card.sendJsEvent(name, json)` 投递给前端。反向的前端→Native 事件通过 `EventSubscriptionRegistry` 注册的 listener 回调。业务代码全程不接触 `HybridCard`，因此底层换容器（AnnieX→其他）业务无感知。

**Q：为什么首次 load 一定要等 view attach 之后？不等会怎样？**
`HybridCard` 的 `onPageEnd`/`onLynxFirstScreen` 等生命周期回调是在 load 过程中触发的。如果在 view 还处于 Compose `ViewFactoryHolder` 构造期（未 attach 到窗口）就 load，这些回调会「提前」触发，而此时监听链路还没就绪，导致**首屏/加载成功事件丢失**，表现为卡片一直 loading 或埋点缺失。所以我用 `isAttachedToWindow` 判断：已 attach 立即 load，未 attach 则挂 `OnAttachStateChangeListener` 等 `onViewAttachedToWindow` 再 load——对齐旧 Widget「先 addView 再 loadUrl」的隐含时序契约。

**Q：内存泄漏的引用链具体长什么样？为什么清理顺序不能反？**
泄漏链是 `Controller → Delegate → HybridCard(+registry+listener)`。如果先 `release()` 再解绑：release 会触发 `onRelease`/回调，此时 delegate 还绑着，回调会投递到「正在/已释放」的 card，可能 NPE 或访问已回收资源；而且 controller 仍持有 delegate，delegate 持有 card，card 无法被 GC。所以必须**先 `unbindController`（`resetDelegate` + `registry.clear()` 断链）→ 再 `card.release()` → 最后 `removeView`**。顺序反了链断不干净。

**Q：WeakHashMap 去重那里，为什么不能用 View.setTag？**
两个原因：① `setTag(int, Object)` 要求 int key 必须是 application 声明的 resource id，随手传 `String.hashCode()` 会直接抛 `IllegalArgumentException` crash；`setTag(Object)`（单参）又会和业务已有 tag 冲突。② 用进程级 `WeakHashMap<HybridCard, _>` 做「是否已发起首次 load」的去重，既不侵入 View 的 tag 空间，又因为 weak key 不会阻止 card 被 GC，避免去重表本身成为泄漏源。

**Q：JSB Method 这么多（上百个），怎么管理和注册？前端调一个不存在的方法会怎样？**
Method 按能力域组织（分享/登录/用户/礼物/评论/上传/埋点/状态订阅等），通过注册表统一注册到容器。前端调用是「方法名 → 查注册表 → 命中则执行、未命中返回错误码」，不会 crash。StateProvider 是另一条链路：Room/User/Setting/Message 等实时状态通过状态桥主动推给前端，前端订阅即可拿到，不用反复 JSB 拉取。

---

# 方向三：KMP 跨端 —— 一次编写、多端复用的架构范式

## 背景问题

Android 和 HarmonyOS 长期**双端各写一遍**：同一个功能，两套代码、两套 bug、两次联调，成本高且容易逻辑漂移。随着鸿蒙推进，这个问题成为研发效率的核心瓶颈。

核心目标：用 Kotlin Multiplatform 把核心业务逻辑下沉到 `commonMain`，实现一次编写、Android 与鸿蒙双端复用。

## 架构设计

### ① 严格分层 + 单向依赖
KMP 模块按 `host → sdk → business → ability → infra` 五层严格单向依赖，`_api` / `_impl` 分离，跨业务域只依赖 `_api`。涉及 **RoomModel、卡片容器、Service 层**等基础设施建设。

### ② expect/actual 跨端桥接
业务逻辑写在 `commonMain`（禁止引用平台 API），平台差异通过 **expect/actual** 桥接。以 Hybrid 卡片为例：`commonMain` 定义 `expect fun KmpAnniexLynxCard(...)`，Android 侧用 Compose `AndroidView` 承接、鸿蒙侧用 ArkTS 组件承接——同一份业务逻辑，两端各自落地渲染。

### ③ 三层解耦的迁移范式（以 TaskBanner 为样板）
把 TaskBanner 完整迁移到 KMP，沉淀出一套可复用的迁移方法论：
- **展示层隔离**：用细粒度 Setting 开关（`LIVE_TOP_RIGHT_BANNER_USE_KMP` / `_ANCHOR_KMP`）在入口层灰度切换，实验逻辑收敛在入口，不污染 legacy Native 文件；
- **数据层桥接**：通过 `rawPayload` 传输 Protobuf 字节流，KMP 侧统一解码；
- **信号层命名空间**：为 KMP 建立专用事件与数据输入桥，做到展示、数据、信号三层彻底解耦。

## 关键设计决策

- **设计阶段前置修复 P0/P1 风险**：首包通道不连通、IM 事件丢失、控制器串房、LiveContext 初始化竞态——都在架构评审阶段识别并修复，而非上线后救火。首包方案也从「KMP 接口请求」改为更稳的「Shell 原生链路透传 initialBannerJson」。
- **业务指标零损耗对齐**：埋点严格 1:1 对齐旧链路——Hybrid 路径的 `live_banner_show/click` 交由前端上报、Native 静态 banner 才由客户端上报，并补齐曝光埋点与布局计数，保证迁移对业务数据无损。
- **编译期隔离，保护 SaaS**：用 sourceSet（`douyin_only` / `saas_only`）隔离，抖音专属 KMP 依赖不泄漏到 SaaS 构建路径，解决 `YamlParseException` 编译污染。
- **稳定性对齐**：修复 HybridCard 引用链泄漏、`CancellationException` 被吞导致的协程取消传播问题、Lynx 卡片空指针崩溃——两端行为对齐。

## 技术要点小结

一套可复用的 KMP 迁移范式：入口隔离 + 三层解耦 + 埋点零损耗对齐 + sourceSet 编译隔离，可直接复制到后续直播模块，把「双端各写一遍」系统性变成「一次编写、多端复用」。

## 深入追问准备

**Q：commonMain 的 Kotlin 代码在鸿蒙侧是怎么跑起来的？编译产物是什么？**
KMP 通过 Kotlin/Native 把 `commonMain` + `ohosArm64Main` 编译成鸿蒙可用的产物，经 FFI 桥接层暴露给 ArkTS。跨端 UI 用注解（如 `@ArkTsExportComposable`/`@ArkTsExportClass`/`@ArkTsExport`）标记导出边界，生成 ArkTS 可调用的接口。业务逻辑（ViewModel、数据处理、状态机）全在 `commonMain` 复用；渲染层通过 `expect/actual` 分叉：Android 用 Compose，鸿蒙用 ArkTS 组件承接同一份 Compose 语义。

**Q：expect/actual 里如果某个能力鸿蒙没有 / Android 没有，怎么办？**
两条路：① 能力有但实现不同——`expect` 声明接口，两端 `actual` 各自实现（如 Hybrid 卡片渲染）。② 能力单端才有——用接口注入而非 expect/actual 硬绑，在 commonMain 定义抽象接口，只在支持的平台 `actual` 出真实现、另一端给 no-op stub。SaaS 隔离就是后者：`douyin_only` 出真实现，`saas_only` 出同包名 no-op stub，保证 `src/main` 里的静态引用两边都能编译过。

**Q：rawPayload 传 Protobuf 字节流，为什么不直接传 JSON？**
三个原因：① 消息源头（IM）本就是 Protobuf，直接透传字节流避免「Proto→JSON→再解析」的双重转换损耗和字段丢失；② KMP 侧用 `modelx-runtime` 统一从字节流解码成 message 实例，两端解码逻辑一致，杜绝双端 JSON 解析差异导致的漂移；③ 字节流比 JSON 更紧凑。代价是可读性差、调试麻烦——所以我在 mock 链路专门加了 `raw_payload_base64` 通道并配空校验/异常兜底，方便验证解码。

**Q：埋点「零损耗对齐」你怎么验证的？口径怎么保证和旧链路一致？**
先厘清旧链路口径：`TopRightBannerWidget` 里 Hybrid banner 的 `live_banner_show/click` 是**前端（Lynx/H5）自己上报**，Native 不报；只有 Native 静态 banner 才客户端上报。KMP 版严格照这个口径：`reportShowIfNeeded()` 只在 `config.mode == NATIVE` 触发，Hybrid 交前端。验证靠对比迁移前后同一 banner 的 show/click 事件量级与参数（banner_id / request_page=topright / room_orientation）是否一致。另外 `log_pb` 字段 KMP 的 RoomModel 当时缺失，是已知缺口，需从 Android `room.getLog_pb()` 注入补齐。

**Q：这套迁移范式的边界在哪？什么功能不适合迁 KMP？**
适合迁的是「业务逻辑重、UI 相对标准」的模块。不适合的：① 强依赖宿主平台特性的 UI（如开播的入场彩蛋动画 `animation_image`，依赖 `streamType==VIDEO` 且涉及运行时尺寸测量与属性动画序列，跨端成本高、收益低，我把它作为 P2 保留在 Android Shell 层）；② 高频、性能敏感、与平台渲染深度耦合的部分。范式的价值是「逻辑下沉复用 + 渲染分叉」，逻辑占比越高收益越大。

---

# 方向四：StockAgent —— AI Agent + RAG 的工程化落地

> 一个 AI 实践项目（股票量化分析、持仓诊断与推荐观察池 Agent）。核心不是「调了个大模型 API」，而是把 LLM 落地成一个流程可控、知识可溯源、行为可约束的真实智能体应用。

## 背景问题

大模型直接问答有三个致命短板，恰恰是投研这种严肃场景不能接受的：
- **幻觉**：模型会一本正经地编造数据和结论；
- **知识陈旧**：训练语料没有最新公告、行情、财报；
- **流程失控**：一步到位的回答无法体现「信息收集 → 基本面 → 催化剂 → 风险 → 结论」的严谨研究路径。

核心目标：用 Agent 编排 + RAG 检索增强 + Guardrails 护栏，把大模型改造成一个可控、可溯源、可迭代的投研智能体。

## 架构设计（五个核心模块）

### ① AgentLoop —— 显式阶段编排的控制回路
不是「一问一答」，而是一个**显式状态机式的 AgentLoop**，把股票研究拆成明确阶段：`INTAKE（信息收集）→ 基本面 → 催化剂 → 风险 → RECOMMENDATION（推荐结论）`。
- 每一步都由 `AnalysisState` 记录上下文，`_next_stage()` 驱动阶段推进；
- 对用户输入先分类（正常请求 / 澄清提问 / 信息不足），信息不足会**主动追问**（要股票代码、市场、持有周期、风险偏好），而不是硬答。
- 价值：把黑盒问答变成白盒、可解释、可干预的研究流程。

### ② LangChain Harness —— 模型调用的统一封装层
`LangChainStockHarness` 把「模型调用」抽象成一层可替换的 harness：封装 Prompt 编排、RAG 上下文注入、联网搜索上下文、模型参数（model / base_url / temperature / responses api）。
- 用 `Protocol` + `BaseStockHarness` 抽象接口，**模型供应商可插拔**（OpenAI 兼容接口、本地模型皆可接），便于降级与切换。

### ③ Hybrid RAG —— 检索增强，解决幻觉与时效
解决「幻觉 + 知识陈旧」的核心链路：
- **知识库构建**：`collect-universe` 生成分行业/分市场（A股/美股/港股）的公司库；`build-a-share-tech` 按「每只股票一篇完整分析文档」生成逐股 RAG 底稿。
- **混合检索**：Markdown → 分块 → **BM25 稀疏检索** + **embedding 向量召回**（本地 `BAAI/bge-small-zh-v1.5`），再用 **MMR** 做多样性重排，最后拼进 Prompt 上下文。
- **存储可生产化**：向量存储支持 Qdrant（生产）与本地 JSON（离线），embedding 不可用时**自动回退 BM25**，保证鲁棒性。

### ④ 可信度标签体系 —— 让每条知识可溯源
所有入库资料都带**可信度标签**：`#official_or_exchange`（官方/交易所）、`#third_party_dataset`（第三方线索）、`#user_supplied`、`#needs_verification`、`#needs_refresh`。
- Agent 回答时会明确提示哪些数据需要核验，做到「知识可溯源、风险有提示」。

### ⑤ Guardrails —— 输入输出双向护栏
`HarnessGuardrails` 做输入/输出的安全与合规约束：
- 输入侧：长度限制、**密钥泄漏检测**（正则拦 `sk-xxx`、api_key/token）、注入防护；
- 输出侧：长度约束、rubric 泄漏防护、免责声明——明确不构成投资建议。

## 关键设计决策

- **流程编排 + 检索 + 护栏三位一体**：而非「一个大模型解决一切」。严肃场景需要的是可控性，这是「AI 落地」与「AI Demo」的本质区分。
- **RAG 可降级、可离线**：embedding/Qdrant 不可用时自动回退 BM25，保证任何环境都能跑。
- **量化观察池用规则评分而非模型拍脑袋**：综合主题强度、涨跌幅、成交额、换手率、PE/PB 约束、风险惩罚输出分级，并全程打 `#needs_verification` 标签——AI 负责组织与解释，不负责承诺收益，边界清晰。
- **完整工程化**：CLI + 桌面端 GUI + 本地 API 服务 + 定时刷新 cron + 单测（pytest）+ RAG 评测（rag_eval）——不是一个脚本，而是一个可持续运行、可评测迭代的完整应用。

## 技术要点小结

一套「Agent + RAG + 护栏」的方法论：AgentLoop 管流程、RAG 管事实、Guardrails 管边界，把不可控的大模型改造成流程可控、知识可溯源、行为可约束的真实应用。

## 深入追问准备

**Q：Hybrid RAG 的融合分数怎么算的？BM25 和向量怎么加权？**
先各自算分再线性融合。BM25 用标准 Okapi 公式，参数 `k1=1.5、b=0.75`，`idf = log(1 + (N - df + 0.5)/(df + 0.5))`。向量走 cosine 相似度。融合公式是 `hybrid = 0.55 * vector + 0.45 * sparse(归一化后的BM25) + exact_bonus`。候选集来自三路合并去重：BM25 Top80 + 向量 Top80 + 含 query token 的兜底块。`exact_bonus` 是命中股票代码/公司名时的精确加权（source 命中 +0.35、六位股票代码正文命中 +0.30、heading 命中 +0.25），保证用户点名某只股票时对应文档优先。

**Q：为什么要 MMR？直接按分数 Top-K 不行吗？**
按分数 Top-K 容易「扎堆」——检索到的前几名可能都来自同一篇文档/同一公司，上下文冗余、覆盖面窄。MMR（最大边际相关）在相关性和多样性间权衡：我的实现是从 Top(`k*6`) 候选里贪心选取，`value = score + 0.05*query_token重叠 - 0.25*(来源已被选中)`——对已出现过的 source 施加 0.25 的多样性惩罚，让最终 K 条尽量来自不同文档，上下文更全面。

**Q：中文怎么分词和检索的？没用分词器会不会召回差？**
没引重量级分词器，用的是轻量策略：正则分别提取拉丁词（`[a-z0-9]...`）、连续中文串（`≥2` 字），再对中文串切 **bigram（二元组）**。bigram 让「宁德时代」能被「宁德」「德时」「时代」等片段召回，规避未登录词问题。另外有 `expand_query_tokens` 做同义词扩展（rag→检索/增强/生成 等）。对投研这种「专有名词+代码」为主的场景，bigram + 精确代码加权已经够用，且零依赖、可离线。

**Q：AgentLoop 是自己实现的状态机，为什么不用现成的 Agent 框架（如 LangGraph）？**
投研场景要的是**确定性的阶段推进**，不是自由探索。现成 Agent 框架偏向「模型自主决定下一步」，可控性弱、容易跑飞。我用显式状态机固定 `信息收集→基本面→催化剂→风险→结论` 的路径，每步 `AnalysisState` 留痕、`_next_stage()` 推进，还能在信息不足时主动追问、澄清提问不推进阶段。模型调用本身仍复用 LangChain（`LangChainStockHarness`），即「框架管模型调用，状态机管流程编排」，各取所长。

**Q：怎么防止幻觉？RAG 之外还有别的手段吗？**
四层：① RAG 把权威知识库注入上下文，让模型「基于给定材料回答」而非凭记忆；② 可信度标签（`#official_or_exchange`/`#third_party_dataset`/`#needs_verification`），回答时明确提示哪些需核验；③ 量化观察池用**规则评分**（主题强度/涨跌幅/成交额/换手率/PE-PB 约束/风险惩罚），不让模型拍数字；④ Guardrails 输出侧强制免责声明、明确不构成投资建议。核心原则是「AI 负责组织与解释，不负责编造事实与承诺收益」。

**Q：这套 RAG 质量怎么评估？改了检索逻辑怎么保证没变差？**
项目里有 `rag_eval` 评测链路和对应单测（`test_rag_index`/`test_rag_eval`），可对固定 query 集回归检索命中，改动检索/融合参数后跑评测对比，避免「优化一处、劣化整体」。这也是我强调它是「可评测迭代的完整应用」而非一次性脚本的原因。

---

## 附：常见追问与技术要点

| 方向 | 常见问题 | 技术要点 |
|---|---|---|
| 开播 | 架构是原创还是照搬 Android？ | 分层思想对齐以保证一致性；但 LifecycleTask 框架、Tetris Element 注册、LiveContext 控制器总线是结合 ArkTS 声明式范式重新落地的。 |
| 开播 | 扩展性体现在哪？ | 新增「状态面板/直播录制」只需实现 Element + Task 注册，核心控制器零改动（enableStatusPanelEntrance / enableBroadcastLiveRecord 即如此接入）。 |
| Hybrid | 为什么不直接用系统 WebView？ | 需要统一 Lynx/Web 两栈、打通 JSB 能力矩阵与实时状态桥、并做生命周期与泄漏治理，系统容器无法满足。 |
| Hybrid | 泄漏是怎么定位和根治的？ | 通过 DisposableEffect 清理顺序（先解绑 delegate 再 release 再 removeView）断开 controller→delegate→card 引用链；配合 WeakHashMap 去重、runCatching 可观测。 |
| KMP | 迁移会不会影响线上数据？ | 埋点 1:1 对齐，Hybrid 路径交前端上报、Native 才客户端上报；banner 曝光/点击率与原生版持平，业务无损。 |
| KMP | 怎么保证不影响 SaaS？ | sourceSet 编译隔离（douyin_only / saas_only），SaaS 侧提供 no-op stub，抖音专属依赖编译期不可见。 |
| StockAgent | 这和「调个 GPT API」有什么区别？ | 区别在可控性：AgentLoop 管流程（显式阶段状态机）、RAG 管事实（BM25+向量+MMR，可溯源标签）、Guardrails 管边界（密钥拦截/免责）。 |
| StockAgent | 怎么解决大模型幻觉？ | Hybrid RAG 把权威知识库注入上下文，资料带可信度标签，回答时提示需核验；量化评分用规则而非模型，不承诺收益。 |
| StockAgent | 这套 AI 能力可迁移到哪里？ | 「Agent+RAG+护栏」是通用方法论，可迁移到智能问答、内容审核辅助、运营助手等场景。 |

---

## 附：可量化的指标抓手（需从数据平台回填真实数字）

以下指标可通过对应埋点事件 / AB key 在数据平台（DataFinder / Libra / Slardar）查询：

- **KMP 提效**：迁移模块数 × 单模块双端重复开发人日 = 节省人日；双端逻辑漂移 bug 数下降。
- **KMP 无损**：`live_banner_show` / `live_banner_click`（request_page=topright）KMP 版 vs 原生版曝光/点击率持平。
- **开播转化**：`livesdk_pm_live_takepage_show` → `livesdk_live_take` 开播成功率；`livesdk_close_room_reason` 异常关播率。
- **播放稳定性**：功耗 `livesdk_performance_power`；后台观看 `livesdk_live_backstage_watch_start`；OOM/Crash 率下降幅度（Slardar）。
- **付费/回放**：Libra key `livesdk_harmony_enable_replay` / `livesdk_harmony_enable_paid_live` 等的渗透与转化。
