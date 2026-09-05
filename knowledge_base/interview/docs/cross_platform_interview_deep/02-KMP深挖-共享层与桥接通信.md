# KMP 深入版：原理、渲染与通信

## 1. 一句话定位

KMP（Kotlin Multiplatform）是 **Kotlin 业务逻辑跨端复用方案**。

在实际项目里它有两种常见形态：

- **逻辑共享模式**：KMP 输出 Model / State / Action，各端原生 UI 渲染。
- **Compose 共享 UI 模式**：KMP 里写 `@Composable` 组件，各端通过平台宿主容器承载渲染。

所以不能简单说“KMP 不渲染 UI”。更准确是：

> KMP 的核心是共享业务语义；UI 可以各端原生渲染，也可以在 Compose Multiplatform 场景下共享部分组件结构，但最终都要通过各端平台容器落地。

一句话讲清楚 KMP 渲染：

> KMP 本身不是一个统一的“跨端渲染引擎”。逻辑共享模式下，KMP 只产出状态，各端用自己的 UI 框架渲染；Compose 共享 UI 模式下，KMP 里的 `@Composable` 由 Compose Runtime 执行，再通过 AndroidView / ArkUIViewTopLayer / UIKitView 等平台互操作层接入各端 UI 树。

## 2. KMP 解决的问题

KMP 主要解决：

- 多端业务逻辑重复实现。
- Android / HarmonyOS / iOS 状态机口径漂移。
- Model / 消息 / 埋点字段不一致。
- 同一业务需求多端重复开发。
- 平台能力差异需要有清晰边界。

适合下沉到 KMP 的内容：

- Model。
- ViewModel。
- 状态机。
- Repository / Service 抽象。
- 消息解析。
- KV / Setting 抽象。
- 埋点参数拼装。
- schema / action 决策。

不适合硬下沉的内容：

- 播放器。
- 复杂动画。
- 强平台 SDK。
- 页面生命周期细节。
- 系统权限、窗口、小窗、PiP。
- 各端原生 UI 细节。

## 3. 工程结构

典型结构：

```text
commonMain
  -> 共享 Model / ViewModel / State / Service / UseCase

androidMain
  -> Android actual
  -> Compose / View / Android SDK

ohosArm64Main
  -> HarmonyOS actual
  -> ArkTS bridge / ArkUI interop

iosMain
  -> iOS actual
  -> Swift / OC bridge
```

`commonMain` 不能直接依赖 Android / HarmonyOS / iOS 平台 API。平台差异通常通过：

- `expect / actual`
- 接口注入
- Service bridge
- wrapper / delegate
- 平台 sourceSet

来解决。

## 4. KMP 的两种渲染模式

### 4.1 逻辑共享模式

这种模式下，KMP 不直接画 UI，只输出状态。

```text
KMP commonMain
  -> ViewModel
  -> RenderState
  -> Action / Effect
  -> 平台 wrapper
  -> Android / HarmonyOS / iOS 原生 UI
```

例子：

```text
RenderState
  - visible
  - title
  - imageUrl
  - schema
  - renderMode
  - loading
  - error
```

各端拿到 state 后：

- Android 用 Compose / View 渲染。
- HarmonyOS 用 ArkUI 渲染。
- iOS 用 SwiftUI / UIKit 渲染。

这条链路里，KMP 到底做什么：

```text
1. 接收 Action
   比如 show、hide、click、message arrive、setting changed

2. 执行业务逻辑
   判断是否展示、展示什么内容、按钮是什么状态、是否需要上报

3. 产出 RenderState
   RenderState 是平台 UI 可以消费的稳定快照

4. 产出 Effect
   Effect 表达一次性动作，比如打开 schema、toast、埋点

5. 平台 wrapper 分发
   Android / HarmonyOS / iOS wrapper 把 State 转成各自 UI 状态

6. 各端原生渲染
   Android Compose/View、HarmonyOS ArkUI、iOS SwiftUI/UIKit 自己完成布局和绘制
```

这里 KMP 不参与平台 UI 的 measure / layout / draw。它解决的是“多端该显示什么、什么时候显示、点击后做什么”一致，而不是“每个像素怎么画”。

可以这样理解：

```text
KMP = UI 的业务大脑
平台 UI = UI 的身体和渲染系统
```

### 4.2 Compose 共享 UI 模式

这种模式下，KMP 中直接写 `@Composable`。

```text
KMP @Composable
  -> Compose Runtime 执行组合
  -> 各端 actual 承接平台差异
  -> 平台宿主容器挂载
  -> 屏幕渲染
```

重要点：

- `@Composable` 是共享 UI 结构。
- Compose Runtime 负责执行组合、状态订阅、重组。
- 平台容器负责把 Compose 或平台 View 接到本端 UI 树。
- 平台能力仍然通过 actual / service / delegate 提供。

这条链路里，KMP Compose 的渲染过程可以拆成：

```text
1. commonMain 写 @Composable
   声明组件结构、状态读取、事件回调

2. Compose Runtime 执行组合
   记录组件树、状态读取、remember 对象和 slot table

3. State 变化触发重组
   Runtime 找到依赖该状态的 Composable 范围重新执行

4. 生成 UI 更新
   Compose 将变化应用到底层平台节点或互操作节点

5. 平台宿主承载
   Android 用 ComposeView / AndroidComposeView
   HarmonyOS 用 ArkUIViewTopLayer / ArkUIComponentContent
   iOS 用 ComposeUIViewController / UIKitView

6. 平台完成绘制
   Android / HarmonyOS / iOS 仍然使用本端图形和 UI 系统显示到屏幕
```

所以 Compose 共享 UI 不是“把一张跨端位图画到所有端”。更准确是：

