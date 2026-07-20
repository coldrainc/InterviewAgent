from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select

from interview_agent.infrastructure.db.models import EvalResultModel, EvalRunModel
from interview_agent.infrastructure.db.session import session_scope
from interview_agent.repositories.civil_service_repository import CivilServiceQuestionRepository
from interview_agent.repositories.interview_repository import InterviewRepository
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
        trace_id = None
        job_input: dict = {}
        async with session_scope() as db:
            jobs = JobRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
            job = await jobs.get_job(job_id)
            if not job:
                return
            job_input = dict(job.input_json or {})
            ops = AgentOpsService(db, tenant_id=context.tenant_id, user_id=context.user_id)
            trace = await ops.create_trace(
                trace_type="workflow",
                title=job.title,
                job_id=str(job.id),
                input_payload=job.input_json,
            )
            trace_id = str(trace.id)

        context_payload = await self._load_product_context(context, job_input)
        scenario = str(job_input.get("scenario") or "interview_readiness")
        workflow_output = _build_workflow_output(scenario, context_payload)
        steps = [
            ("intake", "读取用户上下文", workflow_output["intake"]),
            ("plan", "生成执行计划", workflow_output["plan"]),
            ("execute", "生成可执行产物", workflow_output["execution"]),
            ("review", "质量与风险检查", workflow_output["review"]),
        ]

        for index, (key, title, output) in enumerate(steps, start=1):
            await self._run_step(context, job_id, key, title, output, trace_id, span_type="workflow_step", order=index)

        result = {
            "summary": workflow_output["summary"],
            "scenario": scenario,
            "next_actions": workflow_output["next_actions"],
            "readiness_score": workflow_output["review"]["readiness_score"],
            "capabilities": ["workflow", "async_runner", "event_stream", "agentops", "interview", "practice"],
        }
        await self._finish_job(
            context,
            job_id,
            result,
            trace_id=trace_id,
            metrics={
                "readiness_score": workflow_output["review"]["readiness_score"],
                "step_count": len(steps),
                "session_turn_count": context_payload["session"]["turn_count"],
                "question_count": len(context_payload["questions"]),
            },
        )

    async def _run_multi_agent(self, job_id: str, context: RunnerContext) -> None:
        trace_id = None
        job_input: dict = {}
        async with session_scope() as db:
            jobs = JobRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
            job = await jobs.get_job(job_id)
            if not job:
                return
            job_input = dict(job.input_json or {})
            ops = AgentOpsService(db, tenant_id=context.tenant_id, user_id=context.user_id)
            trace = await ops.create_trace(
                trace_type="multi_agent",
                title=job.title,
                job_id=str(job.id),
                input_payload=job.input_json,
            )
            trace_id = str(trace.id)

        context_payload = await self._load_product_context(context, job_input)
        agent_outputs = _build_multi_agent_outputs(context_payload)
        for index, (key, title, role_output) in enumerate(agent_outputs, start=1):
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

        final_report = agent_outputs[-1][2]
        result = {
            "summary": final_report["summary"],
            "agents": [title for _, title, _ in agent_outputs],
            "handoff_policy": "Planner -> Interview Coach -> Practice Coach -> Critic -> Reporter",
            "recommendations": final_report["recommendations"],
            "risks": final_report["risks"],
        }
        await self._finish_job(
            context,
            job_id,
            result,
            trace_id=trace_id,
            metrics={
                "agent_count": len(agent_outputs),
                "session_turn_count": context_payload["session"]["turn_count"],
                "question_count": len(context_payload["questions"]),
                "risk_count": len(final_report["risks"]),
            },
        )

    async def _run_evaluation(self, job_id: str, context: RunnerContext) -> None:
        trace_id = None
        cases = DEFAULT_EVAL_CASES
        job_input: dict = {}
        async with session_scope() as db:
            jobs = JobRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
            job = await jobs.get_job(job_id)
            if not job:
                return
            job_input = dict(job.input_json or {})
            context_payload = await self._load_product_context(context, job_input)
            cases = _normalize_eval_cases(job_input.get("cases")) or _build_eval_cases_from_context(context_payload)
            ops = AgentOpsService(db, tenant_id=context.tenant_id, user_id=context.user_id)
            trace = await ops.create_trace(
                trace_type="evaluation",
                title=job.title,
                job_id=str(job.id),
                input_payload={"case_count": len(cases), **job_input},
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
                "rubric": "基于用户最近会话、题库答案完整度和关键能力检查点进行规则评估，可继续扩展 LLM-as-judge 与人工复核。",
                "cases": cases[:10],
            },
            trace_id=trace_id,
            metrics=metrics,
        )

    async def _load_product_context(self, context: RunnerContext, job_input: dict) -> dict:
        session_id = str(job_input.get("session_id") or "").strip()
        category = str(job_input.get("category") or job_input.get("industry") or "internet").strip()
        subject = str(job_input.get("subject") or "").strip() or None
        async with session_scope() as db:
            interview_repo = InterviewRepository(db, tenant_id=context.tenant_id, user_id=context.user_id)
            if session_id:
                session_record = await interview_repo.get_session_record(session_id)
            else:
                sessions = await interview_repo.list_sessions(limit=1)
                session_record = await interview_repo.get_session_record(sessions[0]["id"]) if sessions else None
            questions, question_total = await CivilServiceQuestionRepository(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            ).list_questions(category=category, subject=subject, limit=12, offset=0)
        return _normalize_product_context(job_input, session_record, questions, question_total)

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
                "actual": str(item.get("actual") or item.get("answer") or item.get("candidate") or "").strip(),
                "expected": str(item.get("expected") or "").strip(),
                "rubric": item.get("rubric") if isinstance(item.get("rubric"), list) else [],
            }
        )
    return cases


