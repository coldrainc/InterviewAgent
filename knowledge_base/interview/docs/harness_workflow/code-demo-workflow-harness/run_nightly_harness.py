"""Nightly 入口：全量 scenario + Agent Harness（过程性评测）+ Analyzer 诊断 + 报告。

用法：
  python run_nightly_harness.py --gate agent --report nightly-report.html
  可选 --notify-slack channel-xxx（需环境变量 SLACK_WEBHOOK_URL）。
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from harness.schema import Scenario
from harness.runner import ScenarioRunner, DummyAgent
from harness.evaluators.llm_judge import evaluate_llm_assertions, LLMJudge
from harness.analyzers.failure_mode import analyze, findings_summary
from harness.gate import (
    decide, load_baseline, aggregate_scenario_metrics, save_baseline,
)


HTML_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8"/>
<title>Workflow Harness Nightly Report</title>
<style>
 body {{font-family: -apple-system, Segoe UI, sans-serif; margin: 24px; color:#111;}}
 h1,h2,h3 {{margin-top: 2em;}}
 table {{border-collapse: collapse; font-size: 14px;}}
 th, td {{border:1px solid #ddd; padding: 6px 10px; text-align:right;}}
 th:first-child, td:first-child {{text-align:left;}}
 .pass {{color:#0a7d2e; font-weight:bold;}} .fail {{color:#b42318; font-weight:bold;}}
 .tag {{display:inline-block; padding: 2px 8px; border-radius: 12px; background:#eee; margin:2px;}}
</style></head>
<body>
<h1>Workflow Harness Nightly 报告</h1>
<p>生成时间：{now} &nbsp; Gate：<b>{gate}</b> &nbsp; 决策：<span class="{cls}">{verdict}</span></p>

<h2>指标对比（聚合）</h2>
<table><tr><th>Metric</th><th>Baseline</th><th>本次</th><th>变化</th></tr>
{metric_rows}
</table>

<h2>Scenario 矩阵</h2>
<table><tr><th>Scenario</th><th>Success Rate</th><th>Steps</th><th>Cost $</th><th>3D Overall</th><th>Tool Error</th></tr>
{scenario_rows}
</table>

<h2>Analyzer 发现</h2>
<p>总 {count} 条 · {by_severity}</p>
<ul>{findings_items}</ul>

<h2>门禁原因</h2>
<ul>{reason_items}</ul>
</body></html>
"""


def _row(cells, highlight=None):
    cls = ""
    if highlight is not None:
        if isinstance(highlight, (int, float)) and highlight < 0:
            cls = "fail"
        elif isinstance(highlight, (int, float)):
            cls = "pass"
    return "<tr>" + "".join(f"<td class='{cls}'>{c}</td>" for c in cells) + "</tr>"


def build_html(report: dict) -> str:
    agg = report["aggregated"]
    base = report["baseline"]
    metric_rows = ""
    for k in sorted(set(list(agg.keys()) + list(base.keys()))):
        if k == "scenario_count": continue
        v1 = base.get(k, "-")
        v2 = agg.get(k, "-")
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            delta = v2 - v1
            delta_s = f"{delta:+.4f}"
            highlight = delta if "error/cost/step" in k else None
            # 越小越好的项（成本/错误）delta 正值标红
            if any(kk in k for kk in ("cost", "error_rate", "ms", "steps", "count", "repetition")):
                highlight = -delta if delta > 0 else None
            else:
                highlight = delta if delta < 0 else None
        else:
            delta_s = ""
            highlight = None
        metric_rows += _row([k, v1, v2, delta_s], highlight)

    scenario_rows = ""
    for sid, m in report["per_scenario"].items():
        scenario_rows += _row([
            sid,
            f"{m.get('task_success_rate', '?'):.2%}" if isinstance(m.get("task_success_rate"), float) else str(m.get("task_success_rate", "?")),
            m.get("total_steps", "?"),
            f"${m.get('total_cost_usd', 0):.4f}",
            m.get("3d_overall", "?"),
            f"{m.get('tool_error_rate', 0):.2%}",
        ])

    findings = report["analyzer"]
    by_sev = " ".join(
        f"<span class='tag'>{k}: {v}</span>" for k, v in findings["summary"]["by_severity"].items()
    )
    by_tag = " ".join(
        f"<span class='tag'>{k}: {v}</span>" for k, v in findings["summary"]["by_tag"].items()
    )
    findings_items = "".join(
        f"<li><b>[{f['severity']}]</b> {f['tag']} — spans {f['spans']} {f['description']}</li>"
        for f in findings["items"]
    )
    reason_items = "".join(
        f"<li class='{'fail' if r.startswith('[FAIL]') else 'pass'}'>{r}</li>"
        for r in report["decision"]["reasons"]
    )

    verdict = "PASS" if report["decision"]["passed"] else "FAIL"
    return HTML_TEMPLATE.format(
        now=time.strftime("%Y-%m-%d %H:%M:%S"),
        gate=report["gate"],
        verdict=verdict,
        cls="pass" if report["decision"]["passed"] else "fail",
        metric_rows=metric_rows,
        scenario_rows=scenario_rows,
        count=findings["summary"]["count"],
        by_severity=by_sev + " " + by_tag,
        findings_items=findings_items,
        reason_items=reason_items,
    )