```text
KMP Compose 共享组件声明和组合逻辑
  -> Compose Runtime 管状态和重组
  -> 平台互操作层接入本端 UI 树
  -> 本端渲染系统完成最终绘制
```

两种模式的差异：

| 维度 | 逻辑共享模式 | Compose 共享 UI 模式 |
|---|---|---|
| KMP 输出 | State / Action / Effect | `@Composable` + State |
| UI 结构 | 各端自己写 | commonMain 共享部分 UI 结构 |
| 平台渲染 | Android / ArkUI / UIKit 自己渲染 | Compose Runtime + 平台宿主 |
| 动态化 | 低 | 低 |
| 平台差异处理 | wrapper / adapter | actual / interop / platform view |
| 适合场景 | 平台 UI 差异大 | 组件结构相对一致 |

## 5. Android 怎么渲染 KMP 组件

Android 有三类方式。

### 5.1 KMP State + Compose 渲染

```text
KMP ViewModel
  -> StateFlow / callback
  -> Compose collectAsState
  -> Compose UI
```

适合：

- 新组件。
- 状态驱动 UI。
- UI 完全可以由 Compose 表达。

### 5.2 KMP State + Android View 渲染

```text
KMP ViewModel
  -> callback / observer
  -> Android Widget / Delegate
  -> TextView / ImageView / RecyclerView / 自定义 View
```

适合：

- 已有 View 体系。
- 需要复用旧组件。
- 接入 Android 原生容器。

### 5.3 KMP Compose + AndroidView / ComposeView 承载

```text
KMP @Composable
  -> androidMain actual
  -> AndroidView(factory = { nativeView })
  -> Compose 测量和摆放这个 nativeView
  -> nativeView 按 Android View 机制渲染
```

`ComposeView` / `AndroidComposeView` 的作用：

- 把 Compose 渲染树挂进 Android View 层级。
- 让 Compose 可以作为普通 Android View 被页面、Fragment、Widget 承载。

`AndroidView` 的作用：

- 在 Compose 组件树里嵌 Android 原生 View。
- Compose 负责测量、布局、生命周期回调。
- 原生 View 自己负责内部渲染。

你的 `KmpHybridCard.android.kt` 就是这种模式：

```text
KMP @Composable KmpAnniexLynxCard
  -> Android actual
  -> AndroidView
  -> HybridCard
  -> Lynx / Web 容器原生渲染
```

## 6. HarmonyOS 怎么渲染 KMP 组件

HarmonyOS 也有两类方式。

### 6.1 KMP State + ArkUI 渲染

```text
KMP exported interface / class
  -> ArkTS wrapper
  -> ArkTS State / ViewModel adapter
  -> ArkUI build()
  -> ArkUI 组件渲染
```

适合：

- 需要完全遵循 ArkUI 声明式语法。
- 平台 UI 差异较大。
- 需要直接消费 HarmonyOS 端能力。

### 6.2 KMP Compose + ArkUIViewTopLayer / ArkUIComponentContent 承载

```text
KMP @Composable
  -> ohosArm64Main actual
  -> 调 ArkTS service 创建 ComponentContent
  -> ArkUIViewTopLayer
  -> ArkUIComponentContent
  -> 挂到 HarmonyOS UI 树
```

以你的 `KmpHybridCard.ohosArm64.kt` 为例：

```text
KmpAnniexLynxCard
  -> kmpService<IKmpLiveAnniexLynxCardServiceHarmony>()
  -> service.createLynxCardView(params)
  -> ArkInstance(napi_value)
  -> ArkUIViewTopLayer
  -> ArkUIComponentContent
```

这里要讲清楚：

- KMP Compose 负责组件入口、组合、状态和生命周期绑定。
- ArkTS service 负责创建真实 HarmonyOS 侧卡片内容。
- `ArkUIViewTopLayer` 是 Compose 和 ArkUI 的平台互操作层。
- `ArkUIComponentContent` 把 ArkTS 返回的 `ComponentContent` 包装成 Compose 可承载内容。
- `DisposableEffect` 负责 bind / reset delegate。
- `onRelease` 负责释放 controller 和平台 view，避免资源泄漏。

## 7. iOS 怎么渲染 KMP 组件

iOS 也分两类。

### 7.1 KMP State + SwiftUI / UIKit 渲染

```text
KMP Framework
  -> Swift / OC wrapper
  -> ObservableObject / delegate / callback
  -> SwiftUI / UIKit
```

SwiftUI：

```text
KMP State
  -> ObservableObject
  -> @Published
  -> View body 重算
```

UIKit：

```text
KMP callback
  -> UIViewController
  -> update UIView / UILabel / UIImageView
```

### 7.2 KMP Compose + UIKit 宿主承载

```text
KMP @Composable
  -> Compose Runtime for iOS
  -> ComposeUIViewController / UIView
  -> UIKit ViewController / View 层级
```

如果需要在 Compose 里嵌 UIKit View：

```text
KMP @Composable
  -> UIKitView(factory = { UIView() })
  -> Compose 测量和摆放
  -> UIView 按 UIKit 机制渲染
```

## 8. KMP 怎么通信

### 8.1 KMP 调平台

KMP 不能直接调用平台 API，所以需要抽象。

```kotlin
expect class KmpKVStorage {
    fun getString(key: String): String?
    fun putString(key: String, value: String)
}
```

平台实现：

```text
androidMain actual
  -> SharedPreferences / MMKV / Keva

ohosArm64Main actual
  -> ArkTS KV bridge

iosMain actual
  -> UserDefaults / native storage
```

### 8.2 平台调 KMP

