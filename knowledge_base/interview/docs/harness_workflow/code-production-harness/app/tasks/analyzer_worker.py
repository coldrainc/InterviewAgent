"""Analyzer Worker：Run 完成后异步跑 analyzers + LLM-Judge，避免阻塞主 Run。
低优先级队列，即使延迟不影响门禁决策。
"""
from __future__ import annotations

import structlog
from beanie import PydanticObjectId

from .runner_worker import _run_sync, celery_app

log = structlog.get_logger()


@celery_app.task(name="analyzer.run_analyzers", queue="analyzer_queue",
                 rate_limit="120/m", autoretry_for=(Exception,), retry_backoff=3)
def analyze_run_task(run_id: str):
    """跑：
    1) failure mode analyzers（规则，无成本）
    2) LLM-Judge（可关闭，受 LLM 可用性影响）
    """
    async def _inner():
        from ..repos.repos import RunRepo
        from ..models.mongo import ScenarioDoc, AnalyzerFindingDoc
        from ..analyzers.failure_mode import analyze, findings_summary
        from ..schema import Trajectory, Span as SpanSchema, EvidenceRef as ER
        from ..evaluators.llm_judge import evaluate_llm_assertions, LLMJudge
        from ..config import get_settings

        run = await RunRepo.get(PydanticObjectId(run_id))
        if not run:
            return
        sdoc = await ScenarioDoc.find_one(ScenarioDoc.scenario_id == run.scenario_id)
        if not sdoc:
            return
        # 1) 从 Mongo spans 拼 trajectory 给 analyzer 用
        from ..models.mongo import SpanDoc
        span_rows = await SpanDoc.find(SpanDoc.run_id == run.id).to_list(length=5000)
        spans_schema = [
            SpanSchema(
                span_id=r.span_id, parent_span_id=r.parent_span_id,
                type=r.type, name=r.name, started_at=r.started_at.timestamp(),
                duration_ms=r.duration_ms, token_count=r.token_count,
                cost_usd=r.cost_usd, status=r.status,
                tool_name=r.tool_name, tool_args=r.tool_args,
                output_snippet=r.output_snippet, error_message=r.error_message,
            ) for r in span_rows
        ]
        traj = Trajectory(
            trace_id=run.trace_id, started_at=run.started_at.timestamp(),
            ended_at=(run.ended_at or run.started_at).timestamp(),
            total_token_count=run.metrics.get("total_token_count", 0),
            total_cost_usd=run.metrics.get("total_cost_usd", 0.0),
            spans=spans_schema,
            evidence_bank_refs=[],
        )

        findings = analyze(traj)
        docs = [AnalyzerFindingDoc(run_id=run.id, tag=f.tag, severity=f.severity,
                                    span_indices=f.span_indices,
                                    description=f.description)
                for f in findings]
        if docs:
            await AnalyzerFindingDoc.insert_many(docs)
        summary = findings_summary(findings)

        # 2) LLM-Judge：只针对 scenario 中 llm_judge 的断言
        from ..schema import Scenario as ScenarioSchema, Assertion
        judge_results = []
        if get_settings().LLM_API_KEY:
            try:
                sc = ScenarioSchema.model_validate(sdoc.model_dump(
                    include={f: getattr(sdoc, f) for f in (
                        "scenario_id", "version", "tags", "source", "difficulty",
                        "input", "assertions", "golden_trajectory_hints",
                        "tools_whitelist", "seed",
                    )}))
                judge = LLMJudge(model=sc.llm_model or get_settings().LLM_DEFAULT_MODEL)
                judge_results = evaluate_llm_assertions(sc.assertions, traj, judge)
            except Exception as e:
                log.exception("llm_judge_failed", run_id=run_id, err=str(e))

        # 回写 run
        update = {"analyzer_findings_summary": summary}
        if judge_results:
            # 融合进入 gate 指标：LLM-Judge 通过率
            total_judge = len(judge_results) or 1
            pass_rate = sum(1 for r in judge_results if r["passed"]) / total_judge
            update["llm_judge_results"] = judge_results
            update["metrics.llm_judge_rate"] = pass_rate
            # 如果之前 gate 是基于 deterministic 过的，但 LLM-Judge 没过且开关未按 defer 处理，则更新为失败
            if not get_settings().DEFERRED_LLM_AS_PASS and pass_rate < 0.8 and run.gate_passed:
                update["gate_passed"] = False
                if run.gate_reasons is not None:
                    run.gate_reasons.append(
                        f"[FAIL] LLM-Judge 通过率 {pass_rate:.0%} < 80%")
                    update["gate_reasons"] = run.gate_reasons

        await RunRepo.set_status(run.id, run.status, **update)
        return {"run_id": run_id, "findings_count": len(docs),
                "summary": summary, "llm_judge_count": len(judge_results)}

    return _run_sync(_inner())


@celery_app.task(name="analyzer.nightly_summary_notify", queue="analyzer_queue")
def nightly_summary_notify(output_json_path: str, notify_channel: str | None = None):
    """Nightly 完成后推送报告到飞书 / Slack。详见 report_service。"""
    import json, os
    from pathlib import Path
    report = json.loads(Path(output_json_path).read_text(encoding="utf-8"))
    webhook = os.environ.get("SLACK_WEBHOOK_URL") or os.environ.get("FEISHU_WEBHOOK_URL")
    if webhook and notify_channel:
        try:
            import httpx
            verdict = "✅ PASS" if report["decision"]["passed"] else "❌ FAIL"
            text = (f"*Harness Nightly Report* {verdict}\n"
                    f"Scenarios: {report['aggregated']['scenario_count']}\n"
                    f"Success Rate: {report['aggregated'].get('task_success_rate', 'N/A')}\n"
                    f"3D Overall: {report['aggregated'].get('3d_overall', 'N/A')}\n"
                    f"Cost: ${report['aggregated'].get('total_cost_usd', 0):.4f}\n")
            httpx.post(webhook, json={"text": text, "channel": notify_channel}, timeout=5)
        except Exception as e:
            log.warning("notify_failed", err=str(e))
    return "notified"
