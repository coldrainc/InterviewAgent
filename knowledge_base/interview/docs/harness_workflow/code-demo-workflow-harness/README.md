# Workflow Agent Harness - 最小可运行骨架

> 本目录是方案文档「AI-Native 全栈工作流优化方案与 Harness 设计.md」的配套代码骨架。
> 遵循方案 v1.0 中 Scenario×Harness×Environment 三层解耦设计，可直接 `pip install -e .` 后在 CI 运行。

## 目录

```
harness/
├── schema.py           # Scenario / Trajectory / Span 数据模型
├── runner.py           # ScenarioRunner：跑 scenario，采集 trajectory
├── evaluators/
│   ├── deterministic.py  # 确定性断言（tool_called、max_steps 等）
│   ├── trajectory.py     # Trajectory 过程评测（工具正确性、三维度打分）
│   ├── llm_judge.py      # LLM-as-Judge（temperature=0 + seed 固定）
│   └── metrics.py        # 四大类指标计算（完成度/过程/成本/安全）
├── analyzers/
│   ├── repetition.py   # 重复工具循环检测
│   ├── latency.py      # 延迟尖刺检测
│   └── failure_mode.py # 失败模式自动分类
└── gate.py             # 回归门禁（baseline 对比 + 阈值决策）

scenarios/
├── diag-sandbox-toml-damage.yml
└── rag-business-qa.yml

baselines/
└── v1.0.json

run_pr_harness.py          # PR 合并门禁入口
run_nightly_harness.py     # Nightly 入口（Eval + Agent + Analyzer）
```

## 快速运行

```bash
pip install -e .
export OPENAI_API_KEY=...   # 只有 llm_judge 需要，deterministic evaluator 不需要

# 本地跑单个 scenario
python -c "
from harness.schema import load_scenario
from harness.runner import DummyAgent, ScenarioRunner
s = load_scenario('scenarios/diag-sandbox-toml-damage.yml')
runner = ScenarioRunner(DummyAgent())
traj, metrics = runner.run(s)
print('task_success_rate:', metrics['task_success_rate'])
"

# PR 门禁
python run_pr_harness.py --scenarios scenarios/*.yml --baseline baselines/v1.0.json --gate test

# Nightly
python run_nightly_harness.py --gate agent --report nightly-report.html
```