```text
平台 UI
  -> wrapper / delegate
  -> KMP ViewModel.onAction()
  -> KMP 更新 state
  -> 平台 UI 重新渲染
```

典型事件：

- click。
- show。
- hide。
- onAppear。
- onDisappear。
- onLoadSuccess。
- onLoadError。
- onDestroy。

### 8.3 KMP 发 Effect 给平台

```text
KMP ViewModel
  -> Effect.OpenSchema(url)
  -> 平台 wrapper 接收
  -> Android / HarmonyOS / iOS 执行路由
```

Effect 适合表达一次性平台动作：

- 打开 schema。
- 展示 toast。
- 拉 Hybrid。
- 上报埋点。
- 触发动画。

## 9. 数据同步

跨端数据同步常见两种方式。

### 对象复制

```text
平台对象
  -> 转成 KMP Model
  -> KMP 内部持有副本
```

优点：

- 访问快。
- KMP 内部逻辑简单。
- 适合全字段遍历。

缺点：

- 大对象复制成本高。
- 字段变更要维护映射。
- 内存占用更高。

### 对象共享 / 代理

```text
KMP Model
  -> 持有平台对象代理
  -> 访问字段时跨端读取
```

优点：

- 避免大对象全量复制。
- 适合 Room / User 这类大对象少字段访问。

缺点：

- 单字段访问有桥接成本。
- 高频访问需要 prefetch / TTL 缓存。
- 生命周期要严格管理。

判断标准：

- 小对象、全字段读：复制。
- 大对象、少字段读：代理。
- 高频字段：预取 + 缓存。
- 跨线程或长生命周期：注意对象释放和引用安全。

## 10. 消息通信为什么用 Protobuf / rawPayload

直播消息源头通常是 Protobuf。

使用 rawPayload 的原因：

- 避免 Proto -> JSON -> Model 的字段丢失。
- 保证多端从同一份 bytes 解码。
- 对 unknown field / 二进制字段更友好。
- 更贴近原始消息链路。

测试时 raw bytes 不好构造，所以可以提供 base64 mock 通道：

```text
raw_payload_base64
  -> decode bytes
  -> KMP message parser
  -> 生成业务消息
```

## 11. 生命周期和资源释放

KMP Compose + 平台 View 混合时，生命周期尤其关键。

常见风险：

- Compose 重组导致重复创建平台 View。
- 平台 View 被释放后仍被 KMP controller 持有。
- delegate 没 reset，导致回调旧对象。
- 平台 listener 没清理，导致泄漏和重复回调。

常见处理：

```text
remember
  -> 缓存 controller / view wrapper

DisposableEffect
  -> bind controller
  -> onDispose reset delegate

onRelease
  -> release controller
  -> dispose platform content
```

## 12. commonMain 边界设计

KMP 的关键不是把代码“尽量搬到 commonMain”，而是判断什么逻辑适合跨端共享。

适合放在 `commonMain`：

- 业务状态机。
- 纯数据模型。
- 参数拼装。
- 协议解析。
- 埋点字段组装。
- Setting / KV 抽象接口。
- Repository 接口。
- ViewModel 的业务决策。

不适合放在 `commonMain`：

- Android Context。
- ArkTS UI 能力。
- UIKit / SwiftUI 生命周期。
- 播放器 SDK。
- 系统权限。
- 线程调度细节。
- 平台 View 创建。

判断标准：

```text
业务语义一致
  -> 放 commonMain

平台能力不同
  -> expect/actual 或接口注入

UI 表现差异大
  -> commonMain 出 State，各端渲染

UI 结构一致且可接受 Compose
  -> Compose 共享 UI
```

面试可以强调：

> KMP 不是为了追求 100% 代码复用，而是把容易漂移的业务语义收敛到一处，把平台差异留在 sourceSet 边界。

## 13. expect / actual 和接口注入

KMP 处理平台差异主要有两种方式。

### expect / actual

适合平台差异稳定、语义一致的能力。

```text
commonMain expect
  -> androidMain actual
  -> ohosArm64Main actual
  -> iosMain actual
```

适合：

- 时间。
- 日志。
- KV。
- 线程调度。
- 轻量平台能力。

优点：

- 调用方简单。
- 编译期保证各端实现齐全。
- 类型更明确。

缺点：

- sourceSet 之间要保持签名一致。
- 能力复杂时 actual 容易膨胀。

### 接口注入

适合业务依赖可替换、平台能力复杂的场景。

```text
commonMain interface LiveRouter
  -> AndroidLiveRouter
  -> HarmonyLiveRouter
  -> IosLiveRouter
```

适合：

- 路由。
- Hybrid 容器。
- 播放器控制。
- 业务服务。
- 上报和监控。

优点：

- 可测试。
- 可 mock。
- 依赖关系更清楚。
- 不强依赖编译期平台 sourceSet。

工程上经常组合使用：

```text
底层平台能力
  -> expect/actual

业务服务能力
  -> interface + platform implementation
```

## 14. KMP ViewModel 和状态流

KMP 做跨端业务时，最常见的模式是 ViewModel 输出状态。

```text
Action
  -> ViewModel
  -> reduce
  -> State
  -> Effect
```

State 适合表达可重复渲染的 UI 状态：

- visible。
- loading。
- title。
- imageUrl。
- buttonText。
- error。
- selected。

Effect 适合表达一次性动作：

- openSchema。
- showToast。
- reportEvent。
- startAnimation。
- closePanel。

为什么 State 和 Effect 要分开：

- State 可被重复消费。
- Effect 通常只能消费一次。
- 页面重建时 State 可以恢复。
- Effect 如果重复消费会导致重复跳转、重复上报。

跨端消费方式：

