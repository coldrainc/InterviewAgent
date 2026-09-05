# Claude Code / Codex CLI 源码学习路线（配套你的 Workflow Agent 面试复习）

> 下载位置：`面试题/interview/学习资料_CodeAgent源码/`
>   - `OpenAI-Codex-官方开源/` — OpenAI 官方开源 Apache-2.0，Rust + TS/Node，真正可构建运行
>   - `Claude-Code-社区源码合集/`
>       - `original-source-code/` + `claude-code-source-code/` — 2026-03-31 从 npm sourcemap 提取的官方 TS 源码（用于架构学习）
>       - `nano-claude-code/` — 社区 Python 5000 行纯净重实现（无版权问题，可直接 debug 学习，强烈推荐从这个读）
>       - `docs/claude-code-deep-dive-xelatex.pdf` — 中文版架构深度分析报告

---

## 一、先读哪个？优先级

你的简历核心是**Workflow Agent（ReAct / 诊断/Sandbox/MCP）+ Harness 治理**。学习目标是"对标业界一线 Agent Runtime 的实现，让面试时讲 Workflow Agent 设计选型/取舍的依据有实打实来源"，不是为了跑它们。

| 阅读顺序 | 读哪个 | 读多少 | 重点学什么 | 对应你面试哪个点 |
|---|---|---|---|---|
| **⭐ 第 1 位** | `nano-claude-code/`（~5000 行 Python） | 全量精读 | ReAct 循环、Fork/Inline 执行、Skill 包、Memory 包、Git Worktree 沙箱 | **讲自研 Workflow Agent 的时候"为什么我这样设计 ReAct"** |
| **⭐ 第 2 位** | `OpenAI-Codex-官方开源/` | 先看 codex-cli/ + codex-rs/ + .codex/skills | 多级沙箱（Seatbelt/bubblewrap）、MCP 接入、Subagent 系统、Skill 系统、Rust 执行服务器设计 | **沙箱安全 / MCP 设计 / Subagent 并行** |
| 第 3 位 | `docs/claude-code-deep-dive-xelatex.pdf` | 先读架构章节 | 7 层 Memory + Dreaming 系统、工具权限模型、Prompt 分层 | **Agent 可观测 / 上下文分层设计** |
| 第 4 位（验证） | `original-source-code/src/`（泄露 TS 版） | 只看目录 + 关键文件 | 对比 Nano Claude Code 看官方实现和纯净重实现的差异 | 面试不要提"我看过泄露源码"——只用 Nano Python 版的观点讲 |

**面试禁忌**：❌ 不要说"我读过 Claude Code 泄露源码"——合规风险，也让面试官担心你对版权不敏感。要说：
> "我研究了 Claude Code 的社区纯净重实现 Nano Claude Code（~5000 行 Python），它把 Fork/Inline 双执行路径、Memory 跨会话、Skill 技能包这几件事做得非常干净，我在设计 Workflow Agent 的 ReAct 引擎时，借鉴了它……"

---

## 二、Nano Claude Code（Python ~5000 行）精读路径（你应该最先读的）

目录结构 & 对应学习点：

