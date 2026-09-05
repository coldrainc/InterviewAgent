# Lynx：原理、渲染与通信

## 1. 核心定位

Lynx 是一套面向端内动态化的高性能渲染引擎。它更适合活动页、运营卡片、直播动态卡片这类「需要快速下发、快速迭代、端上承载」的场景。

```text
Lynx Bundle / Template
  -> Lynx Runtime 执行业务逻辑
  -> 构建 UI Tree
  -> Layout Engine 计算布局
  -> Native Renderer 渲染
  -> Android / iOS / HarmonyOS 端侧视图
```

一句话：

> Lynx 负责动态页面的执行、布局和渲染；端侧负责容器、通参、JSB、生命周期和业务上下文。

## 2. 它解决什么问题

Lynx 主要解决端内动态化：

- 前端页面或卡片可以动态下发，减少发版成本。
- 端侧提供容器能力和 JSB，前端可以调用原生能力。
- 比 WebView 更强调性能、首屏、端内集成和业务容器能力。

适合：

- 活动页、运营卡片、直播玩法卡片。
- 需要频繁迭代的业务页面。
- 需要端侧能力但不适合每次发版的功能。

不适合：

- 强原生体验、复杂播放器、核心音视频链路。
- 极度依赖系统生命周期和原生组件状态的场景。
- 不允许前端动态下发的安全敏感场景。

## 3. 渲染原理

Lynx 渲染可以拆成五步：

```text
1. 加载 Bundle / Template
2. Runtime 执行 JS 逻辑
3. 构建 Element / UI Tree
4. Layout Engine 计算布局
5. Renderer 在各端创建或更新视图
```

更细一点：

```text
业务入口 / schema
  -> LynxView 创建
  -> 加载 template / bundle
  -> JS Runtime 执行
  -> 生成 Lynx UI Tree
  -> 布局计算
  -> Native 渲染后端更新视图
```

Lynx 与 WebView 的区别：

- WebView 主要依赖浏览器内核渲染。
- Lynx 有自己的渲染管线，更强调端内性能和原生能力集成。
- Lynx 更容易和端侧容器、JSB、业务上下文融合。

Lynx 与 React Native 的区别：

- RN 更偏跨端 App UI 框架。
- Lynx 更偏动态化容器，适合活动和运营场景。
- Lynx 页面通常通过 bundle 下发，端侧容器负责运行环境。

## 4. 各端怎么渲染

### Android

```text
业务入口 / schema
  -> LynxView
  -> 加载 Lynx Bundle
  -> Lynx Runtime 执行 JS
  -> Layout Engine 计算布局
  -> Android 渲染后端创建/更新 View
```

Android 端主要提供：

- LynxView 容器。
- JSB / Native Module。
- 页面生命周期。
- 业务通参。
- 图片、网络、路由、存储等端能力。

### iOS

```text
业务入口 / schema
  -> LynxView
  -> 加载 Lynx Bundle
  -> Runtime 执行
  -> Layout + Render
  -> UIKit 侧展示
```

iOS 端主要提供：

- LynxView 容器。
- OC / Swift JSB。
- Native Module。
- 路由、网络、埋点、存储等端能力。

### HarmonyOS

```text
业务入口 / schema
  -> AnnieX / Lynx 容器
  -> 加载前端 bundle
  -> Lynx Runtime 执行
  -> 端侧渲染后端展示
  -> ArkTS 提供 JSB、通参、上下文
```

HarmonyOS 端主要提供：

- AnnieX / Lynx 容器承载。
- ArkTS 侧 JSB。
- 直播 `LiveContext` 注入。
- 生命周期事件分发。
- 通参和业务 service。

## 5. 直播场景下的容器方案

直播里的 Lynx 页面不能只当普通页面打开。它需要直播房间能力：

- `room_id`
- `anchor_id`
- `sec_anchor_id`
- `enter_from_merge`
- `request_id`
- 消息订阅能力
- 房间生命周期
- 前后台 / show-hide / 横竖屏 / 键盘事件
- 分享、路由、礼物、互动等 JSB

推荐理解为：

```text
直播业务入口
  -> WebcastBizContainer
  -> LynxView / WebView / Popup
  -> globalProps 注入通参
  -> extraContainerContext 注入 LiveContext
  -> JSB 读取上下文并调用直播能力
  -> 前端页面渲染和交互
```