```text
KMP StateFlow
  -> Android collect
  -> Harmony wrapper callback
  -> iOS observable adapter
```

需要注意：

- 状态对象最好不可变。
- 频繁变化字段要拆分。
- 大对象不要直接放 State。
- 回调要和生命周期绑定。

## 15. Compose Runtime 和重组

KMP Compose 共享 UI 时，需要理解 Compose Runtime 做了什么。

```text
@Composable function
  -> composition
  -> slot table
  -> state read tracking
  -> recomposition
  -> apply changes
  -> platform render
```

关键点：

- `@Composable` 不是普通函数，它参与 Compose Runtime 的组合。
- Runtime 会记录状态读取位置。
- 状态变化后，只重组相关范围。
- 最终更新仍要落到平台渲染后端。

性能风险：

- State 粒度过大导致大范围重组。
- `remember` 使用不当导致对象重复创建。
- 平台 View 嵌入 Compose 时生命周期没处理好。
- 重组中执行副作用。

治理方式：

- 状态拆小。
- 稳定对象用 `remember`。
- 副作用放 `LaunchedEffect` / `DisposableEffect`。
- 平台 View 释放放到 onDispose / onRelease。

## 16. 平台 View 嵌入 Compose 的成本

`AndroidView`、`UIKitView`、`ArkUIComponentContent` 都属于“平台互操作”。它们能让 Compose 承载原生 View，但不是零成本。

成本包括：

- 生命周期转换。
- 测量和布局适配。
- 事件分发适配。
- 资源释放。
- 线程切换。
- 状态同步。

典型风险：

- Compose 重组导致平台 View 重复创建。
- 平台 View 持有旧 delegate。
- 端侧 view 销毁但 KMP controller 还在回调。
- 平台 View 内部异步加载完成时宿主已销毁。

正确做法：

```text
remember controller
  -> create platform view once
  -> update props on recomposition
  -> DisposableEffect bind lifecycle
  -> onDispose / onRelease cleanup
```

面试可以这样说：

> Compose 共享 UI 不是把平台差异抹掉，而是提供统一的组合模型。真正接入播放器、Lynx、ArkUI、UIKit 时，仍然要认真处理平台 View 的生命周期。

## 17. HarmonyOS 桥接细节

先讲本质：

> KMP 在 HarmonyOS / iOS 上运行，并不是把 JVM 带到这些平台，也不是像 JS 一样解释执行。KMP 会把 `commonMain` 里的 Kotlin 代码按目标平台编译成 native 产物；平台侧通过生成的 ABI、framework、bridge 或 wrapper 去调用这些 native 产物。平台差异由 `actual`、service、adapter、wrapper 承接。

整体可以理解成：

```text
commonMain Kotlin
  -> 编译到不同 target
      -> androidMain: JVM bytecode / Android runtime
      -> ohosArm64Main: HarmonyOS native library / bridge
      -> iosArm64Main: iOS framework / xcframework
  -> 平台 wrapper 消费
  -> 平台 UI 渲染或平台能力执行
```

所以 KMP 的运行分两层：

- **业务逻辑运行层**：Kotlin/Native 编译后的代码在目标平台进程内运行。
- **平台接入层**：ArkTS、Swift/OC、Android Kotlin 通过 wrapper / bridge 调用 KMP 暴露的能力。

HarmonyOS 场景下，KMP 和 ArkTS 之间通常要通过导出接口、service、wrapper 做桥接。

典型链路：

```text
KMP commonMain
  -> ohosArm64Main actual
  -> Harmony service interface
  -> ArkTS implementation
  -> ArkUI ComponentContent
  -> ArkUI 渲染树
```

关键问题：

- 类型映射：Kotlin nullable 和 ArkTS `undefined` 的对应。
- 生命周期：KMP 对象和 ArkTS 组件销毁时机不同。
- 回调：ArkTS 回调 KMP 时要避免旧对象残留。
- 线程：UI 更新必须回到平台 UI 线程。
- 资源：ArkUI content、controller、listener 要释放。

工程上最好有一个 wrapper 层：

```text
KMP public API
  -> Harmony adapter
  -> ArkTS service
  -> ArkUI component
```

不要让 commonMain 直接理解 ArkUI 细节，也不要让 ArkTS 页面直接散落调用 KMP 内部对象。

### 17.1 KMP 在 HarmonyOS 上怎么运行

HarmonyOS 侧可以理解成：KMP 的 Kotlin 代码先被编译成 `ohosArm64` 目标产物，然后通过鸿蒙侧桥接能力被 ArkTS / ArkUI 工程调用。

```text
KMP commonMain
  -> Kotlin/Native 编译
  -> ohosArm64Main actual 补平台实现
  -> 生成 HarmonyOS 可链接 native 产物
  -> ArkTS bridge / NAPI / service wrapper
  -> ArkUI 页面或业务 service 调用
```

在业务代码里通常不会让 ArkTS 页面直接操作 KMP 内部对象，而是会有一层适配：

```text
ArkUI Page / Component
  -> ArkTS service
  -> KMP bridge
  -> KMP public API / ViewModel
  -> State / Effect
  -> ArkTS adapter
  -> ArkUI 刷新
```

这说明两件事：

- KMP 逻辑是在鸿蒙 App 进程里以 native 产物方式运行。
- ArkUI 仍然是鸿蒙侧的 UI 渲染体系，KMP 只是提供状态、动作或 Compose 互操作入口。

### 17.2 HarmonyOS 消费 KMP 的两种模式

#### 模式一：逻辑共享

这是更常见、也更稳的模式。