```
nano-claude-code/
├── nano_claude_code/
│   ├── agent.py              # 🔴 核心：主 ReAct 循环 + Fork/Inline 执行（和你 ReAct Engine 直接对标）
│   │                         # 必读：run_loop()、fork_subagent()、inline_call_skill()
│   │
│   ├── memory/               # 🟠 跨会话记忆
│   │   ├── memory.py         # 分层 Memory：短期会话 / 长期项目知识 / AI 记忆搜索（向量索引）
│   │   └── extractor.py      # 从对话自动提取知识条目（和你 RAG 入库流水线对应）
│   │
│   ├── skills/               # 🟢 技能系统 = 你简历里的 MCP Skill 扩展
│   │   ├── base.py           # Skill 基类：Schema + 权限 + 执行钩子
│   │   ├── builtin/          # 内置 Skills：bash、file_editor、git_worktree、mcp_client
│   │   └── loader.py         # 动态发现/注册 Skill（和你"动态工具注册"对应）
│   │
│   ├── runtime/              # 🔵 执行沙箱（和你 Sandbox 对应）
│   │   ├── git_worktree.py   # Git Worktree 隔离：一次 Agent Run 一个独立 Worktree（你可以借鉴）
│   │   ├── approval.py       # 工具审批流：三种模式 (auto / ask / never) 和你 HITL 一致
│   │   └── sandbox_check.py  # Seatbelt 能力检测 & 沙箱边界校验
│   │
│   ├── tools/                # 工具层
│   │   ├── bash_tool.py      # Shell 执行（看输入裁剪/脱敏/PII处理）
│   │   ├── file_editor.py    # str_replace + 原子写（和你 SHA-256 原子替换一致思路）
│   │   ├── mcp_client.py     # MCP 客户端：SDK 调用 + 错误重试
│   │   └── git_tool.py       # Git：diff/commit/stash（Agent 自己做版本回溯）
│   │
│   ├── types.py              # 所有关键类型定义（State/Turn/Skill/Memory Schema）
│   ├── prompts.py            # System Prompt（分层：角色 + 工具清单 + Memory Context + Approval Mode）
│   └── cli.py                # CLI 入口：参数解析 + Session 恢复（Checkpoint）
│
└── tests/                    # 单元测试怎么写 Agent（对你 Harness 很有参考）
    ├── test_agent_loop.py
    ├── test_memory_extract.py
    └── test_approval_flow.py
```

### 应该从 Nano Claude Code 带走的 5 个"面试可直接讲"的设计点：

1. **Fork / Inline 双执行路径**
   长任务不是单 ReAct 循环死磕。遇到独立子任务（比如"查一下某个 SDK API"），**Fork 出独立 Subagent**，有自己的 state、memory、权限上下文，跑完毕只把结果传回父 Agent。而同一上下文里简单工具调用走 **Inline**。这样解决了长任务"token 爆炸 + 上下文混在一起"的问题。
   > 面试对应：我在设计 Workflow Agent 时，借鉴了业界主流 Agent 把复杂任务拆成 Fork/Inline 两种路径，独立子任务 fork 独立 agent，同上下文轻量工具调 inline。

2. **Git Worktree 作为一次 Agent Run 的轻量沙箱**
   不是每次跑 Agent 都起 Docker（太重），而是 `git worktree add` 开一个独立工作目录，Agent 所有文件操作都在里面。成功再合并回原分支，失败直接删除 worktree，回滚零成本。这是对 Docker Sandbox 在代码编辑场景的**轻量化补充**。
   > 面试对应：我们的 Sandbox 机制，对 SHA-256 配置同步这类敏感操作一定 Docker 一线隔离；代码编辑/运行任务则用 git worktree + 权限受限用户做第二层轻量隔离，两者结合既安全又成本可控。

3. **三层 Memory（会话短期 / 项目长期 / AI 可检索）**
   不是只有一个 RAG，而是：会话内的消息栈 = 短期记忆；跨会话存到项目知识条目 = 长期记忆（手动或自动 extractor 提取）；AI 要搜索历史用向量检索搜长期记忆。这和你「RAG 知识库 + Agent 上下文建设」两条简历线完美对应。
   > 面试对应：我做直播端 Agent 上下文建设时，按照业界的分层 Memory 思路拆成三层：会话级 state 不落库、项目级业务知识存知识库自动抽取、跨会话事实用向量检索。和单层 RAG 相比幻觉率降了很多。

4. **Approval 三种模式（和你 HITL 对应）**
   工具调用之前审批：`auto/ask/never`。对 `rm -rf /`、`ssh prod`、`drop table` 这类永远 ask；对 `ls`、`pwd`、`read file` 这类只读类永远 auto；中间类（写文件、跑测试）默认 ask，但可配置项目级白名单。
   > 面试对应：我们在 Workflow Agent 做了工具分级治理，高风险工具强制人工审批，只读工具自动执行，写操作通过 SKILL 白名单配置，这和业界 Codex/Claude Code 的 approval 模式一致。

