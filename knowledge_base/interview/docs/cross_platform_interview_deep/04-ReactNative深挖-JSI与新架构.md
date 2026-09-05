# React Native 深入版：原理、渲染与通信

## 1. 一句话定位

React Native 是 **JS/TS 驱动 Native UI** 的跨端框架。

它不是 WebView。开发者用 React 写组件，运行时通过 RN 的渲染管线把组件映射成 Android / iOS 原生 View。

```text
React JS Component
  -> React Reconciler
  -> Shadow Tree
  -> Native UI Tree
  -> Android View / iOS UIView
```

一句话讲清楚 RN 渲染：

> RN 的 JS 代码不直接画像素。JS 代码描述组件树，React Reconciler 计算变化，RN 把这些变化转换成 Native View 的创建、属性更新和布局更新，最终由 Android / iOS 原生渲染系统完成绘制。

## 2. RN 解决的问题

RN 主要解决三类问题：

- 页面级跨端：同一套 JS/TS 页面逻辑复用到 Android / iOS。
- 动态迭代：业务代码可以通过 JS bundle 更新，减少纯 Native 发版依赖。
- 生态复用：复用 React 状态管理、组件化、工程生态。

但 RN 不适合把所有 Native 能力都抹平。高性能播放器、复杂手势、直播间强生命周期能力，通常仍需要 Native Module 或原生组件承接。

## 3. 老架构渲染原理

老架构可以理解成三条线程协作：

```text
JS Thread
  -> 执行 React 代码、状态变更、diff

Shadow Thread
  -> 构建 Shadow Tree、计算布局

UI Thread
  -> 创建 / 更新 Native View
```

完整链路：

```text
JS Component
  -> setState / props change
  -> React Reconciler 计算差异
  -> 生成 UI 更新指令
  -> Bridge 序列化传给 Native
  -> UIManager 批量创建 / 更新 Native View
  -> Android / iOS 原生渲染
```

老架构里的关键成本：

- JS 和 Native 通过 Bridge 异步通信。
- 参数通常需要序列化 / 反序列化。
- 高频事件会挤压 Bridge。
- UI 更新是批处理，时序调试复杂。

更细地拆，RN 老架构一次 UI 更新会经历这几个阶段：

```text
1. JS render 阶段
   React Component 执行 render
   生成 React Element Tree

2. Reconcile 阶段
   React 比较新旧 Element
   找到需要新增、删除、更新的节点

3. Shadow Tree 阶段
   RN 为每个 Native 组件建立 Shadow Node
   Shadow Node 不是真实 View，而是 Native UI 的中间描述

4. Layout 阶段
   Yoga 根据 flexbox 样式计算每个节点的位置和尺寸

5. Bridge 批量提交
   把 createView / updateView / manageChildren 等指令序列化
   通过 Bridge 发到 Native

6. UIManager 执行
   Native 侧根据指令创建或更新 Android View / iOS UIView

7. 平台绘制
   Android 走 measure / layout / draw
   iOS 走 layoutSubviews / CoreAnimation 合成
```

这里最容易混淆的是：React Element、Shadow Node、Native View 不是同一个东西。

| 层级 | 是什么 | 作用 |
|---|---|---|
| React Element | JS 里的 UI 描述 | 表示想要什么 UI |
| Shadow Node | Native 侧布局树节点 | 保存样式、属性、布局信息 |
| Native View | 平台真实视图对象 | 最终显示到屏幕 |

所以 RN 的渲染不是“JS 画 UI”，而是：

```text
JS 描述 UI
  -> RN 生成布局和更新指令
  -> Native 创建真实 View
  -> 系统渲染真实 View
```

## 4. 新架构渲染原理

新架构主要引入：

- **JSI**：JS 和 C++/Native 更直接互调，减少传统 Bridge 成本。
- **TurboModules**：Native Module 懒加载、类型化、调用链更轻。
- **Fabric**：新的渲染系统，Shadow Tree 和 Mounting 更现代化。
- **Codegen**：根据接口定义生成跨 JS / Native 的类型绑定。

链路可以理解成：

```text
JS / React
  -> React Reconciler
  -> Fabric Shadow Tree
  -> C++ 层 diff / commit
  -> Mounting Layer
  -> Android View / iOS UIView
```

新架构的目标不是让 RN 没有跨端成本，而是减少 Bridge 的序列化瓶颈，并让 Native Module 和 UI 渲染更同步、更类型化。

Fabric 下可以这样理解一次渲染：

