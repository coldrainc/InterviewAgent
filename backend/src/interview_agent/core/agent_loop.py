from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from time import perf_counter
from typing import TYPE_CHECKING, Any, TypedDict
from uuid import uuid4

from interview_agent.core.config import InterviewConfig, InterviewMode, InterviewStage
from interview_agent.core.guardrails import GuardrailFinding
from interview_agent.domain.billing import TokenUsage
from interview_agent.core.industry import get_industry_profile
from interview_agent.core.state import InterviewState

if TYPE_CHECKING:
    from interview_agent.core.harness import InterviewHarness


@dataclass
class LoopResult:
    state: InterviewState
    message: str
    advanced: bool = True
    guardrail_findings: list[GuardrailFinding] | None = None
    fallback_used: bool = False
    usage: TokenUsage | None = None
    orchestration: dict[str, Any] | None = None
    evaluation: dict[str, Any] | None = None


@dataclass(frozen=True)
class AnswerAssessment:
    score: int
    needs_more_depth: bool
    reason: str


class InputKind(str, Enum):
    ANSWER = "answer"
    CLARIFYING_QUESTION = "clarifying_question"
    TOO_SHORT = "too_short"


@dataclass
class GraphNodeEvent:
    node: str
    status: str
    duration_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": self.node,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
            "metadata": self.metadata,
            "error": self.error,
        }


