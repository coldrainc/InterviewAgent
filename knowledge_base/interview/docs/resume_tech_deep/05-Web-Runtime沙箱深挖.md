# WebRuntime / Sandbox 深挖

## 1. 一句话定位

WebRuntime 是承载 Web 插件、脚本、动态能力的运行时；Sandbox 是隔离执行环境，用来限制不可信代码的能力边界。

面试里可以这样说：

> WebRuntime 解决“如何运行动态扩展”的问题，Sandbox 解决“运行动态扩展时怎么保证安全和稳定”的问题。

## 2. 为什么需要 WebRuntime

在复杂平台里，经常需要：

- 让不同业务插件独立开发。
- 动态加载脚本或模块。
- 给插件提供统一宿主能力。
- 统一管理插件生命周期。
- 统一观测日志、错误、性能。

如果所有能力都直接写进主工程，会带来：

- 主工程臃肿。
- 发布耦合。
- 插件之间互相污染。
- 权限不可控。
- 故障影响面大。

## 3. WebRuntime 基础结构

```text
Host App
  -> Runtime Manager
  -> Module Loader
  -> Sandbox Context
  -> Plugin / Web App
  -> Host API / Bridge
```

核心模块：

- **Loader**：加载脚本、bundle、manifest。
- **Runtime Context**：保存插件运行上下文。
- **Bridge / Host API**：给插件调用宿主能力。
- **Sandbox**：隔离全局对象、网络、文件、执行权限。
- **Lifecycle**：init / mount / update / unmount / destroy。
- **Monitor**：日志、错误、耗时、资源占用。

## 4. Sandbox 隔离什么

需要隔离：

- 全局变量污染。
- DOM / BOM 权限。
- 网络访问。
- 文件访问。
- 进程资源。
- 定时器和异步任务。
- 插件间消息。
- 敏感宿主 API。

典型策略：

```text
插件代码
  -> 沙箱上下文执行
  -> 只能访问白名单 API
  -> 所有宿主调用经过权限校验
  -> 异常不影响主进程
```

## 5. 常见 Sandbox 实现思路

### JS Proxy 隔离

```text
window proxy
  -> 拦截 get / set
  -> 插件全局变量写入 fakeWindow
  -> 卸载时清理
```

适合前端微应用隔离。

### iframe 隔离

```text
iframe
  -> 独立 window / document
  -> postMessage 通信
```

隔离强，但通信和样式控制成本更高。

### Worker 隔离

```text
Worker
  -> 独立线程
  -> message 通信
  -> 无 DOM 访问
```

适合计算任务、AI 工具执行、非 UI 插件。

### Node VM / 子进程隔离

```text
主进程
  -> fork / worker_thread / vm
  -> 限制执行上下文
  -> IPC 通信
```

适合桌面端或服务端工具运行。

## 6. 插件生命周期

```text
register
  -> load manifest
  -> create sandbox
  -> mount
  -> run
  -> update
  -> unmount
  -> destroy sandbox
```

生命周期里要处理：

- 定时器清理。
- 事件监听清理。
- 网络请求取消。
- bridge 引用释放。
- 插件状态持久化或丢弃。

## 7. 通信机制

插件调用宿主：

```text
Plugin
  -> bridge.invoke(api, params)
  -> permission check
  -> host handler
  -> result / error
```

宿主通知插件：

```text
Host Event
  -> runtime event bus
  -> sandbox dispatch
  -> plugin listener
```

插件间通信：

```text
Plugin A
  -> runtime bus
  -> permission / namespace check
  -> Plugin B
```

不要让插件直接互相引用，否则会破坏隔离边界。

## 8. 安全设计

重点：

- API 白名单。
- 参数校验。
- 权限分级。
- 超时控制。
- 异常捕获。
- 日志审计。
- 敏感信息脱敏。
- 网络域名限制。

对于 AI Agent / 工具执行场景，还要额外限制：

- 文件读写范围。
- 命令执行权限。
- 网络访问权限。
- token / secret 访问。
- 输出内容安全。

## 9. 性能优化

- Runtime 预热。
- 插件按需加载。
- manifest 缓存。
- 公共依赖复用。
- 沙箱池化。
- 大插件懒加载。
- 执行超时熔断。
- 资源占用监控。

## 10. 面试口径

如果问 WebRuntime 难点：

> 难点是运行动态代码时既要给插件足够能力，又不能让插件污染宿主。我的设计会把加载、运行上下文、宿主 API、权限、生命周期和监控拆开。插件只能通过 bridge 调宿主能力，所有调用都走权限和参数校验。

如果问 Sandbox 的核心价值：

> Sandbox 的核心价值是控制动态代码的影响面。它隔离全局变量、资源访问、事件监听和宿主能力，插件异常不会拖垮主应用，卸载时也能完整释放。

