# KMP：原理、渲染与通信

## 1. 核心定位

KMP（Kotlin Multiplatform）不是跨端 UI 框架，它的核心价值是 **复用业务逻辑**。

```text
KMP commonMain
  -> 共享 Model / ViewModel / State / Event / Business Logic
  -> expect / actual 或接口注入处理平台差异
  -> Android / HarmonyOS / iOS 各端消费状态
  -> 各端原生 UI 渲染
```

一句话：

> KMP 统一的是业务语义和状态，不统一 UI 像素；各端仍然用自己的原生 UI 渲染。

## 2. 它解决什么问题

直播互动类业务过去容易多端重复实现：

- Android 写一套。
- HarmonyOS 写一套。
- iOS 再写一套。

问题是：

- 业务逻辑重复。
- 状态机容易漂移。
- 消息解析口径不一致。
- 埋点字段容易漏。
- 多端 bug 修复需要重复投入。

KMP 的目标：

- 业务逻辑写一份。
- 多端共享 Model / ViewModel / State。
- 平台相关能力通过 expect / actual 或接口注入分叉。
- 各端通过 wrapper / bridge 消费同一份业务状态，并使用各自原生 UI 渲染。

## 3. 基本工程结构

典型结构：

```text
commonMain
  - 共享业务逻辑
  - 数据模型
  - ViewModel
  - 状态机
  - 消息解析
  - 埋点参数
  - service 抽象

androidMain
  - Android 平台实现
  - Compose / View 接入
  - Android SDK 能力

harmonyMain / ohosMain
  - HarmonyOS 平台实现
  - ArkTS bridge / wrapper
  - ArkUI 接入

iosMain
  - iOS 平台实现
  - Swift / OC bridge
  - UIKit / SwiftUI 接入
```

常见机制：

- `expect / actual`：共享层定义预期能力，平台侧给实际实现。
- 接口注入：共享层只依赖接口，平台侧注入真实服务。
- sourceSet 隔离：不同宿主、不同平台用不同实现，避免依赖污染。
- 导出桥接：把 Kotlin 类型和接口暴露给 ArkTS / Swift / OC。

## 4. 什么适合下沉到 KMP

适合下沉：

- Model / DTO。
- ViewModel。
- 状态机。
- 消息解析。
- 网络请求封装。
- KV / Setting 抽象。
- 埋点参数拼装。
- schema 业务拼接。
- 业务判断逻辑。

不适合强行下沉：

- 原生 UI 细节。
- 播放器。
- 强系统生命周期。
- 平台 SDK 调用。
- 复杂动画。
- 端侧资源加载。

判断原则：

> 业务逻辑下沉，平台能力分叉。

## 5. 渲染原理

KMP 在项目里有两种消费方式，不能简单说“完全不渲染 UI”。

第一种是 **逻辑共享模式**：KMP 只输出状态和事件，各端用自己的原生 UI 渲染。

```text
Backend / IM / InitParams
  -> KMP Repository / Service
  -> KMP ViewModel
  -> State / RenderConfig / Event / Action
  -> 平台侧 UI 消费
  -> Android Compose / View
  -> HarmonyOS ArkUI
  -> iOS SwiftUI / UIKit
```

第二种是 **Compose 共享 UI 模式**：组件本身用 Compose Multiplatform 写在 KMP 侧，各端把这个 Compose 组件嵌进自己的原生容器里展示。

```text
KMP @Composable
  -> commonMain 共享 UI 结构和状态
  -> androidMain actual 用 AndroidView / ComposeView 承载原生 View
  -> ohosArm64Main actual 用 ArkUIViewTopLayer / ArkUIComponentContent 承载 ArkUI 内容
  -> iosMain 可通过 Compose Multiplatform / UIKit 容器承载
```

所以更准确的说法是：

> KMP 可以只共享业务逻辑，也可以共享 Compose 组件；但最终落到屏幕上时，仍然需要各端通过自己的 View 容器、渲染后端和平台桥接来承载。

## 6. Android 端怎么消费

Android 端常见有三种消费方式。

### 逻辑共享 + Compose 渲染

```text
KMP ViewModel
  -> StateFlow / Observable State
  -> Android Wrapper / Delegate
  -> Compose collectAsState
  -> Compose UI 渲染
```

适合：

