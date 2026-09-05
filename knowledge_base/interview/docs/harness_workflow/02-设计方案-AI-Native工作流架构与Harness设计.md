# AI-Native 全栈工作流优化技术方案 & Harness 设计

> 版本：v1.0 | 2026-08-27
> 背景：基于抖音直播 Workflow Agent + RAG 知识库的现状，参考业界 2026 前沿实践，输出可落地的工作流优化方案与评测 Harness 设计。

---

## 一、业界前沿参考（2025-2026）

**先对齐「Harness 是什么」**：模型是引擎，**Harness 是围绕它的车**——循环、工具、内存、控制流、沙箱、错误处理、评测采集一体化的运行时脚手架。没有 Harness 的 AI 功能 = 没有单测的后端服务。[^awesome-harness]

### 1.1 代表性 Harness / 评测基础设施

| 项目 | 核心创新 | 可借鉴点 |
|---|---|---|
| **AgentCompass** (上海AI Lab, 2026)[^agentcompass] | **Benchmark × Harness × Environment 三层解耦**；异步并行 runtime；pluggable analyzer 自动诊断 failure mode（输出截断、延迟尖刺、重复循环） | 我们 Runtime/Web/Sandbox 三层架构可以往 Benchmark/Harness/Env 解耦方向标准化，诊断 Analyzer 可以直接复用我们的 traceId/spanId 能力 |
| **TRACE** (KAIST, ICML 2026)[^trace] | **无参考轨迹评测**：用 Evidence Bank 累积前序步骤知识，从过程合理性（而非最终答案匹配）评价 trajectory 三维度：有效性、效率、适应性 | 我们的全链路诊断可以引入 Evidence Bank 做过程归因，不再只看"任务成没成"，还看"路径好不好、工具顺序对不对" |
| **SWE-bench-Live** (Microsoft, 2025)[^swebench-live] | **持续更新的活基准**：自动从 GitHub Issue 构造实例 + 自动配置 Docker 环境（每个实例一个镜像），解决 benchmark 过时、数据污染问题 | 可以用同样思路：自动从真实工单/故障/CR 评论抽取任务，构造"活"评测集，避免评测集和业务脱节 |
| **AgentEvals** (LangChain, 2026)[^agentevals] | **Trajectory LLM-as-Judge**：给 OpenAI 格式消息序列打分，支持 trajectory match（子序列匹配）、tool correctness（工具名+参数）、efficiency（步数） | 我们的 span 格式可以直接喂给 LLM Judge 做 trajectory 评分，和传统 pass/fail 形成互补 |
| **Awesome Agent Harnesses** 分类[^awesome-harness] | 明确四类 Harness：Eval（输出质量）、Agent（轨迹）、RL（策略/reward）、Test（Prompt 回归）；识别出 5 个核心组件：scenario registry、metric stack、trace capture、regression gate、gold dataset refresh | 分类学可以直接复用，指导我们建设分层门禁 |
| **Agent 评测框架调研报告 (2026)**[^agent-eval-cn] | 四个核心维度：任务完成度、过程合理性、效率成本、安全合规；三大梯队分类法 + 技术架构共性分析 | 维度定义直接对齐我们已有能力 |

### 1.2 从前沿提炼出的 5 条关键共识

1. **Trajectory 比 Final Answer 更重要**：Agent 多步任务靠最终答案判断是不够的，必须评价过程——工具顺序、参数正确、依赖满足、效率、适应性。这是 2026 年的主流转变。[^trace][^traject-bench]
2. **Harness 必须解耦**：Benchmark（任务集）× Harness（运行时 + 评测）× Environment（沙箱/执行环境）三层独立，避免改动一个点全链路重写。[^agentcompass]
3. **LIVE > STATIC**：SWE-bench-Live 证明"持续自动构造"的评测集，能有效防止数据污染和过时。[^swebench-live]
4. **四类 Harness 都要有，CI 门禁分层**：Test → Eval → Agent → RL，每层独立阈值。PR 只跑轻量 Test Harness，Nightly 跑 Agent + Eval，RL 可选周级。
5. **Trajectory 采集层必须标准化**：OpenTelemetry 作为 trace 标准是社区共识，所有工具调用、推理、沙箱状态变更都要 OTel 格式输出，这是后续一切分析的地基。[^awesome-harness]

---

## 二、问题诊断（基于当前状态）

### 2.1 当前 Workflow Agent 已具备的能力

