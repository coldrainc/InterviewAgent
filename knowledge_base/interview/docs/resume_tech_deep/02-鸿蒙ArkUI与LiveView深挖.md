# HarmonyOS ArkUI / LiveView 深挖

## 1. 一句话定位

HarmonyOS ArkUI 是鸿蒙声明式 UI 框架；LiveView / 直播组件体系是在 ArkUI 基础上承载直播间复杂业务组件的工程实践。

面试里可以这样说：

> 鸿蒙直播不是简单把 Android UI 翻译成 ArkTS，而是要基于 ArkUI 声明式状态模型，重新处理直播场景里的组件生命周期、状态刷新、跨组件通信和性能边界。

## 2. ArkUI 的核心原理

ArkUI 是状态驱动 UI：

```text
State / Prop / Link / Observed
  -> build() 声明 UI
  -> 状态变化触发局部刷新
  -> 组件树重新计算相关节点
  -> 渲染层更新屏幕
```

核心思想：

- UI 是状态的函数。
- `build()` 只描述 UI，不应该产生副作用。
- 真正驱动 UI 的数据才应该是状态。
- 生命周期、事件、消息回调中修改状态。

和传统 Android View 的区别：

| 维度 | Android View | ArkUI |
|---|---|---|
| UI 更新 | 手动 findView / setText / notify | 状态变化驱动 |
| 组件声明 | XML / View 构造 | `build()` 声明式 |
| 状态 | ViewModel / LiveData / MutableState | `@State / @Prop / @Link / @Observed` |
| 性能风险 | 过度 notify / View 泄漏 | 状态粒度过大 / build 副作用 / 冗余刷新 |

## 3. 直播场景的复杂点

直播间相比普通页面复杂在：

- 长连接消息高频。
- 组件多：公屏、礼物、Toolbar、短触、资料卡、弹窗、小窗。
- 房间生命周期长：进房、首帧、切房、退房、前后台。
- UI 层级复杂：Tetris / Element / controller / service 多层协作。
- 性能敏感：掉帧、卡顿、内存泄漏都会被放大。

所以直播组件不能直接把所有字段都挂到 `@State`，否则消息一来就可能触发大范围刷新。

## 4. LiveView / 直播组件落地方式

可以把直播组件拆成四层：

```text
业务数据 / 消息
  -> ViewModel / Controller
  -> ArkUI State Adapter
  -> ArkUI Component / Element
  -> Tetris / 宿主布局挂载
```

典型职责：

- ViewModel：处理业务状态、消息、接口数据。
- Controller：跨组件通信，比如 Toolbar 控制、房间状态、弹窗调度。
- Component / Element：负责 UI 声明和展示。
- Tetris：负责层级、坑位、挂载、卸载。

## 5. 状态管理方案

### 页面局部状态

适合放在组件内：

- loading。
- 是否展开。
- 当前选中 tab。
- 一次性弹窗显示状态。

### 共享业务状态

适合放到 ViewModel / Controller：

- 房间信息。
- 用户状态。
- 小窗状态。
- 短触列表。
- Toolbar 按钮列表。

### 高频消息状态

不能直接整包驱动 UI。

建议：

```text
消息回调
  -> 聚合 / 去重 / 节流
  -> 更新最小 UI 状态
  -> 局部组件刷新
```

例如公屏、点赞、短触变化，都要避免高频消息直接触发整页重渲染。

## 6. 生命周期处理

直播 ArkUI 组件必须关注：

- `aboutToAppear`
- `onAppear`
- `onDisappear`
- `aboutToDisappear`
- 房间进退。
- 前后台切换。
- 组件复用。

常见风险：

- 监听没注销。
- controller 仍持有组件引用。
- 弹窗关闭后回调还在。
- 切房后旧房间消息还在刷新新页面。
- `build()` 中写副作用导致刷新循环。

处理方式：

```text
aboutToAppear
  -> 注册 controller / listener

onAppear
  -> 开始展示相关逻辑

onDisappear
  -> 暂停动画 / 取消可见性监听

aboutToDisappear
  -> remove listener / reset delegate / clear controller
```

## 7. 性能优化细节

### 状态粒度拆分

不要把大对象整体作为状态。

差：

```text
@State roomData
```

更好：

```text
@State title
@State avatarUrl
@State followState
```

只让真正影响 UI 的字段驱动刷新。

### 高频消息降频

直播消息高频，应该：

- 合并重复更新。
- 批量刷新列表。
- 动画和布局解耦。
- 长列表使用懒加载能力。

### build 保持纯读

`build()` 里不要：

- 发请求。
- 写状态。
- 打复杂日志。
- 注册监听。
- 改缓存。

## 8. 面试难点回答

如果问鸿蒙直播 UI 难点：

> 难点不是 ArkUI 语法，而是直播组件的状态和生命周期比普通页面复杂。直播有高频消息、长生命周期、组件复用和跨组件通信，如果状态粒度没拆好，很容易整页刷新；如果生命周期没收口，容易监听泄漏和串房。所以我会把业务状态放到 ViewModel/Controller，UI 只消费最小状态，监听在生命周期里显式注册和清理。