- 新组件。
- 状态驱动 UI。
- 需要和 KMP ViewModel 绑定较深的场景。

### 逻辑共享 + 原生 View 渲染

```text
KMP ViewModel
  -> callback / observer
  -> Android Widget / View
  -> update view
```

适合：

- 老组件迁移。
- 已有 View 体系。
- 需要和原生容器、Tetris、Widget 复用的场景。

### Compose 共享 UI + Android 原生承载

```text
KMP @Composable
  -> androidMain actual
  -> AndroidView / ComposeView
  -> 嵌入 Android View 树
  -> Android 原生容器负责生命周期和挂载
```

以 `KmpHybridCard.android.kt` 为例，KMP 侧暴露 `@Composable actual fun KmpAnniexLynxCard(...)`，内部通过 `AndroidView` 承载 Android 侧 `HybridCard`。也就是说，UI 入口是 KMP Compose 组件，但真正的 Lynx/Web 容器仍由 Android 原生能力创建和渲染。

Android 侧职责：

- 创建 KMP ViewModel。
- 订阅状态。
- 把点击、生命周期、曝光等事件回传 KMP。
- 调用 Android 原生能力，如 ImageLoader、播放器、schema、Hybrid 容器。
- 在 Compose 共享 UI 模式下，用 `AndroidView` / `ComposeView` 把平台 View 接入 Compose 树。

## 7. HarmonyOS 端怎么消费

HarmonyOS 端也有两类方式：状态消费，或者承载 KMP Compose 组件。

### 逻辑共享 + ArkUI 渲染

```text
KMP exported class / interface
  -> ArkTS wrapper / service bridge
  -> ArkTS State / ViewModel adapter
  -> ArkUI 组件渲染
```

### Compose 共享 UI + ArkUI 内容承载

```text
KMP @Composable
  -> ohosArm64Main actual
  -> ArkTS service 创建 ComponentContent
  -> ArkUIViewTopLayer
  -> ArkUIComponentContent
  -> 挂载到 HarmonyOS UI 树
```

以 `KmpHybridCard.ohosArm64.kt` 为例，KMP 侧同样暴露 `@Composable actual fun KmpAnniexLynxCard(...)`。它通过 `kmpService<IKmpLiveAnniexLynxCardServiceHarmony>()` 调 ArkTS/Harmony 侧服务创建 Lynx 卡片，再用 `ArkUIViewTopLayer` 和 `ArkUIComponentContent` 把 ArkTS 返回的 `ComponentContent` 嵌进 Compose 渲染层。

这里的关键点是：

- Compose 组件结构和生命周期在 KMP 侧组织。
- 实际 Lynx/Web 卡片由 HarmonyOS ArkTS 服务创建。
- ArkUI 内容通过 `ArkUIComponentContent` 挂进 KMP Compose 组件树。
- `DisposableEffect` 负责 bind / reset delegate，避免控制器泄漏。
- `onRelease` 负责释放 controller 和 `ComponentContent`，避免复用已 dispose 的句柄。

HarmonyOS 侧职责：

- 通过导出的 KMP 接口拿业务状态。
- 把 KMP State 转成 ArkUI 可观察状态。
- ArkUI 根据状态渲染。
- 点击、曝光、生命周期通过 ArkTS bridge 回传 KMP。
- 平台能力如路由、图片、Hybrid、KV、Setting 由 ArkTS actual / service 实现。
- 在 Compose 共享 UI 模式下，通过 ArkTS service 创建平台内容，再由 KMP Compose 层承载。

注意点：

- ArkTS 强静态类型，不适合把动态 JSON 对象随意向上传。
- KMP 可空类型到 ArkTS 侧要明确归一。
- ArkUI 状态更新要控制粒度，避免冗余刷新。
- KMP 侧不能直接依赖 `ohos.`，平台能力通过接口或 expect / actual 注入。

## 8. iOS 端怎么消费

iOS 端消费 KMP 的核心是通过 KMP Framework 暴露 Kotlin 共享逻辑，再由 Swift / OC 层封装成 iOS UI 可消费的状态和事件。

```text
KMP Framework
  -> Swift / OC Bridge
  -> ObservableObject / delegate / callback
  -> SwiftUI / UIKit 渲染
```

iOS 侧职责：