| 层 | 已有能力 | 对应前沿 |
|---|---|---|
| Trace 捕获 | ✅ traceId/spanId/agentRunId 三级串联 + Runtime Trace + Workflow 阶段账本 | ✅ 刚好命中 Harness 五核心组件的 trace capture |
| 诊断能力 | ✅ span 级异常归因 + 修复建议 | ↔️ 可以升级为 AgentCompass 式 pluggable analyzer |
| 知识库 RAG | ✅ 双路召回 + Query Rewrite + MCP Skill | ↔️ 可以作为 evidence bank 注入 trajectory 评测 |
| 三层架构 | ✅ Web/Runtime/Sandbox | ↔️ 可以标准化为 Benchmark×Harness×Environment 解耦 |

### 2.2 缺失的关键环节（GAP）

| 环节 | 当前状态 | 风险 |
|---|---|---|
| **Scenario Registry**（场景用例库） | 无版本化、无标注 | Prompt 改了不知道有没有回归 |
| **Metric Stack**（指标体系） | 只有 pass/fail，缺过程性指标（tool accuracy、step efficiency、cost、latency） | 优化看不见效果，退化发现不了 |
| **Regression Gate**（CI 门禁） | 没有 AI 功能的自动化回归门 | 线上出了才知道坏了 |
| **Golden Dataset Refresh**（金数据集更新） | 手工或没有 | 评测集和业务错配 |
| **Trajectory Eval**（过程性评测） | 只诊断，不打分 | 无法量化"这次优化好不好" |

---

## 三、完整技术方案

### 3.1 总体架构图

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          用户交互层（Web / IDE Plugin）                        │
├──────────────────────────────────────────────────────────────────────────────┤
│  编排层：Workflow DSL + ReAct Engine（LangGraph 标准化）                       │
│     任务拆解 · 工具调度 · 会话恢复 · Turn 回放 · 取消                         │
├──────────────────────────────────────────────────────────────────────────────┤
│  Harness 层（本次核心建设）                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  ① Scenario Registry  ② Trajectory Capture(OTel)  ③ Metric Stack   │    │
│  │     版本化任务集          全链路采集 · 统一格式       20+ 指标体系     │    │
│  ├──────────────────────────────────────────────────────────────────────┤    │
│  │  ④ Agent Harness(轨迹评)  ⑤ Eval Harness(输出评)  ⑥ Test Harness(PR) │    │
│  │     LLM-Judge+Evidence    LLM-Judge+Faithfulness   Promptfoo/pytest  │    │
│  ├──────────────────────────────────────────────────────────────────────┤    │
│  │  ⑦ Pluggable Analyzers   ⑧ Regression Gate   ⑨ Golden Dataset Pipe  │    │
│  │     故障模式自动诊断        阈值卡 CI             工单→用例自动生产   │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────────────────────────────┤
│  工具 / 知识层：MCP Skill 扩展 · RAG 双路召回（Evidence Bank）                │
├──────────────────────────────────────────────────────────────────────────────┤
│  执行层：Sandbox Runtime · SHA-256 配置同步 · 原子替换/回滚                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 建设路线（三阶段）

#### Phase 1 · 轻量可落地（2-4 周）：Trace 标准化 + Test Harness + 回归基线

**目标**：任何 Prompt / Workflow 改动进主干前，能自动跑出指标，发现 >2% 的回归。

| 组件 | 方案 | 复用你现有能力 |
|---|---|---|
| Trace 采集标准化 | 统一输出 OTel 兼容的 span JSON schema（traceId/spanId/parentSpanId/input/output/meta），每个工具调用、推理、sandbox 变更都吐 span | 复用现有三级 ID 和阶段账本，改格式即可 |
| Scenario Registry v1 | 建 `scenarios/` 目录，按业务域拆分 yml，字段见下 3.3 | 基于真实故障/工单手工先建 20 条 |
| Test Harness | Promptfoo + pytest，跑 scenario registry 的 smoke case | 低成本，PR 合并门禁用 |
| Baseline 机制 | 每个 scenario 存 `baseline.json`（acc、tool accuracy、avg steps），CI 比较 delta 超阈值失败 | 直接用你现有统计代码 |

#### Phase 2 · 过程性评测 + 诊断增强（4-6 周）：Agent Harness + Analyzers

**目标**：不仅看结果，还评价"过程好不好"；自动诊断失败原因。