def _normalize_product_context(job_input: dict, session_record: dict | None, questions: list[dict], question_total: int) -> dict:
    session = session_record or {}
    turns = session.get("turns") if isinstance(session.get("turns"), list) else []
    profile = dict(job_input.get("profile") or {})
    target_role = (
        str(job_input.get("target_role") or "").strip()
        or str(profile.get("targetRole") or profile.get("target_role") or "").strip()
        or str(session.get("target_role") or "").strip()
        or "AI 应用工程师"
    )
    category = str(job_input.get("category") or session.get("industry") or "internet").strip() or "internet"
    weak_signals = _detect_weak_signals(turns)
    return {
        "input": job_input,
        "profile": {
            "target_role": target_role,
            "seniority": str(job_input.get("seniority") or profile.get("seniority") or session.get("seniority") or "高级"),
            "category": category,
        },
        "session": {
            "id": session.get("id"),
            "status": session.get("status"),
            "turn_count": len(turns),
            "turns": turns[-8:],
            "weak_signals": weak_signals,
        },
        "questions": questions[:12],
        "question_total": question_total,
    }


def _build_workflow_output(scenario: str, context: dict) -> dict:
    profile = context["profile"]
    session = context["session"]
    questions = context["questions"]
    weak_signals = session["weak_signals"]
    readiness_score = _readiness_score(session["turn_count"], len(questions), weak_signals)
    if scenario == "study_plan":
        summary = f"已为 {profile['target_role']} 生成刷题与学习计划，覆盖 {profile['category']} 分类下的默认题库和用户上传题库。"
        next_actions = [
            "先完成 8 道中等难度题并记录错因。",
            "对错题按知识点归因，补齐对应学习卡片。",
            "每天结束前运行一次质量评估，观察通过率变化。",
        ]
    else:
        summary = f"已基于最近面试记录生成 {profile['target_role']} 准备度复盘，当前准备度 {readiness_score} 分。"
        next_actions = [
            "补充一个真实项目的指标、失败案例和复盘结论。",
            "针对追问薄弱点做 3 轮模拟问答。",
            "把回答压缩为 STAR/背景-动作-结果结构。",
        ]
    if weak_signals:
        next_actions.insert(0, f"优先修复：{weak_signals[0]}。")

    return {
        "summary": summary,
        "intake": {
            "target_role": profile["target_role"],
            "category": profile["category"],
            "session_turn_count": session["turn_count"],
            "question_count": len(questions),
            "weak_signals": weak_signals,
        },
        "plan": {
            "phases": [
                {"name": "诊断", "goal": "从最近会话和题库中识别短板。"},
                {"name": "训练", "goal": "用面试追问和刷题闭环薄弱知识点。"},
                {"name": "评估", "goal": "通过质量评估看分数、通过率和风险项。"},
            ],
            "priority": weak_signals or ["项目表达", "系统设计", "质量评估"],
        },
        "execution": {
            "practice_questions": [_question_brief(item) for item in questions[:6]],
            "session_review": _session_review(session["turns"]),
            "deliverables": ["面试复盘", "刷题计划", "质量评估基线", "AgentOps Trace"],
        },
        "review": {
            "readiness_score": readiness_score,
            "quality_gates": [
                {"name": "会话数据", "passed": session["turn_count"] >= 2},
                {"name": "题库覆盖", "passed": len(questions) >= 5},
                {"name": "风险闭环", "passed": readiness_score >= 70},
            ],
            "risks": weak_signals or ["暂无明显风险，建议继续用评测跟踪稳定性。"],
        },
        "next_actions": next_actions,
    }