```text
KMP ViewModel
  -> 输出 RenderState
  -> ArkTS wrapper 接收
  -> 转成 ArkUI @State / 普通状态
  -> ArkUI build() 渲染
```

用户操作回传：

```text
ArkUI click / lifecycle
  -> ArkTS adapter
  -> KMP onAction()
  -> KMP 更新 State
  -> ArkUI 局部刷新
```

这种模式下：

- UI 是 ArkUI 画的。
- KMP 不负责 ArkUI 的具体布局。
- KMP 负责业务状态机、消息解析、配置、埋点、action 决策。

#### 模式二：Compose 共享 UI + ArkUI 互操作

如果 KMP 里有 `@Composable`，鸿蒙侧需要平台互操作层把它接到 ArkUI 体系。

```text
KMP @Composable
  -> Compose Runtime
  -> ohosArm64Main actual
  -> ArkTS service 创建 ComponentContent
  -> ArkUIViewTopLayer / ArkUIComponentContent
  -> ArkUI 页面承载
```

这里重点是：

- Compose Runtime 管组合、状态读取、重组。
- ArkTS service 创建真实鸿蒙侧内容。
- `ArkUIViewTopLayer / ArkUIComponentContent` 负责把 ArkUI 内容嵌到 Compose / KMP 宿主关系里。
- 最终显示仍然由鸿蒙 ArkUI / 系统渲染链路完成。

### 17.3 HarmonyOS 需要做哪些改造

要让鸿蒙侧稳定消费 KMP，通常需要补这些能力：

1. **构建接入**
   - KMP 模块支持 `ohosArm64Main`。
   - 编译产物能被鸿蒙工程依赖。
   - 产物版本和鸿蒙 App 版本对齐。

2. **类型桥接**
   - Kotlin nullable 映射到 ArkTS `undefined`。
   - enum / sealed class 转成 ArkTS 可消费模型。
   - List / Map / 对象模型避免动态结构。

3. **服务注入**
   - Router。
   - Setting。
   - KV。
   - Logger。
   - Monitor。
   - Hybrid service。
   - Account / user service。

4. **状态适配**
   - KMP State 转 ArkTS 状态。
   - KMP Effect 转 ArkTS 平台动作。
   - 生命周期回调绑定到 KMP attach / detach / destroy。

5. **资源释放**
   - ArkUI content release。
   - KMP controller release。
   - listener unregister。
   - coroutine / callback cancel。

### 17.4 HarmonyOS 接入常见坑

- ArkTS 不适合使用 TS 动态对象，KMP 导出模型要明确字段。
- KMP `null` 语义要在边界归一成 `undefined`，避免向 ArkTS 内部扩散。
- ArkUI `build()` 不能做副作用，KMP action 不要在 build 调用链里触发。
- KMP callback 回来时组件可能已经销毁，需要 alive check。
- 消息订阅和 service listener 要在页面销毁时清理。
- Compose/ArkUI 互操作时要避免重复创建平台 content。

### 17.5 HarmonyOS 面试回答模板

如果面试官问“KMP 在鸿蒙上怎么跑”，可以这样回答：

> KMP 在鸿蒙上不是跑 JVM，也不是解释执行，而是通过 Kotlin/Native 编译到 `ohosArm64` 目标产物。`commonMain` 放共享业务逻辑，`ohosArm64Main` 补鸿蒙平台 actual 或 bridge。ArkTS 侧通常不会直接散落调用 KMP 内部对象，而是通过 service / wrapper 消费 KMP public API。  
> 如果是逻辑共享，KMP 输出 State / Effect，ArkTS adapter 转成 ArkUI 状态并渲染；如果是 Compose 共享 UI，则通过 ArkUIViewTopLayer / ArkUIComponentContent 这类互操作层把 KMP Compose 或 ArkTS 创建的 ComponentContent 接进页面。最终 UI 还是由 ArkUI 和鸿蒙系统渲染，KMP 负责共享业务语义和状态机。

## 18. Android 桥接细节

Android 侧 KMP 通常更自然，因为 Kotlin、Compose、协程生态一致。

常见链路：

```text
KMP ViewModel
  -> StateFlow
  -> Android lifecycleScope collect
  -> Compose / View update
```

或：

```text
KMP @Composable
  -> Android actual
  -> ComposeView
  -> AndroidView
  -> 原生 View / HybridCard
```

Android 侧要注意：

- `Context` 不要泄漏到 commonMain。
- Activity / Fragment 生命周期要和 KMP collect 绑定。
- AndroidView 里的 View 不要在每次重组都创建。
- 播放器、HybridCard、Surface 这类资源要显式 release。
- 协程 scope 不能使用全局 scope 承载页面任务。

## 19. iOS 桥接细节

先讲本质：

> iOS 上 KMP 主要依赖 Kotlin/Native。Kotlin `commonMain` 和 `iosMain` 代码会被编译成 iOS native binary，并包装成 `.framework` 或 `.xcframework`。Swift / OC 通过生成的 Objective-C/Swift 可见接口调用这些 KMP class、function 和对象。KMP 运行时会随 framework 一起参与 App 进程内运行。

iOS 侧通常把 KMP 编译成 framework，被 Swift / OC 消费。

逻辑共享模式：

```text
KMP Framework
  -> Swift wrapper
  -> ObservableObject / delegate
  -> SwiftUI / UIKit
```

Compose 共享 UI 模式：

```text
KMP @Composable
  -> ComposeUIViewController
  -> UIViewController containment
  -> UIKit / SwiftUI 宿主页面
```

这里要区分两个方向：

- `ComposeUIViewController`：把 KMP Compose UI 包成一个 `UIViewController`，让 iOS 原生页面可以把它当普通 `UIViewController` 接入。
- `UIKitView`：在 KMP Compose UI 里面嵌入一个 iOS 原生 `UIView`，例如地图、播放器、原生输入框或已有 UIKit 组件。

