# 移动端 H5 / Hybrid / 微前端深挖

## 1. 一句话定位

移动端 Hybrid 是把 Web 技术嵌入 App 的方案；微前端是把多个独立业务前端应用组织在同一个宿主运行时里的工程方案。

面试里可以这样说：

> Hybrid 解决的是动态页面和 Native 能力结合的问题，微前端解决的是多业务独立开发、独立发布、统一接入宿主的问题。

## 2. Hybrid 的基本架构

```text
Native App
  -> WebView / Lynx / AnnieX 容器
  -> H5 / 前端 Bundle
  -> JSBridge 调 Native
  -> Native Event 回前端
```

移动端 Hybrid 一般包括：

- 容器管理：WebView / LynxView 创建、复用、销毁。
- 路由协议：schema / deeplink / universal link。
- 通参注入：设备、用户、房间、业务上下文。
- JSBridge：前端调端能力。
- 生命周期：show / hide / foreground / background / destroy。
- 权限和安全：域名白名单、能力授权、参数校验。

## 3. Hybrid 渲染原理

### WebView

```text
H5 HTML / CSS / JS
  -> WebView 浏览器内核
  -> DOM / CSSOM
  -> layout / paint / composite
  -> 屏幕展示
```

优点：

- Web 标准生态完整。
- 页面动态化能力强。
- 研发成本低。

缺点：

- 首屏和内存受 WebView 影响。
- JSBridge 通信成本高。
- 和 Native 的手势、滚动、生命周期容易冲突。

### Lynx / AnnieX

```text
前端 Bundle
  -> Runtime 执行
  -> UI Tree
  -> Layout Engine
  -> Native Renderer
```

优点：

- 比 WebView 更贴近端侧渲染。
- 容器能力更可控。
- 适合高性能动态卡片。

## 4. JSBridge 通信

JS 调 Native：

```text
JS call
  -> bridge.invoke(method, params)
  -> Native router
  -> Native handler
  -> callback / promise
```

Native 发 JS：

```text
Native Event
  -> container.sendEvent
  -> JS listener
  -> 前端更新状态
```

常见能力：

- 路由跳转。
- 分享。
- 登录态。
- 支付。
- 图片选择。
- 网络请求代理。
- 直播消息订阅。
- 埋点上报。

## 5. 微前端解决什么

当业务多、团队多、页面多时，单一前端工程会出现：

- 构建慢。
- 发布互相影响。
- 技术栈升级困难。
- 不同业务耦合严重。
- 宿主能力接入重复。

微前端的目标：

```text
统一宿主
  -> 多个子应用独立开发
  -> 独立构建 / 发布
  -> 运行时按需加载
  -> 公共能力统一注入
```

## 6. 微前端核心方案

### 应用注册

```text
appId / route / domain
  -> 子应用 manifest
  -> bundle 地址
  -> 权限配置
  -> 运行时加载策略
```

### 路由分发

```text
URL / schema
  -> 宿主路由
  -> 匹配子应用
  -> 加载 bundle
  -> 挂载到指定容器
```

### 运行时隔离

需要隔离：

- JS 全局变量。
- CSS 样式。
- 路由状态。
- storage key。
- 事件总线。
- 权限能力。

隔离方式：

- namespace。
- sandbox。
- scoped style。
- app-level bridge。
- 独立 bundle 上下文。

## 7. 性能优化

### 首屏优化

- 容器预创建。
- bundle 预加载。
- 关键资源 preload。
- 首屏数据前置。
- 骨架屏。

### 包体优化

- 公共依赖拆包。
- 按路由懒加载。
- 资源压缩。
- Tree shaking。
- 动态模块拆分。

### 通信优化

- JSBridge 批量调用。
- 避免高频事件穿桥。
- 状态一次注入，减少重复请求。
- Native event 做节流和去重。

## 8. 稳定性和安全

Hybrid 容器必须关注：

- 域名白名单。
- schema 参数校验。
- JSB 权限控制。
- 页面销毁时注销监听。
- 超时兜底。
- 容器 crash 降级。
- 前端异常上报。

如果是直播或金融等敏感业务，还要注意：

- 用户态隔离。
- 房间上下文隔离。
- 支付能力鉴权。
- 不同业务的 bridge 权限隔离。

## 9. 面试口径

如果问 Hybrid 难点：

> Hybrid 难点不是打开 WebView，而是通参、JSBridge、生命周期、安全和性能的统一治理。前端页面要拿 Native 能力，但不能让每个页面随便调全局能力，所以需要容器层做上下文注入、权限控制和销毁清理。

如果问微前端难点：

> 微前端难点是多应用独立发布和运行时隔离。要解决路由分发、bundle 加载、JS/CSS 隔离、公共能力注入、应用间通信和故障隔离，否则多个子应用跑在一个宿主里会互相污染。

如果结合你的经历讲：

> 我做过移动端 H5 / RN / Hybrid 以及直播容器化能力，重点不是单页面开发，而是容器、通参、JSB、运行时隔离和性能优化这些基础能力。

## 10. Hybrid 容器的完整能力模型

一个成熟 Hybrid 容器不能只包含 WebView / LynxView，还要有完整控制面。

```text
Container Manager
  -> 创建 / 复用 / 销毁容器

Route Resolver
  -> schema / url / bid 解析

Resource Loader
  -> 在线 URL / 离线包 / fallback

Global Props
  -> 通参 / 用户态 / 业务上下文

JSBridge Registry
  -> 能力注册 / 权限 / 参数校验

Lifecycle Dispatcher
  -> show / hide / foreground / background / destroy

Monitor
  -> load time / error / blank screen / JS error
```

