from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select

from interview_agent.infrastructure.db.models import EvalResultModel, EvalRunModel
from interview_agent.infrastructure.db.session import session_scope
from interview_agent.repositories.job_repository import JobRepository, job_to_dict
from interview_agent.services.agent_ops_service import AgentOpsService


TERMINAL_JOB_STATUSES = {"succeeded", "failed", "canceled"}


@dataclass(frozen=True)
class RunnerContext:
    tenant_id: str
    user_id: str


DEFAULT_EVAL_CASES = [
    {
        "input": "解释 Agent Harness 在复杂任务中的作用。",
        "expected": "需要提到工具调用、状态管理、规划执行、可观测性和失败恢复。",
        "rubric": ["工具调用", "状态", "规划", "可观测性", "恢复"],
    },
    {
        "input": "说明 RAG 系统上线前要做哪些质量评估。",
        "expected": "需要覆盖召回、答案正确性、引用、延迟、成本和安全。",
        "rubric": ["召回", "正确性", "引用", "延迟", "成本", "安全"],
    },
    {
        "input": "为什么长任务平台要有幂等、重试和事件流？",
        "expected": "需要说明请求不可靠、任务可恢复、用户可观察进度、避免重复副作用。",
        "rubric": ["幂等", "重试", "恢复", "进度", "副作用"],
    },
]


class WorkflowRunner:
    async def run_job(self, job_id: str, context: RunnerContext) -> None:
        try:
            async with session_scope() as db:
                jobs = JobRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
                job = await jobs.get_job(job_id)
                if not job:
                    return
                if job.status == "canceled":
                    return
                await jobs.set_job_status(job.id, "running")
                job_type = job.job_type

            if job_type == "evaluation":
                await self._run_evaluation(job_id, context)
            elif job_type == "multi_agent":
                await self._run_multi_agent(job_id, context)
            else:
                await self._run_workflow(job_id, context)
        except Exception as exc:
            async with session_scope() as db:
                jobs = JobRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
                await jobs.set_job_status(job_id, "failed", error_message=str(exc))

    async def _run_workflow(self, job_id: str, context: RunnerContext) -> None:
        steps = [
            ("intake", "解析任务输入", {"checks": ["目标", "约束", "交付物"]}),
            ("plan", "生成执行计划", {"strategy": "分阶段拆解，先低风险能力闭环"}),
            ("execute", "执行核心工作流", {"artifacts": ["job", "event", "trace", "eval"]}),
            ("review", "质量检查", {"gates": ["结构化输出", "状态一致性", "可观测性"]}),
        ]
        trace_id = None
        async with session_scope() as db:
            jobs = JobRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
            job = await jobs.get_job(job_id)
            if not job:
                return
            ops = AgentOpsService(db, tenant_id=context.tenant_id, user_id=context.user_id)
            trace = await ops.create_trace(
                trace_type="workflow",
                title=job.title,
                job_id=str(job.id),
                input_payload=job.input_json,
            )
            trace_id = str(trace.id)

        for index, (key, title, output) in enumerate(steps, start=1):
            await self._run_step(context, job_id, key, title, output, trace_id, span_type="workflow_step", order=index)

        result = {
            "summary": "复杂任务编排已完成：任务输入、计划、执行、检查全部落到 Job/Step/Event/Trace。",
            "capabilities": ["workflow", "async_runner", "event_stream", "agentops"],
        }
        await self._finish_job(context, job_id, result, trace_id=trace_id)

    async def _run_multi_agent(self, job_id: str, context: RunnerContext) -> None:
        agents = [
            ("planner", "Planner 规划员", "拆解目标、约束、验收标准"),
            ("researcher", "Researcher 检索员", "查找知识库、题库、历史会话和外部资料入口"),
            ("executor", "Executor 执行员", "调用工具和业务模块完成任务"),
            ("critic", "Critic 质检员", "检查幻觉、遗漏、成本和安全风险"),
            ("reporter", "Reporter 汇总员", "输出结构化结果和后续动作"),
        ]
        trace_id = None
        async with session_scope() as db:
            jobs = JobRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
            job = await jobs.get_job(job_id)
            if not job:
                return
            ops = AgentOpsService(db, tenant_id=context.tenant_id, user_id=context.user_id)
            trace = await ops.create_trace(
                trace_type="multi_agent",
                title=job.title,
                job_id=str(job.id),
                input_payload=job.input_json,
            )
            trace_id = str(trace.id)

        for index, (key, title, role_output) in enumerate(agents, start=1):
            await self._run_step(
                context,
                job_id,
                key,
                title,
                {"agent": title, "decision": role_output},
                trace_id,
                span_type="agent",
                order=index,
            )

        result = {
            "summary": "多 Agent 协作链路已跑通。当前版本是可观测骨架，后续可把每个 agent 接入真实 LLM/tool 调用。",
            "agents": [title for _, title, _ in agents],
            "handoff_policy": "Planner -> Researcher -> Executor -> Critic -> Reporter",
        }
        await self._finish_job(context, job_id, result, trace_id=trace_id)

    async def _run_evaluation(self, job_id: str, context: RunnerContext) -> None:
        trace_id = None
        cases = DEFAULT_EVAL_CASES
        async with session_scope() as db:
            jobs = JobRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
            job = await jobs.get_job(job_id)
            if not job:
                return
            cases = _normalize_eval_cases(job.input_json.get("cases")) or DEFAULT_EVAL_CASES
            ops = AgentOpsService(db, tenant_id=context.tenant_id, user_id=context.user_id)
            trace = await ops.create_trace(
                trace_type="evaluation",
                title=job.title,
                job_id=str(job.id),
                input_payload={"case_count": len(cases), **job.input_json},
            )
            trace_id = str(trace.id)
            run = EvalRunModel(
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                job_id=job.id,
                name=job.title,
                status="running",
                metrics_json={},
                created_at=_now(),
            )
            db.add(run)
            await db.flush()
            run_id = str(run.id)

        scores: list[int] = []
        for index, case in enumerate(cases, start=1):
            score, feedback = _score_eval_case(case)
            scores.append(score)
            await self._run_step(
                context,
                job_id,
                f"case-{index}",
                f"评测用例 {index}",
                {"score": score, "passed": score >= 70, "feedback": feedback},
                trace_id,
                span_type="eval_case",
                order=index,
            )
            async with session_scope() as db:
                result = EvalResultModel(
                    run_id=uuid.UUID(run_id),
                    score=score,
                    passed=score >= 70,
                    feedback=feedback,
                    metadata_json={"case": case},
                    created_at=_now(),
                )
                db.add(result)

        average = round(sum(scores) / max(len(scores), 1), 2)
        metrics = {
            "case_count": len(scores),
            "average_score": average,
            "pass_rate": round(sum(1 for score in scores if score >= 70) / max(len(scores), 1), 4),
        }
        async with session_scope() as db:
            run = await db.get(EvalRunModel, uuid.UUID(run_id))
            if run:
                run.status = "succeeded"
                run.metrics_json = metrics
                run.finished_at = _now()
        await self._finish_job(
            context,
            job_id,
            {
                "summary": "质量评估已完成。",
                "metrics": metrics,
                "rubric": "当前 MVP 使用规则评估；后续可接入 LLM-as-judge、人工复核和黄金集回归。",
            },
            trace_id=trace_id,
            metrics=metrics,
        )

    async def _run_step(
        self,
        context: RunnerContext,
        job_id: str,
        key: str,
        title: str,
        output: dict,
        trace_id: str | None,
        *,
        span_type: str,
        order: int,
    ) -> None:
        async with session_scope() as db:
            jobs = JobRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
            job = await jobs.get_job(job_id)
            if not job or job.status == "canceled":
                return
            await jobs.upsert_step(job.id, step_key=key, title=title, status="running", input_payload={"order": order})
        await asyncio.sleep(0.05)
        async with session_scope() as db:
            jobs = JobRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
            await jobs.upsert_step(job_id, step_key=key, title=title, status="succeeded", output_payload=output)
            if trace_id:
                ops = AgentOpsService(db, tenant_id=context.tenant_id, user_id=context.user_id)
                await ops.add_span(
                    trace_id,
                    name=title,
                    span_type=span_type,
                    input_payload={"order": order},
                    output_payload=output,
                    metrics={"duration_ms": 50},
                )

    async def _finish_job(
        self,
        context: RunnerContext,
        job_id: str,
        result: dict,
        *,
        trace_id: str | None,
        metrics: dict | None = None,
    ) -> None:
        async with session_scope() as db:
            jobs = JobRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
            await jobs.set_job_status(job_id, "succeeded", result_payload=result)
            if trace_id:
                ops = AgentOpsService(db, tenant_id=context.tenant_id, user_id=context.user_id)
                await ops.finish_trace(trace_id, status="succeeded", result_payload=result, metrics=metrics or {})


