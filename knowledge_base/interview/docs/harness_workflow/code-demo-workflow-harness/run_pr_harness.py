"""PR 合并门禁入口：跑 Test Harness → 出指标 → 对比 baseline → Pass/Fail。

用法：
  python run_pr_harness.py --scenarios scenarios/*.yml --baseline baselines/v1.0.json --gate test
退出码：0=通过，1=阻断（CI 可直接用）。
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

# 允许 python run_pr_harness.py 直接跑
sys.path.insert(0, str(Path(__file__).parent))

from harness.schema import Scenario
from harness.runner import ScenarioRunner, DummyAgent
from harness.gate import (
    decide, load_baseline, aggregate_scenario_metrics, save_baseline,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", nargs="+", required=True, help="scenario yml 文件或 glob")
    ap.add_argument("--baseline", required=True, help="baseline json 路径")
    ap.add_argument("--gate", default="test", choices=["test", "agent", "release"])
    ap.add_argument("--output", default="output/pr-report.json")
    ap.add_argument("--update-baseline", action="store_true",
                    help="若通过，把本次聚合指标写回 baseline 文件")
    ap.add_argument("--use-real-agent", action="store_true",
                    help="实际接入 Workflow Agent（需要实现 AgentExecutor）")
    args = ap.parse_args()

    # 1. 解析 scenario 列表
    scenario_paths: list[Path] = []
    for pat in args.scenarios:
        scenario_paths.extend(Path(p) for p in glob.glob(pat) if Path(p).exists())
    scenarios = [Scenario.load(p) for p in scenario_paths]
    print(f"[Harness] 加载 scenario 数量: {len(scenarios)}")

    # 2. Runner 初始化（此处默认 DummyAgent，生产替换为真实 Workflow Agent）
    agent = DummyAgent()
    if args.use_real_agent:
        # TODO: 在这里实例化你真实的 AgentExecutor
        # from my_agent import MyWorkflowAgent
        # agent = MyWorkflowAgent()
        raise NotImplementedError("请把你的 AgentExecutor 接进这里后再用 --use-real-agent")
    runner = ScenarioRunner(agent)

    # 3. 跑每个 scenario，采 trajectory + metrics
    per_scenario: dict[str, dict] = {}
    traces_dir = Path(args.output).parent / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    for s in scenarios:
        print(f"  - running {s.id} ...", end=" ")
        traj, metrics = runner.run(s)
        print(f"success_rate={metrics['task_success_rate']} steps={metrics['total_steps']} "
              f"cost=${metrics['total_cost_usd']:.4f}")
        per_scenario[s.id] = metrics
        traj.dump_json(traces_dir / f"{s.id}.{traj.trace_id}.json")

    # 4. 聚合指标 vs baseline → 门禁决策
    agg = aggregate_scenario_metrics(per_scenario)
    baseline = load_baseline(args.baseline)
    decision = decide(agg, baseline, gate_level=args.gate)

    report = {
        "gate": args.gate,
        "per_scenario": per_scenario,
        "aggregated": agg,
        "baseline": baseline,
        "decision": decision.to_dict(),
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n[Gate Decision]")
    for r in decision.reasons:
        print(f"  {r}")
    print(f"  --> {'PASS' if decision.passed else 'FAIL(阻断)'}")

    if decision.passed and args.update_baseline:
        save_baseline(args.baseline, agg)
        print(f"[Baseline] 已更新 {args.baseline}")

    return 0 if decision.passed else 1


if __name__ == "__main__":
    sys.exit(main())