所以更准确的说法是：

```text
Compose UI -> UIKit
  KMP @Composable
    -> ComposeUIViewController
    -> iOS 宿主用 UIViewController containment 接入

UIKit -> Compose UI
  KMP @Composable
    -> UIKitView(factory = { UIView() })
    -> Compose 负责测量和摆放
    -> UIView 自己按 UIKit / CoreAnimation 机制绘制
```

需要关注：

- Kotlin 类型到 Swift 类型的映射。
- nullable 的处理。
- Flow / callback 到 Swift observable 的适配。
- iOS 生命周期和 KMP scope 的绑定。
- UIKitView 嵌入原生 UIView 的释放。

### 19.1 iOS 要怎么引入 KMP

iOS 消费 KMP 的第一步，是把 KMP 模块编译成 iOS 可识别的产物。通常产物形态是：

- `.framework`
- `.xcframework`
- Swift Package 引入的 binary target
- CocoaPods 集成的 KMP framework

常见链路：

```text
KMP shared module
  -> Gradle build
  -> iosArm64 / iosSimulatorArm64 / iosX64
  -> framework / xcframework
  -> Xcode 工程引入
  -> Swift / OC import
```

iOS 侧引入后，Swift 里通常是：

```swift
import SharedKmpModule
```

然后消费 KMP 暴露出来的 class、interface、function、enum、sealed class 等。

需要的工程能力：

- KMP 模块配置 iOS target。
- 输出 `framework` 或 `xcframework`。
- Xcode 工程接入产物。
- Swift / OC wrapper 层封装 KMP API。
- KMP 版本和 iOS App 版本对齐。
- Debug / Release 产物区分。

### 19.2 iOS 消费 KMP 的三种方式

#### 方式一：消费 Model / 工具方法

这是最轻量的方式。

```text
KMP commonMain
  -> Model / parser / helper
  -> iOS Swift 直接调用
```

适合：

- 协议解析。
- 字段转换。
- 埋点参数拼装。
- 配置默认值。
- 纯函数工具。

示例理解：

```text
Swift
  -> KmpMessageParser.parse(rawPayload)
  -> KmpBusinessMessage
  -> iOS UI 自己渲染
```

这种方式改造成本最低，因为 iOS 只把 KMP 当成一个普通 SDK。

#### 方式二：消费 ViewModel / State / Action

这是业务逻辑共享最常见的方式。

```text
iOS UI
  -> Swift wrapper
  -> KMP ViewModel.onAction()
  -> KMP reduce state
  -> StateFlow / callback
  -> Swift ObservableObject
  -> SwiftUI / UIKit update
```

典型结构：

```text
KMP ViewModel
  input: Action
  output: State
  side effect: Effect

iOS Wrapper
  observe state
  convert to Swift model
  dispatch effect to iOS service

iOS View
  render state
  send user event
```

SwiftUI 里常见适配：

```text
KMP StateFlow
  -> Swift adapter
  -> ObservableObject
  -> @Published state
  -> SwiftUI body refresh
```

UIKit 里常见适配：

```text
KMP callback / observer
  -> UIViewController
  -> update UILabel / UIView / UITableView
```

这种方式的价值是：iOS UI 仍然原生，但业务判断和状态机来自 KMP。

#### 方式三：消费 KMP Compose UI

如果 KMP 里写了 Compose Multiplatform UI，iOS 可以通过 `ComposeUIViewController` 接入。

```text
KMP @Composable
  -> ComposeUIViewController
  -> iOS UIViewController
  -> addChild / view hierarchy
  -> UIKit 页面展示
```

iOS 原生侧看到的是一个 `UIViewController`，所以可以像接普通子页面一样接入：

```text
Parent UIViewController
  -> addChild(composeUIViewController)
  -> addSubview(composeUIViewController.view)
  -> set frame / constraints
  -> didMove
```

如果是 SwiftUI 宿主，也可以通过 `UIViewControllerRepresentable` 包一层。

这一种方式适合：

- UI 结构多端一致。
- 组件相对独立。
- 平台差异可控。
- 不强依赖大量 UIKit 专属能力。

不适合：

- 交易主链路强平台交互。
- 大量 UIKit 既有复杂组件。
- 强手势、强动画、强系统能力页面。

### 19.3 iOS 要做哪些 wrapper 改造

iOS 不建议到处直接调用 KMP 内部对象，最好加一层 Swift wrapper。

wrapper 负责：

- 隔离 KMP API 变化。
- 把 Kotlin 类型转成 Swift 友好类型。
- 把 KMP nullable 转成 Swift optional。
- 把 KMP Flow / callback 转成 Combine / async / closure。
- 把 Effect 转成 iOS 原生动作。
- 绑定 iOS 生命周期。
- 统一错误码和日志。

推荐结构：

```text
KMP Framework
  -> KmpFeatureViewModel
  -> Swift FeatureAdapter
  -> Swift ObservableObject / ViewController
  -> SwiftUI / UIKit View
```

不要让页面这样做：

```text
ViewController
  -> 直接 new KMP 内部对象
  -> 直接读写 KMP 内部状态
  -> 各页面自己处理 Flow / nullable / error
```

更稳的是：

```text
ViewController
  -> Swift Adapter
  -> KMP public API
```

### 19.4 Flow / 协程怎么给 iOS 消费

KMP 常用 `StateFlow` / `SharedFlow` 输出状态，但 Swift 不能像 Kotlin 那样自然 collect。

常见改造：