def _build_multi_agent_outputs(context: dict) -> list[tuple[str, str, dict]]:
    session = context["session"]
    profile = context["profile"]
    questions = context["questions"]
    weak_signals = session["weak_signals"]
    planner = {
        "agent": "Planner",
        "goal": f"提升 {profile['target_role']} 的面试和刷题准备度。",
        "task_plan": ["读取最近会话", "抽取短板", "匹配题库", "生成复盘", "做质量门禁"],
    }
    interview_coach = {
        "agent": "Interview Coach",
        "findings": _session_review(session["turns"]),
        "weak_signals": weak_signals,
    }
    practice_coach = {
        "agent": "Practice Coach",
        "selected_questions": [_question_brief(item) for item in questions[:6]],
        "coverage": {"available": len(questions), "category": profile["category"]},
    }
    critic = {
        "agent": "Critic",
        "risks": weak_signals or ["回答结构基本可用，但仍需持续评估。"],
        "quality_gates": [
            "回答是否有真实指标",
            "是否能解释技术取舍",
            "是否能处理失败与风险追问",
            "是否覆盖题库关键知识点",
        ],
    }
    reporter = {
        "agent": "Reporter",
        "summary": f"多 Agent 审核完成：已形成 {profile['target_role']} 的复盘、题库训练和质量风险清单。",
        "recommendations": [
            "把最近一次回答重写为 90 秒版本。",
            "选 3 道同主题题目做限时训练。",
            "运行质量评估并记录通过率变化。",
        ],
        "risks": critic["risks"],
    }
    return [
        ("planner", "Planner 规划员", planner),
        ("interview_coach", "Interview Coach 面试教练", interview_coach),
        ("practice_coach", "Practice Coach 刷题教练", practice_coach),
        ("critic", "Critic 质检员", critic),
        ("reporter", "Reporter 汇总员", reporter),
    ]