| 组件 | 方案 | 复用你现有能力 |
|---|---|---|
| Agent Harness | 引入 TRACE 式 Evidence Bank（基于你 RAG 知识库），给 trajectory 三维度打分（有效性/效率/适应性），走 LLM-Judge | Evidence Bank = 知识库检索结果，直接注入 |
| Trajectory Match | AgentEvals 式：工具名 + 参数的子序列匹配打分 | span 的 tool_call 字段直接用 |
| Pluggable Analyzers | 写一套 analyzer：重复循环检测、输出截断、延迟尖刺、工具参数盲选、非法 tool 调用 | 复用你全链路诊断的归因逻辑，输出从"人工看"升级成"结构化 failure mode 标签" |
| 成本/延迟指标 | 在 span 上累加 token_count、elapsed_ms、$cost | 已有数据，补齐字段即可 |

#### Phase 3 · 持续进化（6-8 周）：Live Benchmark + 分层门禁

**目标**：评测集自动增长，门禁分 PR/nightly/周级三层，RL harness 可选。

| 组件 | 方案 | 借鉴来源 |
|---|---|---|
| Golden Dataset Pipeline | 类似 SWE-bench-Live：从已关闭工单 + PR description + CR comment + 排障记录自动抽取"任务→步骤→正确结果"三元组，经 LLM 生成 candidate，人工抽检后入库 | SWE-bench-Live 的 automated curation pipeline |
| 分层门禁 | **PR 门禁**：Test Harness，1min 跑完；**Nightly**：Eval + Agent Harness，60min；**周级**：全量 scenario + RL harness（可选） | 业界四类 harness 分层标准[^awesome-harness] |
| RL Harness（可选） | 用 trajectory reward（步骤奖励 + 最终结果奖励）做 GRPO / 奖励模型微调 | TRL、AgentCompass 内置支持 |

### 3.3 核心数据结构

#### 3.3.1 Scenario Registry（场景用例）

```yaml
# scenarios/diagnose-workflow-failure-v1.yml
id: diag-sandbox-toml-damage
version: "1.2"
tags: [diagnose, sandbox, configuration]
created_at: "2026-08-20"
source: "incident-2026-08-17-01"  # 来源于真实工单/故障
difficulty: medium

input:
  user_prompt: "这个研发任务工具调用步骤失败了，帮我排查根因并给修复建议。附带 traceId=tr_abc123。"
  context:
    workflow_name: "code_fix_and_test"
    attached_trace: "fixtures/traces/tr_abc123.json"

# 可验证断言，越可机器判断越好
assertions:
  # 确定性断言
  - type: tool_called
    tool_name: "get_trace_detail"
    args_match: {"trace_id": "tr_abc123"}
  - type: tool_called
    tool_name: "sandbox_check_config_integrity"

  # 阈值断言
  - type: max_steps
    value: 8

  # LLM-Judge 断言
  - type: llm_judge
    criteria: "answer must identify TOML corruption caused by residual config, and recommend rollback + SHA-256 check fix"
    model: "gpt-4o-mini"  # 小模型做 judge 够用

# 金 trajectory（可选，用于 trajectory match）
golden_trajectory_hints:
  must_include_tool_sequence:
    - get_trace_detail
    - sandbox_check_config_integrity
  should_contain_in_final_answer:
    - "配置残留"
    - "SHA-256"
    - "原子替换"
```

#### 3.3.2 Trajectory JSON Schema（OTel 兼容）

```jsonc
// traces/tr_abc123.json
{
  "trace_id": "tr_abc123",
  "agent_run_id": "ar_789",
  "started_at": "2026-08-20T10:00:00Z",
  "ended_at": "2026-08-20T10:03:42Z",
  "total_token_count": 48219,
  "total_cost_usd": 0.146,
  "spans": [
    {
      "span_id": "sp_001",
      "parent_span_id": null,
      "type": "llm_reasoning",  // llm_reasoning | tool_call | sandbox_state_change | user_turn
      "name": "react_reasoning_step_1",
      "started_at": "...",
      "duration_ms": 1842,
      "token_count": 4210,
      "cost_usd": 0.013,
      "input": {"messages": ["..."]},
      "output": {"thought": "...", "tool_plan": {"name": "get_trace_detail", "args": {...}}},
      "status": "ok"  // ok | error | timeout | truncated
    },
    {
      "span_id": "sp_002",
      "parent_span_id": "sp_001",
      "type": "tool_call",
      "name": "get_trace_detail",
      "args": {"trace_id": "tr_abc123"},
      "output_snippet": "...",  // 结果摘要，原文存外部存储
      "status": "ok"
    }
    // ... 后续 span
  ],
  "evidence_bank_refs": [
    // 检索引用的知识条目（来自知识库 RAG）
    {"doc_id": "kb-sandbox-config-sync-v3", "chunk_index": 7, "relevance_score": 0.92}
  ]
}
```