```text
1. JS 侧 React 执行
   生成新的 React Element / Fiber 变化

2. C++ Shadow Tree 更新
   Fabric 使用更统一的 C++ Shadow Tree 表达 Native UI

3. Diff / Commit
   计算新旧 Shadow Tree 差异
   形成一次 commit

4. Mounting Transaction
   把差异转换成平台可执行的 mount 指令

5. 平台 UI 执行
   Android 创建 / 更新 View
   iOS 创建 / 更新 UIView
```

Fabric 和老架构最大的差异不是“最终渲染对象变了”。最终仍然是 Android View / iOS UIView。差异在于中间层：

- 老架构依赖 Bridge 批量发送 UI 指令。
- Fabric 用 C++ Shadow Tree 和 Mounting Layer 组织 UI 更新。
- 新架构更强调类型化、同步测量、更少序列化和更清晰的 commit。

可以用这句话回答：

> Fabric 没有改变 RN 最终渲染 Native View 的事实，它改变的是从 React 树到 Native View 更新之间的中间层，让 diff、layout、commit、mount 更统一、更低成本。

## 5. Android 端怎么渲染

Android 侧 RN 页面通常挂在一个 `ReactRootView` 里。

```text
Activity / Fragment
  -> ReactRootView
  -> ReactInstanceManager
  -> JS Bundle
  -> UIManager / Fabric
  -> Android ViewGroup / TextView / ImageView / 自定义 Native View
```

Android 端真实渲染的是 Android View：

- RN `<Text>` 映射到 Android 文本组件。
- RN `<Image>` 映射到 Android 图片组件。
- RN `<View>` 映射到 Android ViewGroup。
- 自定义 Native Component 可以映射到业务自定义 View。

如果 RN 组件里需要直播播放器，通常不会用 JS 自己画播放器，而是封装 Native View：

```text
JS <LivePlayerView>
  -> Native Component Manager
  -> Android LivePlayerView
  -> 播放器 SDK 渲染
```

## 6. iOS 端怎么渲染

iOS 侧通常通过 `RCTRootView` 承载 RN 页面。

```text
UIViewController
  -> RCTRootView
  -> JS Bundle
  -> UIManager / Fabric
  -> UIView / UILabel / UIImageView / 自定义 Native View
```

iOS 真实渲染的是 UIKit 组件：

- RN `<Text>` 映射到 UILabel / Text 相关组件。
- RN `<Image>` 映射到 UIImageView。
- RN `<View>` 映射到 UIView。
- 复杂平台能力由 Native Module / Native Component 承接。

## 7. RN 怎么通信

### 7.1 JS 调 Native

老架构：

```text
JS
  -> NativeModules.xxx.method(params)
  -> Bridge 序列化
  -> Native Module
  -> callback / Promise 回 JS
```

新架构：

```text
JS
  -> TurboModule typed call
  -> JSI / C++
  -> Native 实现
  -> Promise / callback / sync return
```

常见用途：

- 打开 schema。
- 调用相机、定位、权限。
- 访问播放器、KV、网络。
- 上报埋点。

### 7.2 Native 发事件给 JS

```text
Native Event
  -> EventEmitter
  -> JS listener
  -> setState
  -> RN 重新渲染
```

典型事件：

- 播放状态变化。
- 页面生命周期。
- 网络状态。
- Native 弹窗结果。
- 手势事件。

## 8. 性能关注点

RN 常见性能瓶颈：

- JS Thread 忙导致响应慢。
- 高频事件穿 Bridge，造成通信压力。
- 大列表渲染不当，导致掉帧。
- Native Module 调用过细，频繁跨端通信。
- 图片和视频资源未复用。

优化方向：

- 减少 JS / Native 高频通信。
- 用批量接口替代多次小调用。
- 高性能列表用虚拟化。
- 动画尽量走 Native driver / Reanimated。
- 播放器、地图、复杂手势保留 Native 实现。

## 9. RN 长列表处理详细方案

RN 长列表的核心目标是：**不要一次性渲染全部 item，只渲染屏幕附近的一小段窗口，并且让 item 更新范围尽量小**。

### 9.1 基础选型

常见列表组件：

- `ScrollView`：一次性渲染全部子节点，只适合少量内容。
- `FlatList`：基于 `VirtualizedList` 的常用长列表组件。
- `SectionList`：分组列表，适合带 section header 的场景。
- 第三方高性能列表：如 FlashList / RecyclerListView，适合超大列表或复杂 item。

选型原则：