## 11. Runtime 的能力分层

一个可扩展 Runtime 可以分成控制面和执行面。

```text
Control Plane
  -> 插件注册
  -> 权限配置
  -> 版本管理
  -> 调度策略
  -> 监控审计

Execution Plane
  -> sandbox
  -> module loader
  -> host api
  -> event bus
  -> resource manager
```

控制面解决“谁能运行、运行哪个版本、有什么权限”；执行面解决“怎么安全运行、怎么通信、怎么释放资源”。

## 12. 插件 Manifest 设计

插件必须有 manifest 描述自己。

```json
{
  "name": "demo-plugin",
  "version": "1.0.0",
  "entry": "index.js",
  "permissions": ["read:file", "call:network"],
  "resources": {
    "memory": "128MB",
    "timeout": 30000
  },
  "apis": {
    "required": ["storage.get", "logger.info"]
  }
}
```

manifest 的价值：

- 运行前就能做权限审核。
- 版本可追踪。
- 能做灰度和回滚。
- 能做资源配额。
- 能避免运行时才发现缺 API。

## 13. 权限模型

建议采用能力权限，而不是给插件完整宿主对象。

```text
Plugin
  -> request capability
  -> runtime permission check
  -> host api execute
  -> audit log
```

权限可以分级：

- 只读能力：读配置、读文档。
- 低风险写能力：写临时缓存。
- 高风险写能力：改文件、发请求、执行命令。
- 危险能力：删除文件、提交代码、发消息。

高风险能力应加：

- 用户确认。
- dry-run。
- 审计日志。
- 路径白名单。
- 回滚方案。

## 14. 资源配额和熔断

Sandbox 不只是安全隔离，也要控制资源。

常见配额：

- 最大执行时间。
- 最大内存。
- 最大输出长度。
- 最大文件读写范围。
- 最大网络请求数。
- 最大并发任务数。

熔断策略：

```text
任务开始
  -> 记录 start time
  -> 超时终止
  -> 捕获 stderr / error
  -> 标记 failed
  -> 清理临时资源
```

如果没有资源配额，插件或 Agent 工具很容易因为死循环、大输出、递归扫描拖垮宿主。

## 15. Module Loader 细节

Loader 负责把插件代码变成可运行模块。

需要处理：

- 入口文件解析。
- 依赖解析。
- 缓存命中。
- 版本冲突。
- source map。
- 热更新。
- 加载失败 fallback。

加载策略：

```text
manifest
  -> resolve entry
  -> check cache
  -> fetch / read bundle
  -> verify hash
  -> create sandbox
  -> execute entry
```

面试可以说：

> Loader 不是简单 require 一个文件，它要处理版本、缓存、完整性校验、依赖和失败降级。

## 16. Sandbox 通信协议

插件和宿主通信最好协议化。

```json
{
  "id": "call_001",
  "type": "invoke",
  "api": "file.read",
  "params": {
    "path": "workspace/a.md"
  }
}
```

返回：

```json
{
  "id": "call_001",
  "ok": true,
  "result": {}
}
```

错误：

```json
{
  "id": "call_001",
  "ok": false,
  "error": {
    "code": "permission_denied",
    "message": "file.read is not allowed"
  }
}
```

协议化好处：

- 便于审计。
- 便于超时处理。
- 便于重试。
- 便于 trace。
- 便于 mock 和测试。

## 17. 故障隔离

插件异常不应该影响主应用。

隔离策略：

- try/catch 捕获同步错误。
- Promise rejection 统一捕获。
- 子进程崩溃自动回收。
- Worker error 上报。
- 插件级别熔断。
- 同一插件连续失败后禁用。

故障分级：

- 插件内部异常：只卸载插件。
- 宿主 API 异常：降级该能力。
- Runtime 异常：重启 runtime。
- 主进程异常：保留 crash dump 和恢复现场。

## 18. 可观测性设计

Runtime 需要记录：

- 插件启动耗时。
- 插件执行耗时。
- API 调用次数。
- API 错误率。
- 沙箱超时次数。
- 内存峰值。
- 输出大小。
- 用户确认次数。

Trace 结构：

```text
task_id
  -> plugin_id
  -> step_id
  -> api_call
  -> input_summary
  -> output_summary
  -> duration
  -> status
```

这对 AI Agent 场景尤其重要，因为 Agent 多步调用时，不记录 trace 就很难定位“到底是哪一步错了”。

## 19. 可延伸技术点

可以准备：

- JS Proxy sandbox 和 iframe sandbox 的区别。
- Worker 和子进程隔离的适用场景。
- 插件权限如何分级。
- 为什么需要 manifest。
- 如何防止插件死循环或大输出。
- Agent 工具执行为什么必须 sandbox。
- trace 如何帮助复盘多步任务。