class AgentLoop:
    """Explicit interview control loop around the LangChain harness."""

    def __init__(self, config: InterviewConfig, harness: "InterviewHarness") -> None:
        self.config = config
        self.harness = harness
        self.state = InterviewState()
        self.thread_id = f"interview-{uuid4()}"
        self._graph_unavailable_reason = ""
        try:
            self._graph_executor = _build_langgraph_executor(self)
        except Exception as exc:
            self._graph_unavailable_reason = str(exc)
            self._graph_executor = None

    def start(self) -> LoopResult:
        harness_result = self.harness.generate_result(InterviewStage.INTRO, self.state)
        message = harness_result.text
        self.state.stage = InterviewStage.INTRO
        self.state.add_interviewer_message(InterviewStage.INTRO, message)
        return LoopResult(
            state=self.state,
            message=message,
            guardrail_findings=harness_result.findings,
            fallback_used=harness_result.fallback_used,
            usage=harness_result.usage,
        )

    def step(self, candidate_response: str) -> LoopResult:
        return self.handle_input(candidate_response)

    def step_stream(self, candidate_response: str, on_delta: Callable[[str], None]) -> LoopResult:
        return self.handle_input(candidate_response, on_delta=on_delta)

    @property
    def uses_langgraph(self) -> bool:
        return self._graph_executor is not None

    @property
    def orchestration_status(self) -> dict[str, Any]:
        if self._graph_executor is None:
            return {
                "engine": "explicit",
                "langgraph_enabled": False,
                "thread_id": self.thread_id,
                "unavailable_reason": self._graph_unavailable_reason,
            }
        return self._graph_executor.status()

    def set_thread_id(self, thread_id: str) -> None:
        cleaned = thread_id.strip()
        if cleaned:
            self.thread_id = cleaned

    def handle_input(
        self,
        candidate_input: str,
        on_delta: Callable[[str], None] | None = None,
    ) -> LoopResult:
        if self._graph_executor is not None:
            return self._graph_executor.run(candidate_input, on_delta=on_delta)
        result = self._handle_input_explicit(candidate_input, on_delta=on_delta)
        result.orchestration = self.orchestration_status
        return result

    def _handle_input_explicit(
        self,
        candidate_input: str,
        on_delta: Callable[[str], None] | None = None,
    ) -> LoopResult:
        if self.config.mode == InterviewMode.CANDIDATE:
            return self._handle_interviewer_question(candidate_input, on_delta=on_delta)

        if self.state.completed:
            return LoopResult(self.state, "Interview already completed.", advanced=False)
        if not self.state.turns:
            self.start()

        input_check = self.harness.guardrails.check_candidate_input(candidate_input)
        if input_check.blocked:
            message = self.harness.guardrails.blocked_message(input_check.findings)
            return LoopResult(
                self.state,
                message,
                advanced=False,
                guardrail_findings=input_check.findings,
            )

        cleaned_input = input_check.text
        input_kind = self._classify_input(cleaned_input)
        if input_kind == InputKind.CLARIFYING_QUESTION:
            if on_delta:
                harness_result = self.harness.respond_to_candidate_question_result_stream(
                    cleaned_input,
                    self.state,
                    on_delta,
                )
            else:
                harness_result = self.harness.respond_to_candidate_question_result(
                    cleaned_input,
                    self.state,
                )
            return LoopResult(
                self.state,
                harness_result.text,
                advanced=False,
                guardrail_findings=input_check.findings + harness_result.findings,
                fallback_used=harness_result.fallback_used,
                usage=harness_result.usage,
            )
        if input_kind == InputKind.TOO_SHORT:
            active_question = self.state.turns[-1].interviewer
            message = (
                "我先不把这句计入面试回答。请展开一点，最好说明你的设计、取舍和失败处理。\n\n"
                f"当前问题：{active_question}"
            )
            return LoopResult(
                self.state,
                message,
                advanced=False,
                guardrail_findings=input_check.findings,
            )

        self.state.add_candidate_message(cleaned_input)
        assessment = self._assess_answer(cleaned_input)
        self.state.last_answer_assessment = (
            f"回答质量信号：{assessment.score}/6；{assessment.reason}；"
            f"{'建议继续深挖当前方向' if assessment.needs_more_depth else '可以在给出阶段性判断后切换方向'}。"
        )
        next_stage = self._next_stage(assessment)
        if next_stage == InterviewStage.EVALUATION:
            harness_result = self._run_evaluation(on_delta=on_delta)
        elif on_delta:
            harness_result = self.harness.generate_result_stream(next_stage, self.state, on_delta)
        else:
            harness_result = self.harness.generate_result(next_stage, self.state)
        message = harness_result.text
        self.state.stage = next_stage
        self.state.add_interviewer_message(next_stage, message)

        if next_stage == InterviewStage.EVALUATION:
            self.state.completed = True

        return LoopResult(
            state=self.state,
            message=message,
            guardrail_findings=input_check.findings + harness_result.findings,
            fallback_used=harness_result.fallback_used,
            usage=harness_result.usage,
            evaluation=harness_result.structured,
        )

    def _run_evaluation(
        self, on_delta: Callable[[str], None] | None = None
    ) -> "HarnessResult":
        """生成结构化评估报告；harness 不支持时退化为文本评估。"""
        from interview_agent.core.evaluation import degraded_payload, render_evaluation_text
        from interview_agent.core.harness_result import HarnessResult

        generator = getattr(self.harness, "generate_evaluation_result", None)
        if generator is None:
            if on_delta:
                result = self.harness.generate_result_stream(
                    InterviewStage.EVALUATION, self.state, on_delta
                )
            else:
                result = self.harness.generate_result(InterviewStage.EVALUATION, self.state)
            payload = degraded_payload(result.text, self.config.mode)
            result.structured = payload
            result.text = render_evaluation_text(payload, self.config.mode)
            return result
        result = generator(self.state)
        if not isinstance(result, HarnessResult):
            result = HarnessResult(text=str(result))
        if result.structured is None:
            result.structured = degraded_payload(result.text, self.config.mode)
        if on_delta and result.text:
            on_delta(result.text)
        return result

    def _handle_interviewer_question(
        self,
        interviewer_input: str,
        on_delta: Callable[[str], None] | None = None,
    ) -> LoopResult:
        if self.state.completed:
            return LoopResult(self.state, "Interview already completed.", advanced=False)
        if not self.state.turns:
            self.start()

        input_check = self.harness.guardrails.check_candidate_input(interviewer_input)
        if input_check.blocked:
            message = self.harness.guardrails.blocked_message(input_check.findings)
            return LoopResult(
                self.state,
                message,
                advanced=False,
                guardrail_findings=input_check.findings,
            )

        cleaned_input = input_check.text
        if not cleaned_input.strip():
            return LoopResult(self.state, "请先输入面试问题。", advanced=False)

        self.state.add_interviewer_message(InterviewStage.QUESTIONING, cleaned_input)
        if on_delta:
            harness_result = self.harness.generate_result_stream(
                InterviewStage.QUESTIONING,
                self.state,
                on_delta,
            )
        else:
            harness_result = self.harness.generate_result(InterviewStage.QUESTIONING, self.state)
        message = harness_result.text
        self.state.stage = InterviewStage.QUESTIONING
        self.state.add_candidate_message(message)

        answered_turns = sum(1 for turn in self.state.turns if turn.candidate)
        if answered_turns >= self.config.max_turns:
            evaluation_result = self._run_evaluation(on_delta=on_delta)
            self.state.stage = InterviewStage.EVALUATION
            self.state.add_interviewer_message(InterviewStage.EVALUATION, "本轮面试复盘")
            self.state.turns[-1].candidate = evaluation_result.text
            self.state.completed = True
            return LoopResult(
                state=self.state,
                message=evaluation_result.text,
                guardrail_findings=input_check.findings + evaluation_result.findings,
                fallback_used=evaluation_result.fallback_used,
                usage=evaluation_result.usage,
                evaluation=evaluation_result.structured,
            )

        return LoopResult(
            state=self.state,
            message=message,
            guardrail_findings=input_check.findings + harness_result.findings,
            fallback_used=harness_result.fallback_used,
            usage=harness_result.usage,
        )

    def _classify_input(self, candidate_input: str) -> InputKind:
        normalized = candidate_input.strip().lower()
        if not normalized:
            return InputKind.TOO_SHORT

        question_markers = ("?", "？", "什么是", "是什么意思", "怎么理解", "能解释", "可以解释")
        if any(marker in normalized for marker in question_markers):
            return InputKind.CLARIFYING_QUESTION

        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", normalized))
        words = [part for part in normalized.replace("，", " ").replace("。", " ").split() if part]
        if len(normalized) < 12 or (chinese_chars < 18 and len(words) <= 2):
            return InputKind.TOO_SHORT
        return InputKind.ANSWER

    def _next_stage(self, assessment: AnswerAssessment) -> InterviewStage:
        answered_turns = sum(1 for turn in self.state.turns if turn.candidate)
        if answered_turns >= self.config.max_turns:
            return InterviewStage.EVALUATION

        if self.state.stage in {InterviewStage.INTRO, InterviewStage.QUESTIONING}:
            self.state.focus_followup_count = 0
            return InterviewStage.FOLLOW_UP

        self.state.focus_followup_count += 1
        if (
            assessment.needs_more_depth
            and self.state.focus_followup_count < self.config.max_followups_per_focus
        ):
            return InterviewStage.FOLLOW_UP

        self.state.focus_followup_count = 0
        self.state.current_focus_index += 1
        if self.state.current_focus_index >= len(self.config.focus_areas):
            return InterviewStage.EVALUATION
        return InterviewStage.QUESTIONING

    def _assess_answer(self, answer: str) -> AnswerAssessment:
        normalized = answer.strip()
        score = 0
        reasons: list[str] = []

        if len(normalized) >= 80:
            score += 1
            reasons.append("回答有一定展开")
        if _has_metric(normalized):
            score += 1
            reasons.append("包含指标或量化结果")
        if _has_ownership(normalized):
            score += 1
            reasons.append("说明了本人职责")
        if _has_technical_depth(normalized):
            score += 1
            reasons.append("包含技术细节")
        if _has_tradeoff(normalized):
            score += 1
            reasons.append("体现工程取舍")
        if _has_production_signal(normalized):
            score += 1
            reasons.append("覆盖上线或治理")
        if self._has_industry_signal(normalized):
            score += 1
            reasons.append("贴合行业指标或风险约束")

        needs_more_depth = score < 4
        reason = "、".join(reasons) if reasons else "缺少项目证据、指标和技术取舍"
        return AnswerAssessment(score=score, needs_more_depth=needs_more_depth, reason=reason)

    def _has_industry_signal(self, text: str) -> bool:
        profile = get_industry_profile(self.config.industry)
        lowered = text.lower()
        markers = [
            *profile.scenario_keywords,
            *profile.production_signals,
            *profile.risk_controls,
        ]
        return any(marker.lower() in lowered for marker in markers)