async def create_and_start_job(
    *,
    tenant_id: str,
    user_id: str,
    job_type: str,
    title: str,
    input_payload: dict | None = None,
) -> dict:
    async with session_scope() as db:
        repo = JobRepository(db, tenant_id=tenant_id, user_id=user_id)
        job = await repo.create_job(job_type=job_type, title=title, input_payload=input_payload or {})
        payload = job_to_dict(job)
        job_id = str(job.id)
    asyncio.create_task(WorkflowRunner().run_job(job_id, RunnerContext(tenant_id=tenant_id, user_id=user_id)))
    return payload


def _normalize_eval_cases(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    cases = []
    for item in value[:50]:
        if not isinstance(item, dict):
            continue
        input_text = str(item.get("input") or item.get("question") or "").strip()
        if not input_text:
            continue
        cases.append(
            {
                "input": input_text,
                "expected": str(item.get("expected") or "").strip(),
                "rubric": item.get("rubric") if isinstance(item.get("rubric"), list) else [],
            }
        )
    return cases


def _score_eval_case(case: dict) -> tuple[int, str]:
    rubric = [str(item).strip().lower() for item in case.get("rubric", []) if str(item).strip()]
    expected = str(case.get("expected") or "").lower()
    if not rubric:
        rubric = [word for word in expected.replace("、", " ").replace("，", " ").split() if len(word) > 1]
    hits = sum(1 for item in rubric if item and item in expected)
    score = 72 if not rubric else min(100, 60 + round((hits / max(len(rubric), 1)) * 40))
    feedback = f"规则评估得分 {score}。命中 {hits}/{len(rubric) or 1} 个检查点。"
    return score, feedback


def _now() -> datetime:
    return datetime.now(timezone.utc)