5. **Prompt 分层（角色 + 可用工具 + 权限模式 + 当前 Memory + 审批规则）**
   每次调用 LLM 前，system prompt 是拼装出来的：角色系统提示（不变）+ 当前可用 Skill 清单和 Schema（动态）+ 当前 Approval 模式（动态）+ 相关长期记忆（动态）。这避免了"把 1000 行 Prompt 写死在一个字符串里"的维护噩梦。
   > 面试对应：我们的 Agent system prompt 不是硬编码，而是按"角色层 + 工具层 + 约束层 + 上下文层"动态拼装，MCP 注册新工具后自动出现在工具层，不用改 Prompt。

---

## 三、OpenAI Codex 官方开源（Rust + TS）精读路径

Codex 比 Claude Code 多一个杀手锏：**纯 Rust 执行服务器 codex-rs**，性能、内存、沙箱边界都是生产级。读它是为了回答面试官问「你说的 Runtime 如果要高并发高吞吐怎么做？」。

```
OpenAI-Codex-官方开源/
├── codex-cli/              # TypeScript 端：CLI/TUI、命令解析、配置、前端渲染
│   ├── src/
│   │   ├── cli.ts          # 命令入口：login/logout/model/oss/subagent/exec
│   │   ├── approval.ts     # 🔴 审批模型 + 工具分级矩阵（和 Nano Claude Code 对照读）
│   │   ├── memory.ts       # 🔴 Codex 跨会话 Memory（Docs/Sticky Notes/Project Indexes）
│   │   ├── mcp.ts          # 🟢 MCP Client 配置与动态注册（直接参考）
│   │   ├── subagent.ts     # 🟠 Subagent 并行调度（Task 图编排）
│   │   └── policy.ts       # Codex Rules/Policy 规则引擎（配置文件）
│   │
│   └── .codex/skills/      # 🔵 内置 Skills（和你 Workflow Agent 工具对应）
│       ├── code-review/    # 代码审查 Skill
│       ├── web-search/     # 搜索 Skill
│       ├── git/            # Git 操作 Skill（patch/rebase）
│       └── docs/           # 项目知识 Skill（和你 RAG 知识库直接对）
│
├── codex-rs/               # ⭐ Rust 端：执行服务器（codex-exec-server）、沙箱
│   ├── src/
│   │   ├── exec_server.rs  # 🔴 gRPC/HTTP 执行服务：命令/文件/网络调用的统一入口
│   │   ├── sandbox/        # 🔴🔴 重点！三级沙箱：
│   │   │   ├── seatbelt.rs # macOS Sandbox Seatbelt（系统调用级白名单）
│   │   │   ├── bubblewrap.rs # Linux BubbleWrap（Mount Namespace + PID 隔离）
│   │   │   └── win_sandbox.rs # Windows AppContainer
│   │   ├── tools/          # Rust 工具实现（bash/file/git）
│   │   ├── model.rs        # Responses API 客户端（OpenAI 新标准 API）
│   │   ├── memory.rs       # 🔴 Sticky Notes 持久化（SQLite 本地存）
│   │   └── error.rs        # 错误码/错误归因分类（和你诊断分类器对应）
│   │
│   └── Cargo.toml          # 依赖清单：看用了哪些 crate（tonic gRPC、tokio、bubblewrap、sqlite）
│
├── sdk/                    # SDK：供三方系统接入 Codex（你 Workflow Agent API 对标）
│   └── typescript/         # TS SDK：Prompt/Codex Rules/Subagent 调用
│
└── bazel/                  # Bazel 构建（Monorepo 构建体系，作为工程化参考）
```

### 从 Codex 官方开源带走的 4 个大题目回答点：

1. **「怎么把 Agent 做成高并发、低内存？」——直接答：Codex 的 Rust 执行服务器思路**
> 我们现在 Workflow Agent 的 Runtime 用 Python/FastAPI，对于 100 run/小时量级足够。如果后续要 10 倍以上吞吐，我会参考 Codex 的做法拆两层：TypeScript 管 CLI/配置/前端/业务逻辑，Rust 单独做执行服务器（codex-rs），只做最耗 CPU 和 I/O 的事：bash 执行、文件 IO、沙箱边界、网络调用。两边通过 gRPC 通信——Codex 这么做内存占用比纯 Node 实现低了 70%+，单机能扛几千并发的工具调。