- 通过 KMP Framework 获取共享 Model / ViewModel。
- Swift / OC 封装平台能力。
- SwiftUI / UIKit 消费 KMP 输出状态。
- 点击、生命周期、业务事件回传 KMP。

## 9. 通信机制

### KMP 调平台

方式 1：`expect / actual`

```kotlin
// commonMain
expect class PlatformKV {
    fun getString(key: String): String
}

// androidMain / harmonyMain / iosMain
actual class PlatformKV {
    actual fun getString(key: String): String {
        // 调平台 KV
    }
}
```

适合：

- 平台能力差异明确。
- 各端实现都比较稳定。

方式 2：接口注入

```text
commonMain 定义 interface
  -> 平台侧实现
  -> 初始化时注入 KMP
  -> KMP 只依赖抽象
```

适合：

- 能力较多。
- 需要 mock。
- 不同宿主实现不同。

### 平台调 KMP

```text
平台 UI 点击 / 生命周期 / 消息回调
  -> wrapper / bridge
  -> KMP ViewModel.handleAction()
  -> KMP 更新 State
  -> 平台 UI 重新渲染
```

典型事件：

- onAppear / onDisappear。
- onClick。
- onLoadSuccess / onLoadError。
- onMessage。
- onDestroy。
- onExposure。

### KMP 发事件给平台

```text
KMP ViewModel
  -> Action / Effect / Callback
  -> 平台侧处理
  -> open schema / show toast / load hybrid / report log
```

适合：

- 打开 schema。
- 拉起 Hybrid。
- 上报平台埋点。
- 更新宿主布局计数。
- 调用平台图片能力。

## 10. 数据同步方案

跨端数据同步的核心问题是：Room / User / Message 这类对象大、字段多、端侧模型有差异。

不能一刀切。

### 对象复制

```text
Native Object
  -> 转换成 KMP Model
  -> KMP 内部持有完整副本
```

适合：

- 需要遍历大量字段。
- 数据体积可控。
- 访问频率高。
- 希望 KMP 内部访问快。

问题：

- 序列化成本高。
- 内存占用更大。
- 字段同步成本高。

### 对象共享 / 代理

```text
KMP Model Proxy
  -> 访问字段时通过 bridge 回平台取值
  -> 可结合 prefetch / TTL 缓存
```

适合：

- 大对象少字段访问。
- 不希望复制完整对象。
- 平台对象生命周期可控。

问题：

- 单次字段访问有 bridge 成本。
- 高频访问需要缓存。
- 生命周期要避免持有已销毁对象。

### 推荐判断

| 场景 | 方案 |
|---|---|
| 小对象、高频、多字段 | 对象复制 |
| 大对象、少字段、低频 | 对象共享 / 代理 |
| 高频核心字段 | prefetch + TTL 缓存 |
| 生命周期复杂对象 | 尽量复制关键字段，避免长期代理 |

## 11. 消息通信：为什么用 rawPayload / Protobuf

直播消息源头通常是 Protobuf。

如果转成 JSON：

- 可能丢未知字段。
- 特殊类型容易转换错。
- Android / HarmonyOS 解析口径可能不一致。
- 多一层转换成本。

使用 `rawPayload / Protobuf`：

```text
原始 IM Message
  -> rawPayload bytes
  -> KMP 按 Protobuf 解码
  -> 生成共享 Message Model
  -> ViewModel 更新 State
```

收益：

- 字段不丢。
- 双端解码一致。
- 避免 JSON 中间层。
- 更接近服务端消息原始语义。

调试问题：

- bytes 不好手写。
- 所以可以提供 `raw_payload_base64` mock 通道，便于测试注入。

## 12. TaskBanner 举例

TaskBanner 可以这样理解：

```text
IM / Backend / InitParams
  -> KMP ViewModel
  -> 解析 banner 数据
  -> 计算 RenderConfig
  -> 拼接 schema
  -> 控制埋点口径
  -> 输出 State / Action
```

Android：

```text
KMP State
  -> Android Delegate / Widget
  -> Compose / View 渲染
  -> click / show / load callback 回传 KMP
```

HarmonyOS：

```text
KMP Exported Interface
  -> ArkTS wrapper
  -> ArkUI State
  -> ArkUI 组件渲染
  -> JSB / Hybrid / lifecycle 事件回传 KMP
```