面试里要强调：

> Hybrid 的复杂度在控制面，不在 WebView 本身。容器要处理路由、资源、通参、JSB、生命周期、安全、监控和降级。

## 11. 离线包与资源加载

移动端 Hybrid 常用离线包优化首屏和稳定性。

加载优先级可以设计为：

```text
本地命中离线包
  -> 校验版本 / hash
  -> 加载本地资源
  -> 失败 fallback 到线上 URL
  -> 上报命中率和失败原因
```

关键点：

- manifest 描述资源版本。
- hash 校验防止包损坏。
- 灰度控制离线包版本。
- fallback 必须可用，避免白屏。
- 静态资源和接口数据分开缓存。

常见指标：

- 离线包命中率。
- 首屏耗时。
- 白屏率。
- 资源加载失败率。
- fallback 触发率。

## 12. 容器池和预创建

WebView / LynxView 创建成本较高，可以做容器池。

```text
App idle / 页面预热
  -> 预创建容器
  -> 注入基础能力
  -> 等待真实 schema
  -> bind 业务上下文
  -> load 页面
```

收益：

- 降低首次创建耗时。
- 提前完成 Runtime 初始化。
- 提升首屏体验。

风险：

- 预创建过多会增加内存。
- 预注入上下文可能过期。
- 容器复用时容易串业务状态。

控制策略：

- 只预创建空容器，不提前绑定房间上下文。
- bind 时用当前上下文二次校正通参。
- 容器 release 时清理 listener、JSB state、history、delegate。
- 设置最大池大小和过期时间。

## 13. JSBridge 协议设计细节

JSBridge 不建议只是一个 `method + params` 的自由格式，最好做协议化。

```json
{
  "namespace": "live",
  "method": "registerMessage",
  "params": {},
  "callbackId": "cb_001",
  "version": "1.0"
}
```

需要考虑：

- namespace：避免不同业务 method 冲突。
- version：兼容旧前端。
- callbackId：异步回调。
- errorCode：统一错误。
- permission：能力权限。
- timeout：避免 callback 永远不返回。

错误返回建议结构：

```json
{
  "code": 1001,
  "message": "permission denied",
  "data": {}
}
```

## 14. JSBridge 安全设计

安全风险：

- 任意域名调用敏感 JSB。
- schema 参数注入。
- 前端伪造 room_id / user_id。
- JSB 返回敏感信息。
- 调用 Native 能力绕过权限。

防护方式：

- 域名 / bid 白名单。
- JSB 分级授权。
- 参数 schema 校验。
- 敏感能力要求登录态或业务态。
- 返回字段脱敏。
- 所有失败路径上报。

面试可以说：

> JSBridge 本质是前端调用 Native 权限能力，不能当普通函数调用处理。需要从域名、能力、参数、返回值、生命周期五个维度做约束。

## 15. 微前端运行时隔离细节

微前端最难的是隔离，而不是加载。

### JS 隔离

```text
子应用 window
  -> proxy / fake window
  -> set/get 拦截
  -> 卸载时清理新增变量
```

目标：

- 子应用不能污染宿主全局。
- 子应用之间不能覆盖全局变量。
- 卸载后状态可清。

### CSS 隔离

方式：

- CSS Module。
- scoped style。
- Shadow DOM。
- runtime 前缀改写。
- 约定 BEM namespace。

风险：

- 全局 reset 污染宿主。
- 弹窗样式覆盖其它应用。
- z-index 冲突。

### 路由隔离

```text
宿主路由
  -> 子应用 base route
  -> 子应用内部 route
```

需要处理：

- 返回键。
- 刷新恢复。
- 深链进入。
- 子应用卸载时清路由。

## 16. 前端和端侧的状态一致性

复杂 Hybrid 页面常有三份状态：

```text
前端状态
  -> React / Vue / Lynx state

端侧状态
  -> Native / ArkTS / LiveContext

服务端状态
  -> API / 房间状态 / 配置
```

问题：

- 前端开关打开，但端侧 KV 未更新。
- 端侧切房了，前端还拿旧 room_id。
- 服务端配置变了，离线包缓存没更新。

解决：

- 关键状态由端侧作为 source of truth。
- 前端通过 JSB 读写，不绕过端侧。
- 容器 show 时重新校正上下文。
- 关键操作带版本和 room_id 校验。

## 17. 可观测性

Hybrid 必须有完整监控：

- 容器创建耗时。
- bundle 加载耗时。
- 首屏耗时。
- JS error。
- 白屏率。
- JSB 调用成功率。
- JSB 超时率。
- 页面关闭原因。
- fallback 触发原因。

排查白屏时可以按这个顺序：

```text
schema 是否匹配
  -> 容器是否创建
  -> 资源是否加载
  -> JS 是否执行
  -> 首屏节点是否渲染
  -> JSB 是否卡住
  -> 数据接口是否返回
```

## 18. 可延伸技术点

可以准备这些追问：

- WebView、Lynx、RN 在渲染链路上的差异。
- 离线包如何做版本和 fallback。
- JSBridge 如何做权限和参数校验。
- 容器池为什么会导致串上下文，怎么避免。
- 微前端 JS/CSS/路由怎么隔离。
- Hybrid 白屏如何定位。
- 直播容器为什么要注入 LiveContext。