```text
KMP StateFlow
  -> expose observeState(callback)
  -> iOS wrapper 持有 cancellable / closeable
  -> callback 更新 Swift state
```

或者：

```text
KMP Flow
  -> Swift async sequence adapter
  -> Swift Task observe
  -> MainActor update UI
```

需要注意：

- UI 更新必须回主线程。
- iOS 页面销毁时取消观察。
- 不要让 KMP scope 比页面生命周期长太多。
- callback 返回时检查对象是否仍然 alive。
- error / completion 要能传到 Swift。

面试表达：

> iOS 消费 KMP StateFlow 时，我不会让页面直接感知协程细节，而是在 Swift wrapper 里把 Flow 转成 ObservableObject、callback 或 async sequence。页面只消费 Swift 友好的状态，并在 deinit 或 view disappear 时取消订阅。

### 19.5 Effect 怎么在 iOS 执行

KMP 不应该直接执行 iOS 路由、toast、弹窗、交易确认等平台动作，而是发 Effect。

```text
KMP ViewModel
  -> Effect.OpenSchema(url)
  -> Effect.ShowToast(text)
  -> Effect.ReportEvent(params)
  -> Effect.RequireLogin

iOS Adapter
  -> route service
  -> toast service
  -> logger service
  -> auth service
```

这样做的好处：

- commonMain 不依赖 UIKit。
- 平台动作留在 iOS。
- 方便单测 KMP 逻辑。
- 方便不同平台做差异化。

### 19.6 iOS 接入 KMP 需要补哪些基础能力

如果一个团队要真正让 iOS 消费 KMP，通常需要补这些基础设施：

1. **构建产物能力**
   - KMP 输出 `xcframework`。
   - 支持真机和模拟器。
   - Debug / Release 区分。
   - CI 能自动产物发布。

2. **Swift wrapper**
   - 封装 KMP public API。
   - 类型转换。
   - Flow / callback 适配。
   - 生命周期绑定。

3. **平台服务实现**
   - Router。
   - Storage。
   - Network。
   - Logger。
   - Setting。
   - Monitor。
   - Auth / account。

4. **UI 接入层**
   - SwiftUI / UIKit 消费 State。
   - ComposeUIViewController 接入。
   - UIKitView 嵌入原生控件。

5. **测试和排障**
   - commonMain 单测。
   - iOS wrapper 单测。
   - 产物版本检查。
   - crash 符号和日志。
   - 状态流 trace。

### 19.7 iOS 接入时最容易踩的坑

- Kotlin nullable 到 Swift optional 语义没对齐。
- enum / sealed class 在 Swift 侧使用不自然，需要 wrapper。
- Flow 订阅没有取消，导致页面释放后仍回调。
- KMP scope 生命周期过长，造成内存泄漏。
- iOS UI 更新没有回主线程。
- KMP framework 版本和 App 代码不匹配。
- ComposeUIViewController 被重复创建，导致状态丢失。
- UIKitView 嵌入的 UIView 没有释放。
- 平台 service 没注入，commonMain 逻辑调用失败。

### 19.8 面试回答模板

如果面试官问“iOS 怎么消费 KMP”，可以这样回答：

> iOS 消费 KMP，本质是把 KMP shared module 编译成 iOS framework 或 xcframework，然后在 Xcode 里引入。Swift/OC 不建议直接到处调用 KMP 内部对象，而是包一层 Swift wrapper。  
> 如果是逻辑共享，KMP 输出 Model、State、Action、Effect，iOS wrapper 把 StateFlow 或 callback 转成 Swift 的 ObservableObject、closure 或 async sequence，SwiftUI/UIKit 订阅后渲染；用户点击再通过 wrapper 调 KMP 的 onAction。  
> 如果是 Compose 共享 UI，则用 ComposeUIViewController 把 KMP Composable 包成 iOS 的 UIViewController，原生页面通过 child view controller 或 SwiftUI wrapper 接入。如果 Compose 内部要嵌 iOS 原生控件，再用 UIKitView。  
> 真正要改造的是构建产物、Swift wrapper、平台 service、生命周期、线程、错误码和监控，而不是只把 framework 引进来就结束。

面试时不需要强调上线状态，重点讲接入原理：

> iOS 消费 KMP 的核心是把 KMP framework 包一层 Swift/OC wrapper。逻辑共享时消费 State 和 Action；Compose 共享 UI 时通常通过 ComposeUIViewController 把 Compose 内容接入 UIKit 层级。如果 Compose 组件内部需要复用 iOS 原生控件，则用 UIKitView 把 UIView 嵌入 Compose，由 Compose 负责布局位置，UIView 仍按 UIKit 机制完成绘制。

## 20. 跨端数据同步进阶

数据同步最怕“字段看起来一样，语义不一样”。

需要统一的内容：

- 字段名。
- 默认值。
- nullable 语义。
- 枚举取值。
- 单位。
- 时间戳精度。
- 埋点字段口径。
- 服务端协议版本。

对象复制适合稳定快照：

```text
Room
  -> KmpRoomSnapshot
  -> commonMain 使用
```

对象代理适合大对象少字段：

```text
KmpRoomProxy
  getRoomId()
  getAnchorId()
  getOwnerUserId()
```

高频字段需要缓存：

```text
platform object
  -> prefetch fields
  -> KMP cache with TTL
  -> update on room change
```

常见坑：

- Android 默认值和 KMP 默认值不一致。
- HarmonyOS 字段缺失时返回 `undefined`，KMP 按空字符串处理。
- iOS wrapper 把 nullable 转错。
- Setting 未注册导致永远取不到服务端值。
- 埋点字段拼装在多端重复实现导致漂移。

## 21. 消息解析和 rawPayload 进阶