### 3.4 指标体系（Metric Stack）

参考 AgentCompass 与分类学调研报告[^agentcompass][^agent-eval-cn]，分为四大类：

#### 第一类 · 任务完成度（Result Metrics）

| 指标 | 定义 | 门禁阈值示例 |
|---|---|---|
| task_success_rate | scenario 级断言全部通过的比例 | ≥ baseline − 2% |
| answer_faithfulness | 回答是否可被 evidence bank 支撑（Ragas faithfulness） | ≥ 0.88 |
| test_passed_after_action | 代码修复场景下，修复后测试通过率 | SWE-bench 同款 |

#### 第二类 · 过程合理性（Trajectory Metrics）

| 指标 | 定义 | 来源 |
|---|---|---|
| tool_selection_acc | 工具名 + 参数的正确率（vs golden / LLM-Judge） | TRAJECT-Bench[^traject-bench] |
| tool_order_satisfaction | 工具依赖/顺序是否满足 | TRAJECT-Bench |
| trajectory_3d_score | 有效性/效率/适应性 三维度打分，0~1 | TRACE[^trace] |
| tool_repetition_rate | 相同工具无意义重复调用占比 | AgentCompass Analyzer |

#### 第三类 · 效率与成本（Efficiency Metrics）

| 指标 | 定义 |
|---|---|
| avg_steps_to_success | 成功完成的 scenario 平均步数 |
| avg_latency_p50 / p95 | 端到端耗时 |
| avg_token_count_per_success | 成功任务 token 消耗 |
| cost_per_success_usd | 每次成功任务 $ 成本 |

#### 第四类 · 安全与合规（Safety Metrics）

| 指标 | 定义 |
|---|---|
| forbidden_tool_call_rate | 调用黑名单工具/超出权限的比例 |
| pii_leak_rate | 输出中出现凭证/手机号等敏感信息 |
| hallucination_rate | 在 RAG 覆盖问题上，回答无法被知识库证据支持的比例 |

> **经验法则**：一次改动只要 4 个核心指标（task_success_rate ↓、tool_selection_acc ↓、cost ↑、latency_p95 ↑）任意超过阈值 2 倍标准差，直接阻断 PR。

### 3.5 CI 分层门禁（Regression Gate）

参考业界四类 harness 分层[^awesome-harness]：

```
                              ┌─────────────────────────┐
                              │      Weekly / Release    │
                              │  ┌───────────────────┐  │
                              │  │  RL Harness (可选) │  │
                              │  └───────────────────┘  │
                              │  ┌───────────────────┐  │
                              │  │ Full Eval + Agent │  │
                              │  └───────────────────┘  │
                              └────────────┬────────────┘
                                           │
                              ┌────────────▼────────────┐
                              │        Nightly Build     │
                              │  ┌───────────────────┐  │
                              │  │  Eval Harness     │  │
                              │  │  (全量 scenario,   │  │
                              │  │   LLM-Judge, ~30m)│  │
                              │  └───────────────────┘  │
                              │  ┌───────────────────┐  │
                              │  │  Agent Harness    │  │
                              │  │  (轨迹三维度评分,  │  │
                              │  │   Analyzer 诊断,   │  │
                              │  │   ~30min)         │  │
                              │  └───────────────────┘  │
                              └────────────┬────────────┘
                                           │
                     低于阈值阻断 / 发告警（不阻断主干）
                                           │
                              ┌────────────▼────────────┐
                              │         PR / Merge       │
                              │  ┌───────────────────┐  │
                              │  │  Test Harness     │  │
                              │  │  (20 条 smoke,    │  │
                              │  │   Promptfoo + pytest,│ │
                              │  │   < 3min)         │  │
                              │  └───────────────────┘  │
                              └─────────────────────────┘
```

**门禁决策逻辑**（run_gate.py 伪代码）：