```text
少量静态内容
  -> ScrollView

普通业务长列表
  -> FlatList

分组长列表
  -> SectionList

超大列表 / item 复杂 / 性能强诉求
  -> FlashList / RecyclerListView / 原生列表
```

### 9.2 虚拟化窗口

`FlatList` 不会把所有 item 都挂到 Native View 树里，而是维护一个渲染窗口。

```text
total data
  -> visible window
  -> overscan before / after
  -> mount visible cells
  -> unmount far cells
```

关键参数：

- `initialNumToRender`：首屏初始渲染数量。
- `maxToRenderPerBatch`：每批最多渲染多少个 item。
- `updateCellsBatchingPeriod`：批量渲染间隔。
- `windowSize`：屏幕外保留多少窗口。
- `removeClippedSubviews`：移除屏幕外子 View。

调参思路：

- 首屏白屏：适当增大 `initialNumToRender`。
- 滚动过程中空白：增大 `windowSize` 或 `maxToRenderPerBatch`。
- 首屏慢：减少初始数量，拆轻 item。
- 内存高：降低 `windowSize`，开启裁剪。

### 9.3 item 稳定性

长列表卡顿很多时候不是列表组件的问题，而是 item 每次都重新 render。

需要保证：

- `keyExtractor` 稳定。
- `renderItem` 引用稳定。
- item 组件用 `React.memo`。
- item props 尽量是基础类型或稳定对象。
- 不在 `renderItem` 内创建复杂闭包和大对象。

推荐结构：

```text
FlatList
  data={ids}
  renderItem={stableRenderItem}
  keyExtractor={stableKeyExtractor}

MemoItem
  -> 只订阅当前 item 需要的数据
  -> 避免订阅整个列表大状态
```

状态管理上，最好让列表只持有 item id 列表，item 自己按 id 获取局部数据，避免一个 item 状态变化导致整个列表 data 引用变化。

### 9.4 固定高度和动态高度

如果 item 高度固定，应该提供 `getItemLayout`：

```text
index
  -> length
  -> offset
```

收益：

- 避免滚动到指定位置时逐个测量。
- 提升 `scrollToIndex` 稳定性。
- 降低布局计算成本。

如果 item 动态高度：

- 尽量把高度类型收敛成有限几类。
- 图片提前知道宽高比。
- 文本限制行数或异步测量缓存。
- 首次测量后缓存 item height。
- `scrollToIndex` 失败时用 `onScrollToIndexFailed` 兜底。

不要让 item 内容加载后频繁改变高度，比如图片加载后才撑开布局，这会导致列表反复 layout 和滚动跳动。

### 9.5 分页、预取和刷新

长列表数据流要拆成三类：

- refresh：刷新首屏。
- load more：加载下一页。
- prefetch：提前加载图片或下一页数据。

常见策略：

```text
onEndReached
  -> 判断 loading / hasMore
  -> 请求下一页
  -> append ids
  -> 保持已有 item 引用稳定
```

注意点：

- `onEndReached` 可能重复触发，要加 loading guard。
- 分页 append 不要重建所有 item 对象。
- refresh 时保留滚动位置要谨慎。
- 图片预加载不要和列表滚动抢主线程。

### 9.6 曝光和滚动事件

长列表常需要做曝光、停留时长、视频自动播放。

推荐使用：

- `onViewableItemsChanged` 做曝光。
- viewability config 控制曝光阈值。
- 曝光事件批量上报。
- 滚动事件节流。

不要做：

- 每一帧 `onScroll` 都 setState。
- 每个 item 单独上报大量事件。
- 曝光后立刻触发重渲染。

更稳的链路：

```text
scroll event
  -> viewability helper
  -> collect visible item ids
  -> batch report
  -> 不驱动列表 UI 大范围更新
```

### 9.7 图片、视频和复杂 item

长列表 item 里最容易拖慢的是图片、视频、富文本、动画。

治理方式：

- 图片设置固定尺寸和占位图。
- 图片使用缓存和预加载。
- 离屏 item 停止动画和视频。
- 可见 item 才加载重资源。
- 富文本解析结果缓存。
- 复杂 item 拆分子组件并 memo。

直播场景里，如果 item 包含播放器、动效或高频消息，通常要考虑原生组件承接，不要把重渲染全部放在 JS 里。

### 9.8 什么时候用原生列表

以下场景可以考虑原生列表或强 Native 组件：