如果问为什么不用 Android 思路直接迁移：

> Android View 是命令式更新，ArkUI 是状态驱动。直接迁移会把很多副作用带进 `build()` 或状态变量里，导致冗余刷新和生命周期混乱。所以鸿蒙侧需要重新按声明式模型拆状态和组件职责。

## 9. 进阶技术细节

### 9.1 ArkUI 渲染链路怎么理解

可以用这个模型解释：

```text
状态变化
  -> 标记依赖该状态的组件脏
  -> 重新执行相关 build 片段
  -> 生成新的组件描述
  -> diff / 更新渲染节点
  -> 布局、绘制、合成
```

重点不是“状态一变整页刷新”，而是：状态依赖范围越大，受影响的 UI 范围越大。所以性能优化首先要做状态依赖收敛。

面试可以这样说：

> ArkUI 的刷新成本主要取决于状态订阅范围。大对象状态、滥用 Link、把无关字段放进 State，都会扩大刷新面。直播场景消息高频，所以我会先拆状态粒度，再决定状态放组件内、ViewModel 还是 Controller。

### 9.2 V1 / V2 状态模型怎么准备

如果被问状态管理，可以按这个角度讲：

- V1 更常见的是 `@State / @Prop / @Link / @Observed / @ObjectLink`。
- V2 更强调更细粒度、更明确的状态归属和对象观测。
- 不管 V1/V2，核心原则都是“谁拥有状态，谁负责修改；UI 只消费状态”。

常见错误：

```text
父组件把大对象 @State 传给多个子组件
  -> 任意字段变化可能影响大范围刷新

子组件用 @Link 直接改父对象
  -> 状态修改路径不清晰

build() 里派发 action / 写缓存
  -> 可能触发递归刷新或不稳定副作用
```

更稳的做法：

```text
ViewModel / Controller
  -> action 修改状态
  -> UI 订阅最小字段
  -> build 只读状态
```

### 9.3 直播 Tetris / Element 与 ArkUI 的关系

直播不是单页面直接堆组件，通常会有 Tetris 这样的分层挂载系统。

```text
LiveContext
  -> Controller / Service
  -> Tetris Layer
  -> Element Descriptor
  -> Element 实例
  -> ArkUI Component
```

可以这样理解：

- **Tetris** 管“挂在哪里、什么时候挂、层级关系”。
- **Element** 管“这个业务组件是什么、生命周期怎么走”。
- **ArkUI Component** 管“UI 怎么画”。
- **Controller / Service** 管“跨组件业务通信”。

这样拆的好处：

- 新增业务组件不直接改直播主页面。
- 横竖屏、看播/主播、节目房可以按坑位配置。
- 组件销毁时能统一清理资源。

### 9.4 什么时候用普通组件，什么时候用 FrameNode / NodeController

普通 ArkUI 组件适合大部分静态或中低频 UI。

高频动态 UI 可以考虑更底层的节点方案，例如：

- 高频动画。
- 大量动态插入/删除节点。
- 重复创建成本高的列表项。
- 需要绕开整树 diff 的复杂渲染区。

面试可以说：

> 普通业务组件优先用声明式组件，只有当出现高频动态渲染、节点复用、整树 diff 成本明显时，才考虑 FrameNode / NodeController 这类更底层方案。否则会增加维护复杂度。

### 9.5 长列表和高频消息优化

直播常见问题：

- 公屏消息高频。
- 礼物动画高频。
- 点赞特效高频。
- 短触/Toolbar 入口动态变化。

优化思路：

```text
消息入口
  -> 去重 / 合并 / 限频
  -> ViewModel 内维护稳定列表
  -> UI 局部刷新
  -> 动画层和布局层分离
```

具体策略：

- 列表使用懒加载，不做全量渲染。
- item key 稳定，减少复用错乱。
- 动画优先用 opacity / transform，少改宽高。
- 高频事件不要直接触发父组件状态变化。
- 大对象不要跨多层 `@Link` 传递。

### 9.6 内存泄漏排查角度

ArkUI / ArkTS 直播组件常见泄漏点：

- listener 未注销。
- controller 持有组件闭包。
- timer / animation 未停止。
- 弹窗关闭后 callback 持有上下文。
- Hybrid / KMP delegate 没 reset。
- service 单例持有页面对象。

排查思路：

```text
看生命周期
  -> 是否注册和注销成对
看引用链
  -> singleton / controller / closure 是否持有页面
看切房
  -> 旧 room 是否还在回调
看弹窗
  -> dismiss 后是否仍有 listener
```

### 9.7 可以延伸的技术点

面试官如果继续深挖，可以准备这些：

- ArkUI 声明式刷新和 Android View 命令式更新的区别。
- `@State / @Prop / @Link` 的状态归属。
- 高频消息如何避免整页刷新。
- Tetris / Element 为什么能降低直播组件接入成本。
- 组件销毁时如何保证 listener、controller、动画全部释放。
- 为什么 `build()` 里不能写副作用。