```python
# 阈值配置（可按 harness 层级不同）
GATES = {
    "test": {
        "task_success_rate": {"baseline_delta": -0.02},      # 比基线下降>2% → fail
        "tool_selection_acc": {"absolute": 0.90},             # 绝对低于90% → fail
    },
    "agent": {
        "trajectory_3d_score": {"baseline_delta": -0.03},
        "cost_per_success_usd": {"baseline_delta_ratio": 0.15},  # 成本涨15% → fail
    },
}

def decide(metrics: dict, baseline: dict, gate_level: str) -> Pass | Fail:
    for metric_name, rules in GATES[gate_level].items():
        if "baseline_delta" in rules:
            delta = metrics[metric_name] - baseline[metric_name]
            if delta < rules["baseline_delta"]:
                return Fail(f"{metric_name} delta={delta:.3f} exceeds threshold")
        if "absolute" in rules:
            if metrics[metric_name] < rules["absolute"]:
                return Fail(f"{metric_name}={metrics[metric_name]:.3f} below floor")
    return Pass()
```

---

## 四、Harness 实现（代码骨架）

参考 LangGraph + AgentEvals + AgentCompass 设计。完整代码放在 `demos/workflow-harness/`（见下一个文件）。

### 4.1 模块划分

```
demos/workflow-harness/
├── pyproject.toml              # 依赖：langgraph, openai, promptfoo, opentelemetry-api
├── harness/
│   ├── __init__.py
│   ├── schema.py               # Scenario / Trajectory / Span Pydantic 模型
│   ├── runner.py               # ScenarioRunner：跑 scenario，采 trajectory
│   ├── evaluators/
│   │   ├── deterministic.py    # 确定性断言（tool_called、max_steps）
│   │   ├── trajectory.py       # Trajectory match + 3D score + Tool accuracy
│   │   ├── llm_judge.py        # LLM-as-judge 包装（temperature=0、seed 固定）
│   │   └── metrics.py          # 指标计算（四大类 20+ 指标）
│   ├── analyzers/
│   │   ├── repetition.py       # 重复循环检测
│   │   ├── latency.py          # 延迟尖刺
│   │   └── failure_mode.py     # 失败模式分类
│   └── gate.py                 # 回归门（baseline 对比 + 决策）
├── scenarios/
│   ├── diag-sandbox-toml-damage.yml
│   └── rag-business-qa.yml
├── baselines/
│   └── v1.2.json               # 各 scenario baseline 指标
├── run_pr_harness.py           # PR 门禁入口：跑 scenario → 指标 → gate
└── run_nightly_harness.py      # Nightly 入口：全量 + Agent Harness + Analyzer 报告
```

### 4.2 最小可运行片段（Runner 核心）

```python
# harness/runner.py
from .schema import Scenario, Trajectory, Span, SpanType
from opentelemetry import trace

class ScenarioRunner:
    """跑一个 scenario，产出 trajectory + 指标快照。
    真正的 Agent 执行器可替换：LangGraph / 自研 Runtime 都可以。"""

    def __init__(self, agent_executor, otel_tracer=None):
        self.agent = agent_executor
        self.tracer = otel_tracer or trace.get_tracer("workflow-harness")

    def run(self, scenario: Scenario) -> tuple[Trajectory, dict]:
        started = time.time()
        spans: list[Span] = []
        total_tokens = 0
        total_cost = 0.0

        # 注入 scenario 上下文 + seed 固定（减少 flakiness）
        ctx = scenario.build_execution_context(seed=scenario.id)

        for turn in self.agent.run_stream(
            user_prompt=scenario.input.user_prompt,
            context=ctx,
            tools_whitelist=scenario.tools_whitelist,
        ):
            # turn 可能是 reasoning / tool_call / tool_result / final_answer
            span = Span.from_turn(turn, parent_span=spans[-1] if spans else None)
            spans.append(span)
            total_tokens += turn.get("token_count", 0)
            total_cost += turn.get("cost_usd", 0.0)

        traj = Trajectory(
            trace_id=f"tr_{scenario.id}",
            agent_run_id=f"ar_{uuid.uuid4().hex[:6]}",
            started_at=started,
            ended_at=time.time(),
            total_token_count=total_tokens,
            total_cost_usd=total_cost,
            spans=spans,
            evidence_bank_refs=turn.get("evidence_refs", []),
        )

        metrics = compute_all_metrics(traj, scenario)
        return traj, metrics
```

### 4.3 典型使用（PR 门禁脚本）

```bash
# PR 提交时执行
python run_pr_harness.py \
  --scenarios scenarios/*.yml \
  --baseline baselines/v1.2.json \
  --gate test \
  --report output/pr-report.json

# Nightly
python run_nightly_harness.py \
  --gate agent \
  --report output/nightly-report.html \
  --notify-slack channel-ai-platform
```