def _build_eval_cases_from_context(context: dict) -> list[dict]:
    cases: list[dict] = []
    for turn in context["session"]["turns"][-5:]:
        answer = str(turn.get("candidate") or "").strip()
        if not answer:
            continue
        cases.append(
            {
                "input": str(turn.get("interviewer") or "面试回答质量评估"),
                "actual": answer,
                "expected": str(turn.get("assessment") or "回答需要包含背景、行动、结果、指标、反思。"),
                "rubric": ["背景", "行动", "结果", "指标", "反思"],
            }
        )
    for question in context["questions"][:5]:
        cases.append(
            {
                "input": question.get("prompt") or "题库质量评估",
                "actual": " ".join(
                    [
                        f"答案：{question.get('answer')}" if question.get("answer") else "",
                        f"解析：{question.get('explanation')}" if question.get("explanation") else "",
                        f"难度：{question.get('difficulty')}" if question.get("difficulty") else "",
                        f"标签：{','.join(str(tag) for tag in (question.get('tags') or []))}" if question.get("tags") else "",
                    ]
                ),
                "expected": "题目需要有答案、解析、难度、标签和可练习性。",
                "rubric": ["答案", "解析", "难度", "标签"],
            }
        )
    return cases or DEFAULT_EVAL_CASES


def _score_eval_case(case: dict) -> tuple[int, str]:
    rubric = [str(item).strip().lower() for item in case.get("rubric", []) if str(item).strip()]
    expected = str(case.get("expected") or "").lower()
    actual = str(case.get("actual") or case.get("input") or "").lower()
    if not rubric:
        rubric = [word for word in expected.replace("、", " ").replace("，", " ").split() if len(word) > 1]
    inspected = actual or expected
    hits = sum(1 for item in rubric if item and item in inspected)
    content_bonus = 10 if len(actual) >= 120 else 0
    score = 68 if not rubric else min(100, 45 + content_bonus + round((hits / max(len(rubric), 1)) * 45))
    feedback = f"规则评估得分 {score}。命中 {hits}/{len(rubric) or 1} 个检查点，内容长度 {len(actual)}。"
    return score, feedback


def _detect_weak_signals(turns: list[dict]) -> list[str]:
    signals: list[str] = []
    answers = [str(turn.get("candidate") or "") for turn in turns if str(turn.get("candidate") or "").strip()]
    joined = "\n".join(answers)
    if not answers:
        return ["还没有足够会话数据，需要先完成一轮面试或刷题。"]
    if sum(len(answer) for answer in answers) / max(len(answers), 1) < 80:
        signals.append("回答偏短，缺少背景、过程和结果展开")
    if not any(keyword in joined for keyword in ("指标", "QPS", "延迟", "准确率", "成本", "转化率", "%")):
        signals.append("缺少量化指标")
    if not any(keyword in joined for keyword in ("失败", "问题", "风险", "复盘", "取舍", "权衡")):
        signals.append("缺少失败案例、风险意识或技术取舍")
    if not any(keyword.lower() in joined.lower() for keyword in ("rag", "agent", "评测", "trace", "监控", "安全")):
        signals.append("AI 工程生产化关键词覆盖不足")
    return signals[:4]


def _readiness_score(turn_count: int, question_count: int, weak_signals: list[str]) -> int:
    score = 52 + min(turn_count, 6) * 5 + min(question_count, 10) * 2 - len(weak_signals) * 6
    return max(35, min(96, score))


def _session_review(turns: list[dict]) -> list[dict]:
    if not turns:
        return [{"finding": "暂无会话记录", "action": "先完成一轮面试，再生成复盘。"}]
    reviews = []
    for turn in turns[-4:]:
        answer = str(turn.get("candidate") or "")
        reviews.append(
            {
                "question": str(turn.get("interviewer") or "")[:120],
                "answer_length": len(answer),
                "action": "补充指标和取舍" if len(answer) < 120 else "保留结构，继续增加失败复盘",
            }
        )
    return reviews


def _question_brief(question: dict) -> dict:
    return {
        "id": question.get("id"),
        "subject": question.get("subject"),
        "difficulty": question.get("difficulty"),
        "prompt": str(question.get("prompt") or "")[:140],
        "has_answer": bool(question.get("answer")),
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)