平台侧保留：

- 原生 UI 渲染。
- 图片加载。
- Hybrid 容器打开。
- 宿主布局联动。
- 平台埋点出口。
- 生命周期绑定。

KMP 统一：

- 数据解析。
- 状态机。
- schema 拼接。
- 埋点口径。
- 模式判断。
- 行为决策。

## 13. 和 RN / Lynx 的区别

| 技术 | 核心复用 | 渲染方式 | 通信方式 |
|---|---|---|---|
| RN | UI + JS 逻辑 | JS 描述，Native View 渲染 | Bridge / JSI |
| Lynx | 动态页面 / 前端逻辑 | Lynx 引擎布局，各端渲染后端 | JSB / 容器事件 |
| KMP | 业务逻辑 / 状态 / 模型 / 部分 Compose UI | 状态由原生 UI 渲染；Compose UI 由平台宿主容器承载 | expect/actual、接口注入、bridge |

面试里可以这样总结：

> RN 和 Lynx 都更接近 UI / 页面跨端或动态化；KMP 的核心是业务逻辑跨端，但在 Compose Multiplatform 场景下也可以共享部分 UI 组件。区别是，KMP 里的 Compose 组件最终仍需要 AndroidView、ArkUIViewTopLayer、UIKit 容器等平台承载能力来落地渲染。

## 14. 平台容器如何渲染 KMP Compose 组件

这里要区分两个概念：

- **KMP Compose 组件**：Kotlin 里写的 `@Composable`，编译到不同平台。
- **平台宿主容器**：Android / HarmonyOS / iOS 上负责把 Compose 渲染结果挂进本端 UI 树的容器。

不是 `UIKit`、`AndroidView`、`ArkUIViewTopLayer` 自己“理解 KMP 语法”。真正理解 `@Composable` 的是 **Compose Runtime + Compose Compiler 生成的代码**。平台容器做的是承载和互操作。

### 14.1 Android：ComposeView / AndroidComposeView / AndroidView

Android 上有两条路径。

第一条是纯 Compose 组件渲染：

```text
KMP @Composable
  -> Compose Runtime 执行组合
  -> 生成 Compose LayoutNode 树
  -> Android Compose 渲染后端
  -> AndroidComposeView / ComposeView 挂到 Android View 树
  -> Canvas / RenderNode 绘制到屏幕
```

这里 `ComposeView` 可以理解成 Android View 体系里的宿主，它把 Compose 世界接到 Android 原生 View 树里。

第二条是 Compose 里嵌原生 View：

```text
KMP @Composable
  -> Android actual 实现
  -> AndroidView(factory = { nativeView })
  -> Compose 测量 / 布局这个 Android View
  -> nativeView 自己按 Android View 机制渲染
```

`AndroidView` 的作用不是渲染 Compose，而是 **在 Compose 树里嵌一个 Android 原生 View**。你的 `KmpHybridCard.android.kt` 就是这种模式：KMP 提供 `@Composable actual fun KmpAnniexLynxCard`，内部用 `AndroidView` 承载 Android 侧 `HybridCard`，真正的 Lynx/Web 卡片还是 Android 原生容器渲染。

### 14.2 HarmonyOS：ArkUIViewTopLayer / ArkUIComponentContent

HarmonyOS 上也类似，但宿主是 ArkUI 内容。

链路可以理解成：

```text
KMP @Composable
  -> Compose Runtime for HarmonyOS 执行组合
  -> KMP actual 调 ArkTS service
  -> ArkTS 创建 ComponentContent
  -> ArkUIViewTopLayer 创建平台互操作层
  -> ArkUIComponentContent 包装 ComponentContent
  -> 挂到 HarmonyOS UI 树 / top layer
```

你的 `KmpHybridCard.ohosArm64.kt` 里就是这个模式：

```text
KmpAnniexLynxCard
  -> kmpService<IKmpLiveAnniexLynxCardServiceHarmony>()
  -> service.createLynxCardView(params)
  -> ArkInstance(napi_value)
  -> ArkUIViewTopLayer
  -> ArkUIComponentContent
```

几个关键点：