class _LangGraphState(TypedDict, total=False):
    candidate_input: str
    cleaned_input: str
    input_kind: str
    blocked: bool
    terminal: bool
    route: str
    active_stage: str
    next_stage: str
    assessment_score: int
    findings: list[dict[str, str]]
    fallback_used: bool
    completed: bool
    message_length: int


class _LangGraphLoopExecutor:
    """LangGraph orchestration for the interview turn lifecycle."""

    graph_version = "interview-turn-v1"

    def __init__(self, loop: AgentLoop) -> None:
        self.loop = loop
        self.graph_app: Any = None
        self.checkpointer: Any = None
        self._active_on_delta: Callable[[str], None] | None = None
        self._last_result: LoopResult | None = None
        self._input_findings: list[GuardrailFinding] = []
        self._events: list[GraphNodeEvent] = []

    def configure(self, graph_app: Any, *, checkpointer: Any = None) -> None:
        self.graph_app = graph_app
        self.checkpointer = checkpointer

    def run(
        self,
        candidate_input: str,
        on_delta: Callable[[str], None] | None = None,
    ) -> LoopResult:
        self._active_on_delta = on_delta
        self._last_result = None
        self._input_findings = []
        self._events = []
        graph_config = {"configurable": {"thread_id": self.loop.thread_id}}
        try:
            self.graph_app.invoke({"candidate_input": candidate_input}, config=graph_config)
        except Exception as exc:
            self._events.append(
                GraphNodeEvent(
                    node="graph",
                    status="failed",
                    duration_ms=0,
                    error=str(exc),
                    metadata={"fallback": "explicit_loop"},
                )
            )
            result = self.loop._handle_input_explicit(candidate_input, on_delta=on_delta)
            result.fallback_used = True
            result.orchestration = self._metadata(fallback_reason=str(exc))
            return result
        finally:
            self._active_on_delta = None

        result = self._last_result
        if result is not None:
            result.orchestration = self._metadata()
            return result

        result = self.loop._handle_input_explicit(candidate_input, on_delta=on_delta)
        result.fallback_used = True
        result.orchestration = self._metadata(fallback_reason="graph returned without LoopResult")
        return result

    def status(self) -> dict[str, Any]:
        return {
            "engine": "langgraph",
            "langgraph_enabled": True,
            "graph_version": self.graph_version,
            "checkpoint": self.checkpointer is not None,
            "thread_id": self.loop.thread_id,
        }

    def record(
        self,
        node: str,
        *,
        status: str,
        started_at: float,
        metadata: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self._events.append(
            GraphNodeEvent(
                node=node,
                status=status,
                duration_ms=(perf_counter() - started_at) * 1000,
                metadata=metadata or {},
                error=error,
            )
        )

    def set_result(self, result: LoopResult) -> None:
        self._last_result = result

    def _metadata(self, *, fallback_reason: str | None = None) -> dict[str, Any]:
        payload = self.status()
        payload["events"] = [event.to_dict() for event in self._events]
        if fallback_reason:
            payload["fallback_reason"] = fallback_reason
        return payload


def _build_langgraph_executor(loop: AgentLoop) -> _LangGraphLoopExecutor | None:
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return None
    executor = _LangGraphLoopExecutor(loop)

    def route_mode(graph_state: _LangGraphState) -> _LangGraphState:
        started_at = perf_counter()
        if loop.config.mode == InterviewMode.CANDIDATE:
            result = loop._handle_interviewer_question(
                graph_state["candidate_input"],
                on_delta=executor._active_on_delta,
            )
            executor.set_result(result)
            executor.record(
                "route_mode",
                status="succeeded",
                started_at=started_at,
                metadata={"route": "candidate_mode", "stage": result.state.stage.value},
            )
            return {"terminal": True, "route": "candidate_mode", "completed": result.state.completed}
        if loop.state.completed:
            result = LoopResult(loop.state, "Interview already completed.", advanced=False)
            executor.set_result(result)
            executor.record(
                "route_mode",
                status="succeeded",
                started_at=started_at,
                metadata={"route": "completed"},
            )
            return {"terminal": True, "route": "completed", "completed": True}
        executor.record(
            "route_mode",
            status="succeeded",
            started_at=started_at,
            metadata={"route": "interviewer_mode"},
        )
        return {"terminal": False, "route": "interviewer_mode", "active_stage": loop.state.stage.value}

    def ensure_started(_: _LangGraphState) -> _LangGraphState:
        started_at = perf_counter()
        generated_intro = False
        if not loop.state.turns:
            loop.start()
            generated_intro = True
        executor.record(
            "ensure_started",
            status="succeeded",
            started_at=started_at,
            metadata={"generated_intro": generated_intro, "turn_count": len(loop.state.turns)},
        )
        return {"active_stage": loop.state.stage.value}

    def guard_input(graph_state: _LangGraphState) -> _LangGraphState:
        started_at = perf_counter()
        input_check = loop.harness.guardrails.check_candidate_input(graph_state["candidate_input"])
        executor._input_findings = input_check.findings
        if input_check.blocked:
            result = LoopResult(
                loop.state,
                loop.harness.guardrails.blocked_message(input_check.findings),
                advanced=False,
                guardrail_findings=input_check.findings,
            )
            executor.set_result(result)
            executor.record(
                "guard_input",
                status="blocked",
                started_at=started_at,
                metadata={"finding_count": len(input_check.findings)},
            )
            return {
                "blocked": True,
                "terminal": True,
                "findings": _safe_guardrail_summary(input_check.findings),
            }
        cleaned_input = input_check.text
        input_kind = loop._classify_input(cleaned_input)
        executor.record(
            "guard_input",
            status="succeeded",
            started_at=started_at,
            metadata={
                "input_kind": input_kind.value,
                "finding_count": len(input_check.findings),
                "input_chars": len(cleaned_input),
            },
        )
        return {
            "cleaned_input": cleaned_input,
            "input_kind": input_kind.value,
            "blocked": False,
            "findings": _safe_guardrail_summary(input_check.findings),
        }

    def answer_clarifying_question(graph_state: _LangGraphState) -> _LangGraphState:
        started_at = perf_counter()
        cleaned_input = graph_state["cleaned_input"]
        if executor._active_on_delta:
            harness_result = loop.harness.respond_to_candidate_question_result_stream(
                cleaned_input,
                loop.state,
                executor._active_on_delta,
            )
        else:
            harness_result = loop.harness.respond_to_candidate_question_result(
                cleaned_input,
                loop.state,
            )
        result = LoopResult(
            loop.state,
            harness_result.text,
            advanced=False,
            guardrail_findings=executor._input_findings + harness_result.findings,
            fallback_used=harness_result.fallback_used,
            usage=harness_result.usage,
        )
        executor.set_result(result)
        executor.record(
            "answer_clarifying_question",
            status="succeeded",
            started_at=started_at,
            metadata={
                "fallback_used": harness_result.fallback_used,
                "message_length": len(harness_result.text),
            },
        )
        return {
            "terminal": True,
            "fallback_used": harness_result.fallback_used,
            "message_length": len(harness_result.text),
        }

    def ask_for_detail(graph_state: _LangGraphState) -> _LangGraphState:
        started_at = perf_counter()
        active_question = loop.state.turns[-1].interviewer
        message = (
            "我先不把这句计入面试回答。请展开一点，最好说明你的设计、取舍和失败处理。\n\n"
            f"当前问题：{active_question}"
        )
        result = LoopResult(
            loop.state,
            message,
            advanced=False,
            guardrail_findings=executor._input_findings,
        )
        executor.set_result(result)
        executor.record(
            "ask_for_detail",
            status="succeeded",
            started_at=started_at,
            metadata={"message_length": len(message)},
        )
        return {"terminal": True, "message_length": len(message)}

    def assess_answer(graph_state: _LangGraphState) -> _LangGraphState:
        started_at = perf_counter()
        cleaned_input = graph_state["cleaned_input"]
        loop.state.add_candidate_message(cleaned_input)
        assessment = loop._assess_answer(cleaned_input)
        loop.state.last_answer_assessment = (
            f"回答质量信号：{assessment.score}/6；{assessment.reason}；"
            f"{'建议继续深挖当前方向' if assessment.needs_more_depth else '可以在给出阶段性判断后切换方向'}。"
        )
        next_stage = loop._next_stage(assessment)
        executor.record(
            "assess_answer",
            status="succeeded",
            started_at=started_at,
            metadata={
                "score": assessment.score,
                "needs_more_depth": assessment.needs_more_depth,
                "next_stage": next_stage.value,
            },
        )
        return {"assessment_score": assessment.score, "next_stage": next_stage.value}

    def generate_next_turn(graph_state: _LangGraphState) -> _LangGraphState:
        started_at = perf_counter()
        next_stage = InterviewStage(graph_state["next_stage"])
        if next_stage == InterviewStage.EVALUATION:
            harness_result = loop._run_evaluation(on_delta=executor._active_on_delta)
        elif executor._active_on_delta:
            harness_result = loop.harness.generate_result_stream(
                next_stage,
                loop.state,
                executor._active_on_delta,
            )
        else:
            harness_result = loop.harness.generate_result(next_stage, loop.state)
        message = harness_result.text
        loop.state.stage = next_stage
        loop.state.add_interviewer_message(next_stage, message)
        if next_stage == InterviewStage.EVALUATION:
            loop.state.completed = True
        result = LoopResult(
            state=loop.state,
            message=message,
            guardrail_findings=executor._input_findings + harness_result.findings,
            fallback_used=harness_result.fallback_used,
            usage=harness_result.usage,
            evaluation=harness_result.structured,
        )
        executor.set_result(result)
        executor.record(
            "generate_next_turn",
            status="succeeded",
            started_at=started_at,
            metadata={
                "stage": next_stage.value,
                "completed": loop.state.completed,
                "fallback_used": harness_result.fallback_used,
                "message_length": len(message),
            },
        )
        return {
            "terminal": True,
            "completed": loop.state.completed,
            "fallback_used": harness_result.fallback_used,
            "message_length": len(message),
        }

    def after_mode(graph_state: _LangGraphState) -> str:
        return "done" if graph_state.get("terminal") else "ensure_started"

    def after_guardrails(graph_state: _LangGraphState) -> str:
        if graph_state.get("terminal"):
            return "done"
        input_kind = graph_state.get("input_kind")
        if input_kind == InputKind.CLARIFYING_QUESTION.value:
            return "clarify"
        if input_kind == InputKind.TOO_SHORT.value:
            return "too_short"
        return "answer"

    graph = StateGraph(_LangGraphState)
    graph.add_node("route_mode", route_mode)
    graph.add_node("ensure_started", ensure_started)
    graph.add_node("guard_input", guard_input)
    graph.add_node("clarify", answer_clarifying_question)
    graph.add_node("too_short", ask_for_detail)
    graph.add_node("assess_answer", assess_answer)
    graph.add_node("generate_next_turn", generate_next_turn)
    graph.set_entry_point("route_mode")
    graph.add_conditional_edges(
        "route_mode",
        after_mode,
        {"done": END, "ensure_started": "ensure_started"},
    )
    graph.add_edge("ensure_started", "guard_input")
    graph.add_conditional_edges(
        "guard_input",
        after_guardrails,
        {"done": END, "clarify": "clarify", "too_short": "too_short", "answer": "assess_answer"},
    )
    graph.add_edge("clarify", END)
    graph.add_edge("too_short", END)
    graph.add_edge("assess_answer", "generate_next_turn")
    graph.add_edge("generate_next_turn", END)
    checkpointer = _create_langgraph_checkpointer()
    compile_kwargs = {"checkpointer": checkpointer} if checkpointer is not None else {}
    executor.configure(graph.compile(**compile_kwargs), checkpointer=checkpointer)
    return executor


def _create_langgraph_checkpointer() -> Any | None:
    try:
        from langgraph.checkpoint.memory import MemorySaver
    except ImportError:
        try:
            from langgraph.checkpoint.memory import InMemorySaver
        except ImportError:
            return None
        return InMemorySaver()
    return MemorySaver()


def _safe_guardrail_summary(findings: list[GuardrailFinding]) -> list[dict[str, str]]:
    return [
        {
            "code": finding.code,
            "message": finding.message,
            "action": finding.action.value,
        }
        for finding in findings
    ]


def _has_metric(text: str) -> bool:
    metric_patterns = (
        r"\d+(\.\d+)?\s*(%|ms|s|秒|分钟|qps|tps|w|万|k|kb|mb|gb)",
        r"(p50|p90|p95|p99|top\s*k|topk|召回率|准确率|通过率|命中率|延迟|吞吐|成本)",
    )
    lowered = text.lower()
    return any(re.search(pattern, lowered, flags=re.I) for pattern in metric_patterns)


def _has_ownership(text: str) -> bool:
    markers = ("我负责", "我主导", "我设计", "我实现", "我搭建", "我推进", "我参与", "本人负责")
    return any(marker in text for marker in markers)


def _has_technical_depth(text: str) -> bool:
    lowered = text.lower()
    markers = (
        "rag",
        "agent",
        "langchain",
        "langgraph",
        "llm",
        "embedding",
        "rerank",
        "bm25",
        "chunk",
        "qdrant",
        "向量",
        "检索",
        "重排",
        "索引",
        "工具调用",
        "链式调用",
        "状态机",
        "状态图",
        "节点",
        "检查点",
        "prompt",
        "评测",
        "缓存",
        "降级",
        "重试",
    )
    return any(marker in lowered for marker in markers)


def _has_tradeoff(text: str) -> bool:
    markers = ("取舍", "权衡", "对比", "瓶颈", "约束", "风险", "代价", "成本", "因为", "所以")
    return any(marker in text for marker in markers)


def _has_production_signal(text: str) -> bool:
    markers = (
        "上线",
        "灰度",
        "回滚",
        "监控",
        "告警",
        "日志",
        "观测",
        "安全",
        "权限",
        "压测",
        "评估",
        "评测",
        "ab",
        "a/b",
        "故障",
        "复盘",
    )
    lowered = text.lower()
    return any(marker in lowered for marker in markers)
