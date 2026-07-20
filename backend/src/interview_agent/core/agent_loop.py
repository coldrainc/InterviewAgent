from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

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


@dataclass(frozen=True)
class AnswerAssessment:
    score: int
    needs_more_depth: bool
    reason: str


class InputKind(str, Enum):
    ANSWER = "answer"
    CLARIFYING_QUESTION = "clarifying_question"
    TOO_SHORT = "too_short"


class AgentLoop:
    """Explicit interview control loop around the LangChain harness."""

    def __init__(self, config: InterviewConfig, harness: "InterviewHarness") -> None:
        self.config = config
        self.harness = harness
        self.state = InterviewState()

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

    def handle_input(
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
        if on_delta:
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
        )

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
        "状态机",
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