def notify_slack(report: dict, webhook: str, channel: str):
    """简单 Slack 通知（非阻塞、失败降级为打印）。"""
    try:
        import urllib.request
    except Exception:
        print("[Slack] 依赖缺失，跳过")
        return
    verdict = "✅ PASS" if report["decision"]["passed"] else "❌ FAIL"
    text = (f"*Workflow Harness Nightly* {verdict}\n"
            f"Scenarios: {report['aggregated'].get('scenario_count', '?')}\n"
            f"Success Rate: {report['aggregated'].get('task_success_rate', '?')}\n"
            f"3D Overall: {report['aggregated'].get('3d_overall', '?')}")
    payload = json.dumps({"channel": channel, "text": text}).encode()
    req = urllib.request.Request(webhook, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[Slack] 通知失败: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", nargs="+", default=["scenarios/*.yml"])
    ap.add_argument("--baseline", default="baselines/v1.0.json")
    ap.add_argument("--gate", default="agent", choices=["test", "agent", "release"])
    ap.add_argument("--report", default="output/nightly-report.html")
    ap.add_argument("--run-llm-judge", action="store_true")
    ap.add_argument("--notify-slack", default=None, help="channel name，需 SLACK_WEBHOOK_URL")
    ap.add_argument("--update-baseline", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    scenario_paths: list[Path] = []
    for pat in args.scenarios:
        scenario_paths.extend(Path(p) for p in glob.glob(pat) if Path(p).exists())
    scenarios = [Scenario.load(p) for p in scenario_paths]
    print(f"[Harness] Nightly, scenarios: {len(scenarios)}, gate: {args.gate}")

    runner = ScenarioRunner(DummyAgent())
    judge = LLMJudge() if args.run_llm_judge else None
    per_scenario: dict[str, dict] = {}
    analyzer_findings: list[dict] = []
    traces_dir = Path(args.report).parent / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)

    for s in scenarios:
        print(f"  - {s.id} ...", end=" ")
        traj, metrics = runner.run(s)

        if judge:
            llm_results = evaluate_llm_assertions(s.assertions, traj, judge)
            # 把 LLM-Judge 结果并入 task_success_rate
            llm_pass = sum(1 for r in llm_results if r["passed"])
            llm_total = len(llm_results) or 1
            # 简单融合：deterministic 与 llm judge 各占一半
            old = metrics["task_success_rate"]
            llm_rate = llm_pass / llm_total
            metrics["task_success_rate"] = round(0.7 * old + 0.3 * llm_rate, 3)
            metrics["llm_judge_results"] = llm_results
            metrics["llm_judge_rate"] = round(llm_rate, 3)

        findings = analyze(traj)
        metrics["analyzer"] = findings_summary(findings)
        for f in findings:
            analyzer_findings.append({
                "scenario": s.id,
                "severity": f.severity,
                "tag": f.tag,
                "spans": f.span_indices,
                "description": f.description,
            })

        print(f"success_rate={metrics['task_success_rate']} "
              f"3d_overall={metrics.get('3d_overall', '?')}")
        per_scenario[s.id] = metrics
        traj.dump_json(traces_dir / f"{s.id}.{traj.trace_id}.json")

    agg = aggregate_scenario_metrics(per_scenario)
    baseline = load_baseline(args.baseline)
    decision = decide(agg, baseline, gate_level=args.gate)

    report = {
        "gate": args.gate,
        "duration_sec": round(time.time() - t0, 1),
        "per_scenario": per_scenario,
        "aggregated": agg,
        "baseline": baseline,
        "decision": decision.to_dict(),
        "analyzer": {
            "summary": findings_summary([
                type('F', (), {"severity": f["severity"], "tag": f["tag"]})()
                for f in analyzer_findings
            ]),
            "items": analyzer_findings,
        },
    }

    # 输出 json 报告
    out_json = Path(args.report).with_suffix(".json")
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # 输出 html 报告
    html = build_html(report)
    Path(args.report).write_text(html, encoding="utf-8")
    print(f"\n[Report] JSON: {out_json} | HTML: {args.report} | 耗时 {report['duration_sec']}s")

    print("\n[Gate Decision]")
    for r in decision.reasons:
        print(f"  {r}")
    print(f"  --> {'PASS' if decision.passed else 'FAIL(阻断)'}")

    if args.notify_slack:
        import os
        wh = os.environ.get("SLACK_WEBHOOK_URL")
        if wh:
            notify_slack(report, wh, args.notify_slack)
        else:
            print("[Slack] 缺少 SLACK_WEBHOOK_URL，跳过通知")

    if decision.passed and args.update_baseline:
        save_baseline(args.baseline, agg)
        print(f"[Baseline] 已更新 {args.baseline}")

    return 0 if decision.passed else 1


if __name__ == "__main__":
    sys.exit(main())