2. **「沙箱怎么落地到 Linux/macOS/Windows 三平台？」——Codex 三级沙箱矩阵**
> 平台不同，沙箱技术栈不一样：Codex 用 macOS **Seatbelt（sandbox_init，系统调用级白名单）**、Linux **BubbleWrap（Mount/PID/Network Namespace，比 Docker 轻）**、Windows **AppContainer**。这三件事分别对应平台原生能力而不是硬上 Docker（Docker 在桌面端用户体验很差）。对我们 Workflow Agent 的 Sandbox 来说，Docker 是服务器端主方案，但如果以后要开放给工程师本地跑，就应该参考这个三级矩阵。

3. **「Skill/MCP 配置怎么组织？」——.codex/skills 目录 + 声明式 YAML**
> Codex 把 Skill 作为一等公民：每个 Skill 在 `.codex/skills/<name>/` 目录里放 skill.yaml（声明输入输出 schema、权限等级、触发命令）+ script 实现。这个比我们现在"在代码里注册 Skill"更维护友好——运营/产品同学也能改 YAML 加 Skill，不需要改代码。这个我计划下一步加到我们 MCP 扩展体系里。

4. **「Codex vs Claude Code 选型结论（面试直接讲）」**
> 如果我从零选一个 Agent Runtime 做自研基座：
> - **团队 TS/Rust 多、做纯码 Agent** → 站在 Codex 官方开源的肩膀上二开，Rust 执行服复用、CLI/TUI 直接用。
> - **团队 Python 多、做业务工作流（诊断/RAG/看板）** → 参考 Nano Claude Code 的结构，Python 实现的 ReAct Loop + Fork/Inline + Skill + Memory 成本最低，1-2 周就能跑通 MVP。
> - 两者的工具分级、三层 Memory、Approval 审批模型是共通的，都值得吸收。

---

## 四、Claude Code 泄露版 TS 源码（对照用，别对外说你读过）

只做**结构对照**，不深入复制代码。看下面这几个目录，和 Nano Claude Code / Codex 对照验证：

```
original-source-code/src/
├── commands/            # 命令实现（bash、edit、search、diff、apply_patch……）
├── prompts/             # 官方 Prompt 分层（看系统提示分层方式）
├── mcp-server/          # MCP Server 实现（Codex 是 MCP Client，这里是 Server 端，对）
├── tool-system/         # 工具调用 Schema + 权限矩阵
├── memory/              # 官方 Memory（7 层 Memory 架构 + Dreaming 后台刷新）
└── service/             # Bridge 桥接：CLI ↔ LLM ↔ Tool 的三层 Service
```

> 用法：你把 docs 里的中文分析报告 `claude-code-deep-dive-xelatex.pdf` 翻一遍，里面有 7 层 Memory + Dreaming 系统的架构图，直接学理论就行。Dreaming 系统就是"Agent 下班之后，后台异步把今天的对话抽取、打标签、合并记忆"，对你"直播知识库入库流水线"自动化这个点很有启发。

---

## 五、和你 Harness 方案的对应复习法

把源码学习和面试两个核心点打通：

### 5.1 回答「Workflow Agent 为什么这么设计？（行业对标）」
- ReAct 循环设计 → 对照 Nano Claude Code `agent.py:run_loop()`
- Fork/Inline 拆分任务 → Nano Claude Code
- 审批分级 → Codex `approval.ts` + Nano `approval.py`（交叉验证行业共识）
- Skill/MCP 体系 → 三面互证：你设计的 MCP、Claude Code 的 skills/、Codex 的 `.codex/skills/`
- Memory 分层 → 三面互证：你 RAG 三层、Nano 三层、Codex Memory+Docs+Sticky
- 沙箱分层 → 你 Docker + SHA256 ↔ Nano Git Worktree ↔ Codex 三级原生沙箱矩阵
- Prompt 分层拼装 → Nano `prompts.py` + 泄露版 `prompts/`（行业默认做法）