直播消息是 KMP 很适合下沉的场景，因为多端最容易出现解析口径不一致。

更稳的链路：

```text
platform message
  -> rawPayload bytes
  -> KMP protobuf parser
  -> KMP business message
  -> RenderState / Effect
  -> platform UI
```

优势：

- 多端共享解析逻辑。
- unknown field 保留更好。
- mock 可以通过 base64 构造。
- 埋点和业务判断口径统一。

需要注意：

- rawPayload 不能无限保存，避免内存膨胀。
- 解析失败要有错误码和降级。
- 消息版本变化要兼容旧字段。
- 高频消息要在 KMP 或平台侧做聚合。
- UI 不要被每条消息直接驱动大范围刷新。

## 22. 设置、AB 和配置同步

直播业务大量依赖 Setting / AB。KMP 下沉后，配置读取要统一，否则多端行为会漂移。

设计方式：

```text
commonMain
  -> KSettingKey<T>
  -> setting service interface

platform actual / service
  -> Android Setting
  -> Harmony Setting
  -> iOS Setting
```

需要保证：

- key 名一致。
- 默认值一致。
- 对象字段序列化一致。
- 注册时机一致。
- debug / mock / server 优先级一致。
- 未注册 key 有明确 fallback。

对象型 Setting 更适合保留整体模型：

```text
live_task_banner_manage_config
  -> LiveTaskBannerManageConfigKmp
  -> config.enable
```

不要为了方便把对象型配置拆成多个自造 boolean key，否则会和服务端真实配置结构脱节。

## 23. 线程和协程

KMP commonMain 常用协程，但不同平台的调度和生命周期并不完全一样。

要关注：

- UI 更新回主线程。
- IO 放后台线程。
- scope 跟随页面或组件生命周期取消。
- 长任务取消后不再回调 UI。
- 多端 dispatcher actual 保持语义一致。

常见错误：

- 使用全局 scope 导致页面销毁后任务继续跑。
- 异步回调回来时平台 View 已释放。
- 多个 collect 重复订阅同一个 StateFlow。
- 线程切换后触碰平台 UI 对象。

建议：

```text
KMP ViewModel owns scope
  -> onAttach start
  -> onDetach cancel or pause
  -> onDestroy release
```

平台 wrapper 负责把生命周期事件转给 KMP。

## 24. 可测试性

KMP 的一个收益是 commonMain 逻辑可以做跨端共享测试。

适合测试：

- reducer。
- state machine。
- message parser。
- setting fallback。
- schema 决策。
- repository mock。
- 埋点参数拼装。

测试结构：

```text
given initial state
when action / message / config
then new state / effect
```

平台差异测试：

- Android actual 是否正确。
- Harmony bridge 类型是否正确。
- iOS wrapper nullable 是否正确。
- sourceSet 是否缺实现。

面试可以说：

> KMP 不是只为了少写代码，更重要是把核心业务状态机变成可测试的公共逻辑，减少多端靠人工对齐。

## 25. KMP 选型边界

KMP 适合收敛业务语义，但不适合替代所有平台能力。

适合：

- 多端一致的业务判断。
- 复杂状态机。
- 消息解析。
- 埋点字段。
- 通用数据模型。
- 跨端配置读取。

不适合：

- 强平台 UI。
- 播放器内核。
- 小窗 / PiP。
- 系统权限。
- 平台动画。
- 硬件能力。

判断方式：

```text
这段逻辑的业务语义是否多端一致？
是否依赖平台生命周期？
是否需要高频访问平台对象？
是否能用 State / Effect 表达？
如果平台差异很大，下沉后是否更复杂？
```

## 26. 可延伸技术点

面试可以准备这些追问：

- KMP 和 RN / Lynx 的根本区别是什么。
- 为什么 KMP 不追求 100% 代码复用。
- commonMain 应该放什么，不应该放什么。
- expect/actual 和接口注入怎么选。
- State 和 Effect 为什么要拆开。
- Compose Runtime 重组怎么影响平台 View。
- AndroidView / UIKitView / ArkUIComponentContent 的成本是什么。
- HarmonyOS 桥接时 nullable 和生命周期怎么处理。
- rawPayload 为什么比 JSON 更适合直播消息。
- 对象复制和对象代理怎么选。
- Setting / AB 怎么保证多端默认值一致。
- KMP 如何做单测和多端一致性验证。

## 27. 面试回答口径

如果问 KMP 渲染：

> KMP 在我们项目里有两种形态。第一种是逻辑共享，commonMain 输出 Model、State、Action，各端用 Compose、ArkUI、SwiftUI/UIKit 自己渲染。第二种是 Compose 共享 UI，KMP 直接写 `@Composable`，但最终仍通过平台容器承载，比如 Android 用 AndroidView / ComposeView，HarmonyOS 用 ArkUIViewTopLayer / ArkUIComponentContent，iOS 用 ComposeUIViewController / UIKitView。

如果问平台容器怎么渲染 KMP 组件：

> 平台容器不是直接解析 KMP 字节码。真正执行 `@Composable` 的是 Compose Runtime。平台容器负责把 Compose 渲染树或平台原生 View 接到本端 UI 树里。比如 AndroidView 是在 Compose 里嵌 Android View，ArkUIComponentContent 是把 ArkTS 创建的 ComponentContent 嵌进 KMP Compose，UIKitView 是把 UIView 嵌进 Compose。

如果问通信：

> 通信本质是状态下发和事件回传。KMP 输出 state，平台 UI 订阅并渲染；用户点击、生命周期、加载结果通过 wrapper / delegate 回传 KMP；KMP 再更新 state 或发 effect 给平台执行具体能力。