## 6. 通参注入

通参注入解决的是：前端页面怎么拿到稳定、正确的直播上下文参数。

```text
LiveGlobalPropsService
  -> 基础通参
  -> App 信息
  -> LiveContext 校正
  -> room_id / anchor_id / sec_anchor_id
  -> 注入 Lynx globalProps
```

为什么要用 `LiveContext` 二次校正：

- Hybrid 页面可能异步加载。
- 容器可能复用。
- 直播间可能切房。
- 参数生成时机可能早于真实房间绑定。

收益：

- 避免前端请求串房。
- 避免埋点归因错误。
- 保证前端和宿主房间口径一致。

## 7. JSB 通信机制

JSB 是 Lynx 页面和 Native / ArkTS 能力之间的桥。

### 前端调端侧

```text
Lynx JS
  -> call JSB
  -> ArkTS / Android / iOS Native Method
  -> 读取 LiveContext / Service / MessageManager
  -> 执行业务能力
  -> callback / Promise 返回前端
```

常见能力：

- 注册消息。
- 获取回放设置。
- 更新回放状态。
- 打开面板。
- 跳转 schema。
- 分享。
- 获取通参。

### 端侧发事件给前端

```text
端侧生命周期 / 业务事件
  -> sendEvent
  -> Lynx 页面监听
  -> 前端更新状态
```

常见事件：

- 容器 show / hide。
- 前后台切换。
- 横竖屏变化。
- 键盘弹起收起。
- 房间消息。
- 容器关闭。

## 8. LiveContext 注入方案

核心设计：

```text
WebcastBizContainer.onShow
  -> 获取当前 LiveContext
  -> 注入 extraContainerContext['liveContext']
  -> JSB 从 extraContainerContext 读取
  -> 调用 messageManager / room service
```

为什么不让 JSB 自己全局查：

- 全局查上下文容易串房。
- JSB 与直播房间耦合会变重。
- 每个 JSB 自己处理生命周期，释放不统一。
- 容器销毁后旧 JSB 可能继续持有旧上下文。

容器层注入的好处：

- 同一容器内所有 JSB 共享同一个上下文。
- 容器是上下文边界，语义更清楚。
- 销毁时可以统一释放监听和状态。
- 降低串房和内存泄漏风险。

## 9. 性能与稳定性优化

### 按需加载

- 只有入口触发时才加载 Lynx / Web 容器。
- 不在直播主链路初始化阶段提前加载重型页面。
- 避免影响进房、开播、首帧等关键路径。

### 通参本地生成

- 通参由端侧统一生成并注入。
- 前端不需要重复请求基础上下文。
- `LiveContext` 校正降低二次请求和纠错成本。

### 生命周期收口

- show / hide / foreground / background 统一由容器派发。
- JSB listener 跟随容器销毁注销。
- stateStore / message listener / callback 不长期持有页面。

### 事件降噪

- 高频生命周期事件只在状态变化时派发。
- 房间消息订阅按需注册，退出时解除。
- 避免前端反复刷新无关 UI。

## 10. 面试口径

如果问「Lynx 渲染原理」：

> Lynx 是动态化渲染引擎。前端 bundle 被端侧 Lynx 容器加载后，Runtime 执行 JS，构建 UI Tree，Layout Engine 计算布局，最后由各端渲染后端创建或更新视图。它不是普通 WebView，更强调端内动态化性能和 Native 能力集成。

如果问「直播 Lynx 容器难点」：

> 难点不是打开 Lynx 页面，而是让前端页面安全消费直播房间能力。直播页面需要通参、生命周期、消息、JSB 和 LiveContext。如果 JSB 各自取上下文，容易串房和泄漏。所以我把通参、LiveContext 注入、JSB 和生命周期都收口到容器层。

如果问「其他端怎么消费」：

> Android / iOS / HarmonyOS 都是通过各自的 Lynx 容器消费同一类前端 bundle。区别在于端侧提供的 JSB 和容器上下文不同。Android 用 Native JSB，iOS 用 OC/Swift JSB，HarmonyOS 用 ArkTS JSB。直播场景下，HarmonyOS 侧会额外把 LiveContext 注入容器，让 JSB 能拿到房间能力。

