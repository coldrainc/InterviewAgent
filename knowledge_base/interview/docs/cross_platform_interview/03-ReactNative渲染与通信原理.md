# React Native：原理、渲染与通信

## 1. 核心定位

React Native 是 **JS/TS 驱动原生 UI** 的跨端框架。它不是 WebView，而是 JS 描述组件树，最终由 Android / iOS 创建真实原生 View。

```text
JS/TS 组件
  -> React Reconciler 计算变更
  -> Bridge / JSI / Fabric
  -> Native UIManager / Mounting Layer
  -> Android View / iOS UIView
```

一句话：

> RN 复用的是 UI 结构和 JS 业务逻辑，渲染仍然落在各端原生控件上。

## 2. 解决的问题

- 用一套 JS/TS 页面逻辑覆盖 Android / iOS。
- 保留原生 View 的交互体验。
- 通过 Native Module 访问端侧能力。

适合：

- 页面级跨端。
- 业务迭代快、端能力依赖中等的页面。
- 对动态化要求没有 Lynx 那么强的场景。

不适合：

- 高频动画、复杂手势、实时渲染链路。
- 播放器、音视频、直播核心链路等强平台能力。
- JS 和 Native 高频大数据通信场景。

## 3. 老架构原理

老架构核心是三线程 + 异步 Bridge。

```text
JS Thread
  - 执行 JS 业务逻辑
  - setState / props 更新
  - 生成 UI 更新指令

Shadow Thread
  - Yoga 布局计算
  - 生成布局结果

Native / UI Thread
  - 创建和更新原生 View
  - 响应用户交互
```

渲染链路：

```text
JS Component
  -> Virtual Tree
  -> Shadow Tree
  -> Bridge 序列化消息
  -> UIManager
  -> Native View
```

老架构的问题：

- Bridge 异步通信，有序列化 / 反序列化成本。
- JS Thread 忙时，交互响应和 UI 更新会延迟。
- 高频事件、动画、列表滚动容易遇到瓶颈。
- Native 回调 JS 时，页面可能已经销毁，需要防生命周期问题。

## 4. 新架构原理

新架构主要由 JSI、TurboModules、Fabric 组成。

- **JSI**：JS 直接持有 C++ / Native 对象引用，减少传统 Bridge 成本。
- **TurboModules**：Native Module 懒加载，调用链路更直接。
- **Fabric**：新渲染架构，使用 C++ Shadow Tree 和新的 Mounting 流程。

新架构链路：

```text
JS/TS Component
  -> React Reconciler
  -> Fabric Renderer
  -> C++ Shadow Tree
  -> Mounting Layer
  -> Native View
```

新架构收益：

- 减少 Bridge 序列化开销。
- Native Module 可以懒加载。
- 渲染树、布局、挂载流程更统一。
- 更适合并发渲染和复杂页面调度。

但不是没有成本：

- JS Thread 仍然可能成为瓶颈。
- 高频动画仍然要避免 JS 每帧驱动。
- Native Module 仍然要注意线程和生命周期。

## 5. 各端怎么渲染

### Android

Android 侧消费 RN 描述后创建原生 View：

```text
Text       -> TextView
View       -> ReactViewGroup / ViewGroup
Image      -> ImageView / 图片组件
ScrollView -> ScrollView / 列表容器
```

渲染过程：

```text
JS 声明组件树
  -> RN 计算 diff
  -> Android UIManager / Fabric Mounting
  -> 创建或更新 Android View
  -> UI Thread 绘制
```

需要关注：

- UI 操作必须回主线程。
- Native Module 不阻塞 UI Thread。
- 大列表要虚拟化。
- 图片和视频要依赖端侧缓存与释放。

### iOS

iOS 侧消费 RN 描述后创建 UIKit 组件：

```text
Text       -> UILabel
View       -> UIView
Image      -> UIImageView
ScrollView -> UIScrollView
```

渲染过程：

```text
JS 声明组件树
  -> RN 计算 UI 变化
  -> iOS Mounting Layer
  -> 创建或更新 UIView
  -> Main Thread 绘制
```

需要关注：

- UIKit 操作必须在主线程。
- Native 回调 JS 前要确认页面生命周期。
- 大对象跨 JS / Native 传递要控制频率。

## 6. 通信机制

### JS 调 Native

```text
JS 调用 NativeModule.method(params)
  -> Bridge / JSI
  -> Native Module 执行
  -> Promise / callback 返回 JS
```

常见用途：

- 相机、相册、定位、支付。
- 端侧配置、设备信息。
- 调用已有 Native SDK。

风险：

- 高频调用会放大通信成本。
- 参数体积大时序列化成本高。
- 页面销毁后回调 JS 可能导致异常。

### Native 发事件给 JS

```text
Native EventEmitter
  -> Bridge / JSI
  -> JS Listener
  -> 更新 state
  -> 触发 UI 更新
```

常见用途：

- 网络变化。
- 播放状态。
- 系统事件。
- IM / push。

注意：

- listener 要跟随页面销毁注销。
- 高频事件需要节流、合并或放到 Native 层处理。

## 7. 性能优化要点

- 减少 JS 和 Native 高频通信。
- 大数据避免反复跨 Bridge 传输。
- 列表使用虚拟化和分页。
- 动画尽量原生驱动。
- JS Thread 不做重计算。
- Native Module 不阻塞主线程。
- 图片、视频、播放器资源要显式释放。

## 8. 和 Lynx / KMP 的区别

| 技术 | 复用内容 | 渲染方式 | 典型场景 |
|---|---|---|---|
| React Native | UI 结构 + JS 逻辑 | 原生 View | App 页面跨端 |
| Lynx | 动态页面 / 活动逻辑 | Lynx 引擎 + 端侧渲染后端 | 活动页、运营卡片、动态容器 |
| KMP | 业务逻辑 / 状态 / 模型 | 各端原生 UI 自己渲染 | 多端业务逻辑复用 |

## 9. 面试口径

如果问「RN 渲染原理」：

> RN 不是 WebView。它是 JS 描述 UI，React Reconciler 计算变化，再通过 Bridge 或新架构的 JSI/Fabric 把更新传到 Native，最终 Android 创建 Android View，iOS 创建 UIView。

如果问「RN 性能瓶颈」：

> 主要是 JS Thread 和 JS-Native 通信。高频事件、大数据传输、依赖 JS 每帧驱动的动画都会有风险。优化方向是减少跨端通信、列表虚拟化、动画原生化、Native Module 不阻塞主线程。