---

## 五、工作流优化（围绕 Harness 的研发流程升级）

### 5.1 Workflow Agent 开发的新流程（AI-Native）

```
旧流程：写 Prompt / 调工具 → 手工点几下测 → 上线 → 出了才知道坏了
新流程：
  1. 写 Scenario（新增/改动用例先入库）
  2. 本地跑 Test Harness，看指标
  3. 提 PR → CI 自动跑 Test Harness → 指标卡 + 回归对比
  4. Merge → Nightly 跑 Agent + Eval → 第二天早上收报告（含 Analyzer 自动诊断的失败模式）
  5. 线上失败 → 自动进 Golden Dataset Pipeline → 下一个 release scenario 已包含
```

### 5.2 指标看板（Harness 报告示例）

每次 Harness 跑完输出 4 份视图：
1. **对比视图**：本次指标 vs baseline，红/绿标注（类 Lighthouse 报告）
2. **Trajectory 火焰图**：span 级耗时+token，一眼看出哪个工具慢/耗 token（复用 OTel UI）
3. **失败模式雷达图**：Analyzer 自动分类的 10+ failure mode 数量分布（类 AgentCompass[^agentcompass] 图 1 能力画像）
4. **Scenario 矩阵**：每个 scenario 的通过情况 + 最劣 Top 5

---

## 六、可预期收益

| 收益 | 量化参考（行业均值） | 对应你场景 |
|---|---|---|
| 回归发现率 | 80%+ AI 退化能在 CI 发现，不是线上 | 你现在缺这块，预计第一阶段就能发现 30%+ 的 Prompt/工具改坏 |
| 排障效率 | Trajectory 标准化 + Analyzer 自动诊断，排障时间减少 50% | 和你负责的全链路诊断正相关，大幅缩短 MTTR |
| 迭代效率 | 每轮优化能看指标，不靠感觉，迭代速度 2x+ | Prompt/RAG/ReAct 策略迭代加速 |
| 成本控制 | Token/$ 指标门禁，可避免成本失控 | Agent 越用越多时，没有成本门禁会出问题 |

---

## 七、踩坑 & 注意事项

1. **Flakiness（结果不稳定）是第一敌人**：LLM 的随机性必须控制——judge 用 `temperature=0 + fixed seed`，scenario 里如果有外部依赖一律 mock 或 gold 数据；允许 flaky 指标但必须有"允许波动窗口"（如 3σ 外才算回归）。
2. **不要上 LLM-Judge 就放弃确定性断言**：确定性断言（工具被没被调用、步数、关键字符串）便宜又稳，放在第一层；LLM-Judge 做第二层补充。[^awesome-harness]
3. **Judge 模型别用大模型**：小模型（gpt-4o-mini、qwen2.5-7b）做 judge 够准，成本差 10x+，TRACE 论文已经验证过这一点。[^trace]
4. **Scenario 质量 > 数量**：20 条高质量、覆盖核心业务的 scenario 胜过 500 条边角 case。先从历史线上 top 故障/工单里挑。
5. **Harness 自己也要有测试**：evaluator 和 analyzer 有单测，不然"测试工具出 bug 了比被测系统还难查"。

---

## 参考文献

[^agentcompass]: AgentCompass: A Unified Evaluation Infrastructure for Agent Capabilities, Shanghai AI Laboratory, 2026. https://arxiv.org/pdf/2607.13705
[^trace]: Beyond the Final Answer: Evaluating the Reasoning Trajectories of Tool-Augmented Agents (TRACE), KAIST, ICML 2026. https://arxiv.org/html/2510.02837v3
[^swebench-live]: SWE-bench Goes Live!, Microsoft, 2025. https://arxiv.org/pdf/2505.23419v2.pdf
[^agentevals]: AgentEvals - LangChain trajectory evaluators, 2026. https://github.com/langchain-ai/agentevals
[^traject-bench]: TRAJECT-Bench: A Trajectory-Aware Benchmark for Evaluating Agentic Tool Use, 2025. https://arxiv.org/html/2510.04550v1
[^awesome-harness]: Awesome Agent Harnesses (Harness 分类学与全景清单). https://github.com/Anandesh-Sharma/awesome-agent-harnesses
[^agent-eval-cn]: Agent 评测框架调研报告（2026版）, CSDN. https://blog.csdn.net/weixin_43857576/article/details/160632918