> 面试话术："我在设计 Workflow Agent 的时候，系统对标过 Claude Code 和 Codex CLI 两个业界一线 Agent 的架构，在 ReAct 循环、分层 Memory、工具分级审批、沙箱隔离、Skill/MCP 这几个点上，我们的实现和业界主流方案是对齐的，但根据抖音直播研发场景做了两点定制：一是把诊断能力 span 账本直接内置在 Runtime 里（通用 Agent 通常没有这个）；二是 RAG 知识库作为 Evidence Bank 注入，不仅给用户做问答，也做 Harness Judge 的事实依据。"

### 5.2 回答「Harness 治理怎么设计？（行业对标）」
- Scenario/Run/Baseline 三层 → Codex `tests/` + `policy.ts`（Codex 自己有 Policy Rules 引擎和场景规则）
- Tool Accuracy / 3D Score → Codex Subagent 调度成功率 + Skill 重试率
- LLM-Judge → Codex 的 code-review Skill 本身就是 LLM 评审
- Analyzer 失败模式分类 → Codex `codex-rs/src/error.rs` 错误码 + 分类器（和你 failure_mode.py 一致）
- 止血开关 GATE_ENABLED → Codex 有 "Zero Data Retention" 组织级关闭，也是全局开关

> 面试话术："我们的 Harness 本质上就是把通用 Agent 平台里的"Policy Rules + Skill 测试 + 错误归因"这三块单独抽取出来，做成面向研发团队的治理产品。和 Codex Policy Rules 的差异是：它做的是单个 Agent 每次执行的规则，我们做的是整个研发流程的版本化治理——Scenario 有版本、Baseline 有历史、门禁有回滚、有审计、有 P0 止血开关。"

---

## 六、每天 1 小时的 7 天学习计划

| 天 | 内容 | 产出（写进自己的复习笔记） |
|---|---|---|
| Day 1 | 读 Nano `types.py` + `prompts.py` + `cli.py`（入口） | 画出 Nano Claude Code 的整体架构图（模块+数据流向） |
| Day 2 | 精读 `agent.py run_loop()`（核心） | 把 ReAct 循环伪代码写下来：什么时候 Inline 什么时候 Fork，Fork 传什么回来 |
| Day 3 | 读 `skills/base.py` + `skills/builtin/mcp_client.py` + `runtime/approval.py` | 对照你简历 MCP Skill，整理「业界 Agent 工具系统 5 要素」清单（Schema/注册/权限/审批/错误处理） |
| Day 4 | 读 `memory/` 整目录 + `runtime/git_worktree.py` | 对照你简历「三层 Memory + 沙箱隔离」，画出自己的设计 vs 业界设计对比表 |
| Day 5 | Codex 官方开源：`codex-cli/approval.ts` + `codex-cli/memory.ts` + `codex-cli/mcp.ts` | 对照 Day3 Day4：找 Codex vs Nano 相同和不同点，总结"为什么两家都选一样的审批/记忆模型" |
| Day 6 | Codex `codex-rs/src/sandbox/` 全目录（Rust 只看结构+注释）+ 中文 PDF 架构报告 | 整理「Agent 沙箱 3 平台选型矩阵」（Linux/macOS/Windows 分别用什么） |
| Day 7 | 回到你简历：用学到的这 6 天内容，重写一遍 Workflow Agent 的介绍话术 | 产出"自己项目架构 vs 业界一线"的对比 + 为什么这么选型 + 哪些地方计划下一步改进 |

---

## 七、合规提醒（面试重要）

| ✅ 可以在面试中说 | ❌ 不要在面试中说 |
|---|---|
| "我参考了 Nano Claude Code 这个社区 Python 纯净重实现（~5k 行），它的 Fork/Inline 双执行……" | "我下载了 Claude Code 泄露的源码学习……"（版权/合规红线） |
| "我分析过 OpenAI Codex 官方开源的 Apache-2.0 仓库，它的 codex-rs Rust 执行服务器 + BubbleWrap 沙箱……" | "我跑了破解版的 Claude Code……"（任何破解/泄露不要提） |
| "我对比过业界两款头部 Agent（Codex 和 Claude Code）在 Memory 分层、工具审批、Skill 体系上的对齐点……" | 具体引用源码路径、行号、私有变量名（避免暴露看过泄露版） |