- item 数量非常大。
- item 内有播放器、复杂手势、Surface。
- 滚动和动画要求非常高。
- 曝光、预加载、复用策略强依赖平台能力。
- RN 列表调参后仍无法满足帧率。

面试回答可以这样说：

> RN 长列表首先用 FlatList 做窗口化，控制 initialNumToRender、windowSize、batch size，并通过 stable key、React.memo、getItemLayout、图片预加载、曝光批量上报来降低 JS 和 Native 压力。如果 item 很重，比如播放器、复杂手势或直播高频消息，就不硬撑 RN，应该下沉为原生组件或原生列表。

## 10. 适合场景

适合：

- 普通业务页面。
- 中等复杂交互页面。
- 需要 Android / iOS 页面逻辑复用。
- 对动态迭代有诉求的模块。

不适合：

- 极高性能播放器主链路。
- 强 Native 生命周期页面。
- 大量实时消息高频渲染场景。
- 对首帧、包体、内存极敏感的核心链路。

## 11. 老架构 Bridge 的细节

RN 老架构里，JS 和 Native 之间的 Bridge 是性能和复杂度的核心来源。

```text
JS Object
  -> serialize
  -> batched message queue
  -> Native deserialize
  -> UIManager / NativeModule
```

Bridge 的特点：

- 异步：JS 调 Native 后通常不会同步拿到结果。
- 批处理：UI 更新会被合并后发送。
- 序列化：复杂对象需要跨边界转换。
- 队列化：JS Thread、Native Modules Thread、UI Thread 之间需要调度。

这会带来几个问题：

- 高频事件会把队列打满，比如滚动、手势、播放器进度。
- JS 侧状态变更不一定立刻反映到 Native View。
- Native 回调过多会反向挤压 JS Thread。
- 调试时要同时看 JS 栈和 Native 栈。

优化思路：

- 一次传完整状态，不要逐字段调用 Native。
- 高频事件只传关键状态，或者端侧聚合后再通知 JS。
- 动画和手势尽量放到 Native / UI Runtime。
- 播放器、地图、相机等重能力做成 Native Component。

## 12. 新架构 Fabric / TurboModule 细节

新架构的核心目标是减少 Bridge 成本，并让 JS / Native 接口更类型化。

### Fabric

Fabric 是新的渲染系统，可以理解成 RN UI 的新 mounting 架构。

```text
React Element
  -> Fiber Tree
  -> Shadow Tree
  -> Diff / Commit
  -> Mounting Transaction
  -> Native View update
```

Fabric 的关键变化：

- Shadow Tree 更接近 C++ 层统一模型。
- commit / mount 链路更清晰。
- 支持更同步的布局和测量能力。
- 与 React Concurrent 能力更容易协作。

### TurboModule

TurboModule 用于替代传统 NativeModule。

优势：

- 按需加载 Native Module。
- 接口通过 Codegen 生成绑定。
- 类型约束更强。
- 调用链更轻。

### JSI

JSI 提供 JS Runtime 和 C++ / Native 的直接互操作能力。

```text
JS Runtime
  -> JSI HostObject / HostFunction
  -> C++ / Native implementation
```

它不等于“所有调用都无成本”。只是减少了传统 Bridge 的 JSON 化和消息队列成本，工程上仍要控制跨边界调用频率。

## 13. RN 布局和渲染提交

RN 布局通常基于 Yoga。

```text
JS 声明 style
  -> Shadow Node
  -> Yoga layout
  -> layout result
  -> Native View frame
```

需要注意：

- RN 的 layout 结果最后还是落到平台 View。
- 大量节点会增加 Shadow Tree 和 Native View 创建成本。
- 频繁 setState 会导致 JS reconcile 成本上升。
- 布局频繁变化会增加 native mounting 压力。

性能优化方向：

- 减少无意义 wrapper View。
- 大列表用虚拟化。
- 列表 item 保持稳定 key。
- 避免在 render 中创建大量新对象和匿名函数。
- 大图、视频、地图交给原生组件处理。

## 14. RN 状态管理和重渲染

RN 页面卡顿很多时候不是 Native 慢，而是 JS 状态变化粒度过粗。

常见问题：

- 一个全局 store 改动触发大范围页面刷新。
- 列表 item 每次都重新 render。
- 高频事件直接 setState。
- selector 没有做 memo。
- props 引用每次都变，导致子组件无法跳过渲染。

治理方法：

- 状态按页面、组件、业务域拆分。
- 高频事件用节流、批处理或端侧聚合。
- 用 memo / useMemo / useCallback 控制引用稳定。
- 长列表 item 拆小并避免订阅全局大状态。
- Native 事件不要直接驱动整页重渲染。

