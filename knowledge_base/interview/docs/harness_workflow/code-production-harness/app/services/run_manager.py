"""Run Manager：编排 scenario 执行、采 span、写 Mongo、调用门禁决策。
核心被 Celery Worker 调（异步）和 /runs API 调（同步 dry-run）。
"""
from __future__ import annotations

import time
from typing import Optional

import structlog
from beanie import PydanticObjectId

from ..config import Settings, get_settings
from ..models.mongo import AnalyzerFindingDoc, RunDoc, SpanDoc
from ..repos.repos import BaselineRepo, RunRepo, ScenarioRepo
from ..schema import Scenario, Span, SpanType, EvidenceRef
from .gate_logic import decide
# 生产接入 LangGraph；也允许接你现有自研 Runtime（通过环境变量切换）
from ..executors.langgraph_executor import LangGraphAgentExecutor

log = structlog.get_logger()


class RunManager:
    def __init__(self, settings: Optional[Settings] = None):
        self.s = settings or get_settings()
        self.agent = LangGraphAgentExecutor()  # 可替换为自定义 Runtime

    # ------------------------------------------------------------------
    # 执行单个 scenario
    # ------------------------------------------------------------------

    async def run_scenario(self, *, scenario_id: str, gate_level: str,
                           triggered_by: str, commit_sha: Optional[str] = None,
                           pr_id: Optional[str] = None, dry_run: bool = False) -> RunDoc:
        scenario_doc = await ScenarioRepo.get(scenario_id)
        if not scenario_doc:
            raise ValueError(f"scenario 不存在: {scenario_id}")
        scenario = Scenario.model_validate(scenario_doc.model_dump(
            include={"scenario_id": scenario_doc.scenario_id,
                     **{f: getattr(scenario_doc, f)
                        for f in ("version", "tags", "source", "difficulty",
                                  "input", "assertions", "golden_trajectory_hints",
                                  "tools_whitelist", "seed")}))

        run = RunDoc(
            trace_id=f"tr_{scenario_id}_{int(time.time())}",
            agent_run_id=f"ar_{PydanticObjectId()}",
            scenario_id=scenario_id,
            scenario_version=scenario.version,
            gate_level=gate_level,
            triggered_by=triggered_by,
            commit_sha=commit_sha,
            pr_id=pr_id,
            status="running",
            started_at=time.time(),
        )
        run = await RunRepo.create(run)
        log.info("run.started", run_id=str(run.id), scenario=scenario_id, gate=gate_level)

        try:
            traj, metrics, assertions, span_docs, findings = self._execute_and_evaluate(
                run.id, scenario, timeout_sec=self.s.RUN_MAX_TIMEOUT_SEC)
            # 门禁
            baseline = (await BaselineRepo.latest())
            base_metrics = baseline.metrics if baseline else {}
            decision = decide(metrics, base_metrics, gate_level,
                              gate_enabled=self.s.GATE_ENABLED,
                              deferred_llm_as_pass=self.s.DEFERRED_LLM_AS_PASS)
            await RunRepo.set_status(
                run.id, "succeeded",
                metrics=metrics,
                assertions=[a.model_dump() for a in assertions] if hasattr(assertions[0], "model_dump") else assertions,
                analyzer_findings_summary=findings.get("summary", {}),
                gate_passed=decision.passed,
                gate_reasons=decision.reasons,
            )
            await RunRepo.append_spans(run.id, span_docs)
            if findings.get("items"):
                await RunRepo.add_findings(run.id, findings["items"])
            log.info("run.done", run_id=str(run.id), passed=decision.passed,
                     success_rate=metrics.get("task_success_rate"))
        except Exception as e:  # pragma: no cover - 任务本身的异常（Agent/DB）
            log.exception("run.failed", run_id=str(run.id), err=repr(e))
            await RunRepo.set_status(run.id, "failed", runtime_error=repr(e),
                                     gate_passed=False,
                                     gate_reasons=[f"RUN ERROR: {e!r:.200s}"])
        # 重新取最新
        updated = await RunRepo.get(run.id)
        assert updated is not None
        return updated

    # ------------------------------------------------------------------
    # 内部：执行 + 评测（同步）
    # ------------------------------------------------------------------

    def _execute_and_evaluate(self, run_id, scenario: Scenario, *, timeout_sec: int):
        # 1) 调 agent executor，边跑边采 span
        from ..evaluators.deterministic import evaluate_assertions
        from ..evaluators.trajectory import evaluate_trajectory
        from ..evaluators.metrics import compute_all_metrics
        from ..analyzers.failure_mode import analyze, findings_summary

        deadline = time.time() + timeout_sec
        spans_schema: list[Span] = []
        tokens = cost = 0.0
        evidence_refs = []
        final_output = ""

        iter_stream = self.agent.run_stream(
            user_prompt=scenario.input.user_prompt,
            context=scenario.build_execution_context(),
            tools_whitelist=scenario.tools_whitelist,
            seed=scenario.seed,
        )
        for turn in iter_stream:
            if time.time() > deadline:
                raise TimeoutError(f"run 超过 {timeout_sec}s 硬超时")
            span = Span.from_turn(turn, parent=spans_schema[-1] if spans_schema else None)
            spans_schema.append(span)
            tokens += span.token_count
            cost += span.cost_usd
            if turn.get("type") == "final_answer":
                final_output = span.output_snippet
                evidence_refs.extend(turn.get("evidence_refs", []))

        # 2) 构建 Trajectory（用于 evaluator，不直接写 Mongo 而是把 span_docs 写 Mongo）
        from ..schema import Trajectory
        traj = Trajectory(
            trace_id=f"tr_{run_id}",
            started_at=spans_schema[0].started_at if spans_schema else time.time(),
            ended_at=time.time(),
            total_token_count=int(tokens),
            total_cost_usd=float(cost),
            spans=spans_schema,
            evidence_bank_refs=[EvidenceRef(**r) for r in evidence_refs],
        )

        # 3) evaluators
        det = evaluate_assertions(scenario, traj)
        traj_eval = evaluate_trajectory(scenario, traj)
        metrics = compute_all_metrics(traj, scenario)
        metrics.update(traj_eval)

        # 4) analyzers
        finding_objs = analyze(traj)
        finding_docs = [AnalyzerFindingDoc(
            tag=f.tag, severity=f.severity,
            span_indices=f.span_indices, description=f.description,
        ) for f in finding_objs]

        # 5) Mongo 用的 SpanDoc 列表
        span_docs = [SpanDoc(
            run_id=PydanticObjectId(run_id),
            span_id=s.span_id, parent_span_id=s.parent_span_id,
            type=s.type.value if isinstance(s.type, SpanType) else s.type,
            name=s.name, started_at=s.started_at,
            duration_ms=s.duration_ms, token_count=s.token_count,
            cost_usd=s.cost_usd,
            status=s.status.value if hasattr(s.status, "value") else s.status,
            tool_name=s.tool_name, tool_args=s.tool_args,
            input_snippet=str(s.input)[:800], output_snippet=s.output_snippet[:800],
            error_message=s.error_message,
        ) for s in spans_schema]

        findings_out = {
            "items": finding_docs,
            "summary": findings_summary(finding_objs),
        }
        return traj, metrics, det["assertions"], span_docs, findings_out