- `service.createLynxCardView(params)` 由 Harmony/ArkTS 侧创建真实卡片内容。
- KMP Compose 侧负责组合、生命周期和尺寸挂载。
- `ArkUIViewTopLayer` 提供 Compose 与 ArkUI 的互操作挂载层。
- `ArkUIComponentContent` 把 ArkTS 返回的 `ComponentContent` 包成 Compose 可放置的内容。
- `DisposableEffect` 做 controller bind / reset，避免 KMP controller 持有旧 delegate。
- `onRelease` 里释放 controller 和 view，避免复用已 dispose 的 ArkUI 句柄。

所以 HarmonyOS 不是把 Kotlin UI 直接变成 ArkTS 代码，而是通过 Compose Runtime 和 ArkUI interop，把平台创建的 ArkUI 内容挂进 KMP Compose 组件树。

### 14.3 iOS：ComposeUIViewController / UIView / UIKitView

iOS 上常见也是两条路径。

第一条是 Compose 组件整体由 UIKit 宿主承载：

```text
KMP @Composable
  -> Compose Runtime for iOS 执行组合
  -> Skia / Metal 等渲染后端绘制
  -> ComposeUIViewController / UIView 承载
  -> 加入 UIKit ViewController / View 层级
```

这里 `UIViewController / UIView` 是宿主，负责把 Compose 渲染面接到 iOS 页面结构里。

第二条是 Compose 里嵌 UIKit 原生 View：

```text
KMP @Composable
  -> UIKitView(factory = { UIView() })
  -> Compose 负责测量和摆放
  -> UIView 自己按 UIKit 机制渲染
```

这和 Android 的 `AndroidView` 类似：`UIKitView` 是互操作组件，用来把 UIKit View 嵌进 Compose 组件树。

### 14.4 这套机制怎么通信

不管 Android / HarmonyOS / iOS，本质都是同一套闭环：

```text
平台容器创建
  -> KMP Compose 组件进入 composition
  -> remember / DisposableEffect 绑定平台 controller
  -> 平台 View / ArkUI Content / UIKit View 创建
  -> 用户交互或生命周期回调
  -> delegate / callback 回传 KMP controller
  -> KMP 更新 state 或发 effect
  -> Compose recomposition 或平台 View update
  -> onDispose / onRelease 释放平台资源
```

面试里可以这样总结：

> 平台容器不是直接“渲染 KMP 字节码”。KMP 的 `@Composable` 会被 Compose Runtime 执行，生成可布局、可更新的 Compose 节点；平台宿主负责把这些节点或平台原生 View 接入本端 UI 树。Android 用 ComposeView 承载 Compose，用 AndroidView 嵌原生 View；HarmonyOS 用 ArkUIViewTopLayer / ArkUIComponentContent 承载 ArkTS 创建的 ComponentContent；iOS 用 ComposeUIViewController / UIView 承载 Compose，也可以用 UIKitView 嵌 UIKit View。通信上通过 controller、delegate、callback 和 DisposableEffect 绑定生命周期。

## 15. 面试口径

如果问「KMP 怎么渲染」：

> KMP 有两种模式。第一种是逻辑共享模式：KMP 输出 Model、State、Action，各端用 Compose、ArkUI、SwiftUI/UIKit 自己渲染。第二种是 Compose 共享 UI 模式：组件用 KMP Compose 写，但最终仍要通过各端容器承载，比如 Android 用 AndroidView/ComposeView 嵌入原生 View，HarmonyOS 用 ArkUIViewTopLayer/ArkUIComponentContent 承载 ArkTS 创建的 ComponentContent。KMP 统一业务语义和部分 UI 结构，各端负责平台能力和最终渲染。

如果问「其他端怎么消费 KMP」：

> 平台侧一般会有 wrapper 或 delegate。UI 订阅 KMP ViewModel 的状态，用户点击、生命周期、消息回调再通过 wrapper 回传给 KMP。KMP 更新状态后，平台 UI 重新渲染。平台能力比如图片、路由、Hybrid、KV、Setting，不由 commonMain 直接调用，而是通过 expect/actual 或接口注入。

如果问「为什么不是所有东西都 KMP」：

> 因为 KMP 最适合复用稳定的业务逻辑，不适合强行统一平台 UI 和系统能力。直播场景里播放器、动画、页面生命周期、系统能力差异很大，强行下沉会增加复杂度。所以我的原则是业务逻辑下沉，平台能力分叉。