面试可以这样说：

> RN 性能优化不是只看 Bridge，也要看 React 本身的状态粒度。跨端通信少了，但 JS 侧 render 太重一样会卡。

## 15. Native Component 设计

复杂能力一般通过 Native Component 暴露给 RN。

```text
JS <LivePlayerView props={...} />
  -> Component Descriptor / ViewManager
  -> Native View 创建
  -> props update
  -> command / event
```

Native Component 要设计好三类接口：

- props：声明式状态，比如 url、muted、visible。
- command：一次性动作，比如 play、pause、seek。
- event：Native 回调 JS，比如 onFirstFrame、onError。

设计原则：

- props 表达稳定状态。
- command 表达一次性动作。
- event 不要高频轰炸 JS。
- Native View 自己管理强平台生命周期。
- 销毁时释放播放器、listener、Surface。

直播播放器这类场景通常适合：

```text
RN 页面负责业务编排
Native Component 负责播放器渲染和生命周期
Native Module 负责宿主能力
```

## 16. RN 通信协议设计

RN 和 Native 通信要避免“方法散落 + 参数自由拼”的模式。

推荐把通信协议化：

```text
Action
  type
  payload
  traceId

Event
  type
  payload
  timestamp
```

这样做的好处：

- JS 和 Native 都能稳定解析。
- 方便埋点和 trace。
- 方便灰度兼容。
- 出错时能知道是哪类 action。

对于 NativeModule：

- 方法不要过细。
- 参数 DTO 化。
- 错误码统一。
- Promise reject 要带 code。
- 对平台能力差异做 feature detect。

对于 EventEmitter：

- listener 注册和移除必须成对。
- 页面 hide / destroy 时取消订阅。
- 高频事件做端侧聚合。
- 对事件顺序敏感的场景加 sequence。

## 17. RN 启动和包体优化

RN 的启动成本主要来自：

- 加载 JS bundle。
- 初始化 JS Runtime。
- 执行业务代码。
- 创建 RootView。
- 首次布局和 native view mounting。

优化方向：

- bundle 拆分。
- 懒加载低优先级模块。
- 预初始化 RN Runtime。
- 首屏数据前置。
- 减少首屏组件层级。
- 图片资源走缓存。
- 首屏 Native 骨架屏。

需要注意：

> 预加载能降低首屏，但会增加内存常驻。核心链路要看启动耗时和内存之间的取舍。

## 18. 稳定性和排障

RN 排障通常要同时看 JS、Native 和通信三层。

常见问题：

- JS exception。
- Native crash。
- RedBox / white screen。
- Bridge 消息丢失。
- Native Module 未注册。
- Bundle 加载失败。
- 版本不兼容。

需要建设的能力：

- JS 错误上报。
- Native crash 关联 RN 页面。
- bundle 版本记录。
- 页面首屏耗时。
- NativeModule 调用耗时。
- 通信错误码。
- 降级策略。

排查链路：

```text
用户问题
  -> 页面 / bundle version
  -> JS error / native crash
  -> bridge / module call trace
  -> native component lifecycle
  -> data / config / network
```

## 19. 可延伸技术点

面试可以准备这些追问：

- RN 为什么不是 WebView。
- 老架构 Bridge 为什么容易成为瓶颈。
- JSI 解决了什么，没有解决什么。
- Fabric 和传统 UIManager 的区别。
- TurboModule 为什么需要 Codegen。
- RN 页面为什么会白屏，怎么排查。
- Native Component 的 props / command / event 怎么设计。
- 高频播放器进度为什么不适合直接发给 JS。
- RN 动画为什么要尽量脱离 JS Thread。
- RN 和 Lynx 都能动态化，为什么适用场景不同。

## 20. 面试回答口径

如果问 RN 的渲染原理：

> RN 是 JS 驱动 Native UI。JS 层写 React 组件，Reconciler 生成 UI 更新，老架构通过 Bridge 发给 Native UIManager，新架构通过 JSI / Fabric 更直接地更新 Native View。最终屏幕上渲染的是 Android View 或 iOS UIView，不是 WebView。

如果问 RN 怎么通信：

> JS 调 Native 通过 NativeModule，老架构走 Bridge，新架构走 TurboModule / JSI。Native 发 JS 通常通过 EventEmitter。性能上要避免高频小粒度跨端调用，最好批量化、状态化。
