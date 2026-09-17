from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from interview_agent.core.config import InterviewConfig, InterviewMode, InterviewStage
from interview_agent.core.evaluation import (
    degraded_payload,
    evaluation_prompt_instruction,
    parse_evaluation_json,
    render_evaluation_text,
)
from interview_agent.core.guardrails import HarnessGuardrails
from interview_agent.core.harness_result import HarnessResult
from interview_agent.core.prompt_policy import (
    candidate_system_prompt,
    interview_stage_instruction,
    interviewer_system_prompt,
)
from interview_agent.domain.billing import TokenUsage
from interview_agent.rag.knowledge_base import MarkdownKnowledgeBase
from interview_agent.core.state import InterviewState
from interview_agent.infrastructure.web_search import WebSearchClient


class InterviewHarness(Protocol):
    guardrails: HarnessGuardrails

    def generate(self, stage: InterviewStage, state: InterviewState) -> str:
        ...

    def generate_result(self, stage: InterviewStage, state: InterviewState) -> HarnessResult:
        ...

    def generate_evaluation_result(self, state: InterviewState) -> HarnessResult:
        ...

    def generate_result_stream(
        self,
        stage: InterviewStage,
        state: InterviewState,
        on_delta: Callable[[str], None],
    ) -> HarnessResult:
        ...

    def respond_to_candidate_question(self, question: str, state: InterviewState) -> str:
        ...

    def respond_to_candidate_question_result(
        self, question: str, state: InterviewState
    ) -> HarnessResult:
        ...

    def respond_to_candidate_question_result_stream(
        self,
        question: str,
        state: InterviewState,
        on_delta: Callable[[str], None],
    ) -> HarnessResult:
        ...


class BaseInterviewHarness(ABC):
    def __init__(
        self,
        config: InterviewConfig,
        guardrails: HarnessGuardrails | None = None,
    ) -> None:
        self.config = config
        self.guardrails = guardrails or HarnessGuardrails()

    @abstractmethod
    def generate_result(self, stage: InterviewStage, state: InterviewState) -> HarnessResult:
        raise NotImplementedError

    def generate(self, stage: InterviewStage, state: InterviewState) -> str:
        return self.generate_result(stage, state).text

    def generate_evaluation_result(self, state: InterviewState) -> HarnessResult:
        """默认实现：用普通 EVALUATION 文本降级为结构化报告（total_score=None）。"""
        result = self.generate_result(InterviewStage.EVALUATION, state)
        payload = degraded_payload(result.text, self.config.mode)
        result.structured = payload
        result.text = render_evaluation_text(payload, self.config.mode)
        return result

    def generate_result_stream(
        self,
        stage: InterviewStage,
        state: InterviewState,
        on_delta: Callable[[str], None],
    ) -> HarnessResult:
        result = self.generate_result(stage, state)
        if result.text:
            on_delta(result.text)
        return result

    @abstractmethod
    def respond_to_candidate_question_result(
        self, question: str, state: InterviewState
    ) -> HarnessResult:
        raise NotImplementedError

    def respond_to_candidate_question(self, question: str, state: InterviewState) -> str:
        return self.respond_to_candidate_question_result(question, state).text

    def respond_to_candidate_question_result_stream(
        self,
        question: str,
        state: InterviewState,
        on_delta: Callable[[str], None],
    ) -> HarnessResult:
        result = self.respond_to_candidate_question_result(question, state)
        if result.text:
            on_delta(result.text)
        return result


class LangChainInterviewHarness(BaseInterviewHarness):
    """LangChain-backed harness that turns interview state into model calls."""

    def __init__(
        self,
        config: InterviewConfig,
        llm: BaseChatModel | None = None,
        knowledge_base: MarkdownKnowledgeBase | None = None,
        web_search: WebSearchClient | None = None,
        model: str = "gpt-5.5",
        provider: str = "openai",
        base_url: str | None = None,
        api_key: str | None = None,
        wire_api: str | None = None,
        temperature: float = 0.4,
        request_timeout: float | None = None,
        max_retries: int | None = None,
        thinking_enabled: bool | None = None,
        reasoning_effort: str | None = None,
        guardrails: HarnessGuardrails | None = None,
    ) -> None:
        super().__init__(config, guardrails=guardrails)
        llm_kwargs = {"model": model, "temperature": temperature}
        if base_url:
            llm_kwargs["base_url"] = base_url
        if api_key:
            llm_kwargs["api_key"] = api_key
        if request_timeout is not None:
            llm_kwargs["timeout"] = request_timeout
        if max_retries is not None:
            llm_kwargs["max_retries"] = max_retries
        if wire_api == "responses":
            llm_kwargs["use_responses_api"] = True
        if provider.lower() == "deepseek" and thinking_enabled is not None:
            extra_body: dict[str, Any] = {
                "thinking": {"type": "enabled" if thinking_enabled else "disabled"}
            }
            if thinking_enabled and reasoning_effort:
                extra_body["reasoning_effort"] = reasoning_effort
            llm_kwargs["extra_body"] = extra_body
        self.llm = llm or _create_chat_model(provider=provider, **llm_kwargs)
        self.knowledge_base = knowledge_base
        self.web_search = web_search

    def generate_result(self, stage: InterviewStage, state: InterviewState) -> HarnessResult:
        messages = [
            SystemMessage(content=self._system_prompt()),
            HumanMessage(content=self._stage_prompt(stage, state)),
        ]
        return self._safe_invoke(messages, fallback=self._fallback_message(stage, state))

    def generate_result_stream(
        self,
        stage: InterviewStage,
        state: InterviewState,
        on_delta: Callable[[str], None],
    ) -> HarnessResult:
        messages = [
            SystemMessage(content=self._system_prompt()),
            HumanMessage(content=self._stage_prompt(stage, state)),
        ]
        return self._safe_stream(messages, fallback=self._fallback_message(stage, state), on_delta=on_delta)

    def respond_to_candidate_question_result(
        self, question: str, state: InterviewState
    ) -> HarnessResult:
        messages, fallback = self._candidate_question_messages(question, state)
        return self._safe_invoke(messages, fallback=fallback)

    def generate_evaluation_result(self, state: InterviewState) -> HarnessResult:
        """EVALUATION 阶段：要求 LLM 输出结构化 JSON 评分卡，解析失败则降级为文本报告。"""
        messages = [
            SystemMessage(content=self._system_prompt()),
            HumanMessage(
                content=self._stage_prompt(
                    InterviewStage.EVALUATION,
                    state,
                    instruction_override=evaluation_prompt_instruction(self.config.mode),
                )
            ),
        ]
        try:
            response = self.llm.invoke(messages)
            raw_text = self._content_to_text(response.content)
            payload = parse_evaluation_json(raw_text, self.config.mode)
            rendered = render_evaluation_text(payload, self.config.mode)
            checked = self.guardrails.check_model_output(rendered)
            return HarnessResult(
                text=checked.text,
                findings=checked.findings,
                usage=_extract_token_usage(response),
                fallback_used=bool(payload.get("degraded")),
                structured=payload,
            )
        except Exception:
            fallback_text = self._fallback_message(InterviewStage.EVALUATION, state)
            payload = degraded_payload(fallback_text, self.config.mode)
            rendered = render_evaluation_text(payload, self.config.mode)
            checked = self.guardrails.check_model_output(rendered)
            return HarnessResult(
                text=checked.text,
                findings=checked.findings,
                fallback_used=True,
                structured=payload,
            )

    def respond_to_candidate_question_result_stream(
        self,
        question: str,
        state: InterviewState,
        on_delta: Callable[[str], None],
    ) -> HarnessResult:
        messages, fallback = self._candidate_question_messages(question, state)
        return self._safe_stream(messages, fallback=fallback, on_delta=on_delta)

    def _candidate_question_messages(
        self,
        question: str,
        state: InterviewState,
    ) -> tuple[list[Any], str]:
        focus = self._current_focus(state)
        query = self._context_query(state.stage, state, focus, extra=question)
        knowledge_context = self._knowledge_context(query)
        web_context = self._web_context(query)
        messages = [
            SystemMessage(content=self._system_prompt()),
            HumanMessage(
                content=f"""候选人在面试过程中提出了澄清问题或知识性问题。

当前面试题：
{state.turns[-1].interviewer if state.turns else "暂无当前题目。"}

候选人的问题：
{question}

知识库上下文：
{knowledge_context}

联网搜索上下文：
{web_context}

指令：
用中文回答候选人的问题，并把回答扩展成面试答题辅导：
1. 先用 2-4 句话解释核心概念。
2. 给出一个“面试中可以这样答”的结构化话术，包含定义、架构/流程、工程取舍、风险与优化。
3. 如果知识库上下文里有相关要点，提炼 2-4 个高分关键词。
4. 最后用一句话把候选人带回当前面试题。
不要评价候选人，也不要推进到新的面试主题。"""
            ),
        ]
        active_question = state.turns[-1].interviewer if state.turns else "当前问题"
        fallback = (
            f"简单说，{question} 是一个澄清问题。面试里建议先给定义，再讲流程、取舍和风险。"
            f"请你继续回答当前题目：{active_question}"
        )
        return messages, fallback

    def _system_prompt(self) -> str:
        context = self.config.to_prompt_context()
        if self.config.mode == InterviewMode.CANDIDATE:
            return self._candidate_system_prompt(context)
        return self._interviewer_system_prompt(context)

    def _interviewer_system_prompt(self, context: dict[str, Any]) -> str:
        return interviewer_system_prompt(context)

    def _candidate_system_prompt(self, context: dict[str, Any]) -> str:
        return candidate_system_prompt(context)

    def _stage_prompt(
        self,
        stage: InterviewStage,
        state: InterviewState,
        instruction_override: str | None = None,
    ) -> str:
        transcript = state.transcript() or "No prior turns."
        focus = self._current_focus(state)
        query = self._context_query(stage, state, focus)
        if self._should_retrieve_context(stage, state):
            knowledge_context = self._knowledge_context(query)
            web_context = self._web_context(query)
        else:
            knowledge_context = "开场题阶段暂不检索知识库。"
            web_context = "开场题阶段暂不联网搜索。"
        instruction = interview_stage_instruction(
            stage.value,
            candidate_mode=self.config.mode == InterviewMode.CANDIDATE,
            focus=focus,
        )

        if instruction_override:
            instruction = instruction_override

        return f"""当前阶段：{stage.value}
当前模式：{self.config.to_prompt_context()["mode_label"]}
当前行业：{self.config.to_prompt_context()["industry_label"]}
当前重点：{focus}
当前方向连续追问次数：{state.focus_followup_count}/{self.config.max_followups_per_focus}
上一轮回答质量信号：
{state.last_answer_assessment or "暂无。"}

<reference_data>
面试目标：
{self.config.candidate.interview_goal}

候选人简历摘要：
{self.config.candidate.resume_summary}

候选人完整简历：
{self.config.candidate.resume_text or "暂未提供完整简历。"}

候选人做过的事情：
{self.config.candidate.project_experience or "暂未提供做过的事情。"}

行业画像：
{self.config.to_prompt_context()["industry_profile"]}

行业验证信号：
{self.config.to_prompt_context()["industry_signals"]}

行业风险约束：
{self.config.to_prompt_context()["industry_risks"]}

面试重点：
{self.config.to_prompt_context()["focus_areas"]}

内部评分参考（仅用于判断，不向用户复述）：
{self.config.to_prompt_context()["rubric"]}

面试记录：
{transcript}

知识库上下文：
{knowledge_context}

联网搜索上下文：
{web_context}
</reference_data>

指令：
{instruction}"""

    def _current_focus(self, state: InterviewState) -> str:
        if not self.config.focus_areas:
            return "general engineering judgment"
        index = min(state.current_focus_index, len(self.config.focus_areas) - 1)
        return self.config.focus_areas[index]

    def _knowledge_context(self, query: str) -> str:
        if self.knowledge_base is None:
            return "未配置知识库。"

        return self.knowledge_base.context_for(query)

    def _should_retrieve_context(self, stage: InterviewStage, state: InterviewState) -> bool:
        return stage != InterviewStage.INTRO or any(turn.candidate for turn in state.turns)

    def _web_context(self, query: str) -> str:
        if self.web_search is None:
            return "未启用联网搜索。"
        try:
            return self.web_search.context_for(query)
        except Exception:
            return "联网搜索暂时不可用。"

    def _context_query(
        self,
        stage: InterviewStage,
        state: InterviewState,
        focus: str,
        extra: str = "",
    ) -> str:
        last_answer = ""
        if state.turns and state.turns[-1].candidate:
            last_answer = state.turns[-1].candidate
        profile = self.config.candidate
        return (
            f"{stage.value} {focus} {profile.target_role} {profile.resume_summary} "
            f"{profile.project_experience} {last_answer} {extra}"
        ).strip()

    def _content_to_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            if parts:
                return "\n".join(parts).strip()
        return str(content).strip()

    def _content_to_delta(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            if parts:
                return "".join(parts)
        return str(content) if content is not None else ""

    def _safe_invoke(self, messages: list[Any], fallback: str) -> HarnessResult:
        try:
            response = self.llm.invoke(messages)
            raw_text = self._content_to_text(response.content)
            checked = self.guardrails.check_model_output(raw_text)
            return HarnessResult(
                text=checked.text,
                findings=checked.findings,
                usage=_extract_token_usage(response),
            )
        except Exception:
            checked = self.guardrails.check_model_output(fallback)
            return HarnessResult(text=checked.text, findings=checked.findings, fallback_used=True)

    def _safe_stream(
        self,
        messages: list[Any],
        *,
        fallback: str,
        on_delta: Callable[[str], None],
    ) -> HarnessResult:
        chunks: list[Any] = []
        parts: list[str] = []
        try:
            for chunk in self.llm.stream(messages):
                chunks.append(chunk)
                delta = self._content_to_delta(getattr(chunk, "content", ""))
                if delta:
                    parts.append(delta)
                    on_delta(delta)
            raw_text = "".join(parts)
            if not raw_text.strip():
                raise RuntimeError("stream returned empty content")
            checked = self.guardrails.check_model_output(raw_text)
            return HarnessResult(
                text=checked.text,
                findings=checked.findings,
                usage=_extract_stream_token_usage(chunks),
            )
        except Exception:
            checked = self.guardrails.check_model_output(fallback)
            if checked.text:
                on_delta(checked.text)
            return HarnessResult(text=checked.text, findings=checked.findings, fallback_used=True)

    def _fallback_message(self, stage: InterviewStage, state: InterviewState) -> str:
        focus = self._current_focus(state)
        if self.config.mode == InterviewMode.CANDIDATE:
            if stage == InterviewStage.INTRO:
                label = self.config.to_prompt_context()["industry_label"]
                return f"已进入被面试候选人模式。请直接问我面试题，我会按{label} AI 工程候选人的口吻作答。"
            return "我会先给结论，再结合项目背景、本人职责、技术方案、指标和复盘来回答这个问题。"
        if stage == InterviewStage.EVALUATION:
            return "当前模型暂时不可用。我会先基于已有记录给出保守结论：需要更多有效回答后再做完整评价。"
        if stage == InterviewStage.FOLLOW_UP:
            return "阶段性判断：你刚才的回答还需要更多项目证据。我想进一步追问：这个方案里你本人负责的关键决策是什么？你用什么指标证明它有效？"
        return f"我们继续围绕{focus}。请你结合简历里的真实项目，说明你的设计思路、关键取舍、AI 工程难点和失败处理。"


def _create_chat_model(provider: str, **kwargs: Any) -> BaseChatModel:
    normalized = provider.lower()
    if normalized == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ModuleNotFoundError as exc:
            raise RuntimeError("使用 Anthropic 模型需要安装 langchain-anthropic。") from exc

        anthropic_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key not in {"base_url", "use_responses_api"} and value is not None
        }
        return ChatAnthropic(**anthropic_kwargs)
    return ChatOpenAI(**kwargs)


def _extract_token_usage(response: Any) -> TokenUsage | None:
    candidates: list[Any] = []
    for attr in ("usage_metadata", "response_metadata"):
        value = getattr(response, attr, None)
        if value:
            candidates.append(value)
    if isinstance(response, dict):
        candidates.append(response)

    for payload in candidates:
        usage = _usage_from_mapping(payload)
        if usage is not None:
            return usage
        if isinstance(payload, dict):
            nested = payload.get("token_usage") or payload.get("usage")
            usage = _usage_from_mapping(nested)
            if usage is not None:
                return usage
    return None


def _extract_stream_token_usage(chunks: list[Any]) -> TokenUsage | None:
    for chunk in reversed(chunks):
        usage = _extract_token_usage(chunk)
        if usage is not None:
            return usage
    return None


def _usage_from_mapping(payload: Any) -> TokenUsage | None:
    if not isinstance(payload, dict):
        return None
    input_tokens = (
        payload.get("input_tokens")
        or payload.get("prompt_tokens")
        or payload.get("prompt_token_count")
        or payload.get("cache_read_input_tokens")
        or 0
    )
    output_tokens = (
        payload.get("output_tokens")
        or payload.get("completion_tokens")
        or payload.get("candidates_token_count")
        or 0
    )
    try:
        usage = TokenUsage(input_tokens=int(input_tokens), output_tokens=int(output_tokens))
    except (TypeError, ValueError):
        return None
    return usage if usage.total_tokens > 0 else None


class ScriptedInterviewHarness(BaseInterviewHarness):
    """Deterministic harness for tests and offline demos."""

    def __init__(
        self,
        config: InterviewConfig,
        knowledge_base: MarkdownKnowledgeBase | None = None,
        guardrails: HarnessGuardrails | None = None,
    ) -> None:
        super().__init__(config, guardrails=guardrails)
        self.knowledge_base = knowledge_base

    def generate_result(self, stage: InterviewStage, state: InterviewState) -> HarnessResult:
        focus = self.config.focus_areas[
            min(state.current_focus_index, len(self.config.focus_areas) - 1)
        ]
        if self.config.mode == InterviewMode.CANDIDATE:
            label = self.config.to_prompt_context()["industry_label"]
            if stage == InterviewStage.INTRO:
                text = f"已进入被面试候选人模式。请直接问我面试题，我会以{label} AI 工程候选人的身份回答。"
            elif stage == InterviewStage.EVALUATION:
                text = "本轮回答可以围绕项目背景、个人职责、技术取舍、指标和复盘继续补充。"
            else:
                text = (
                    f"我的回答是：在{focus}这个方向，我会先说明业务背景和目标，"
                    f"再讲我负责的设计、关键取舍、上线验证和风险复盘，确保回答有项目证据和{label}生产环境细节。"
                )
            checked = self.guardrails.check_model_output(text)
            return HarnessResult(text=checked.text, findings=checked.findings)
        if stage == InterviewStage.INTRO:
            text = (
                f"{self.config.candidate.name}你好，我们会基于你的简历和做过的事情来面试。"
                f"先从{focus}开始：请讲一个你最有代表性的 AI 项目，说明背景、你的职责、架构、难点、指标和结果。"
            )
        elif stage == InterviewStage.QUESTIONING:
            text = f"围绕{focus}，如果做生产级设计，你会重点考虑哪些取舍？"
        elif stage == InterviewStage.FOLLOW_UP:
            text = "阶段性判断：你的回答有一定方向，但还需要项目证据。请继续说明这里最难的约束是什么？你如何验证自己的选择是对的？"
        elif stage == InterviewStage.EVALUATION:
            text = "评价：表达清晰，仍需更多真实项目指标和故障复盘证据。结论：建议谨慎通过。"
        else:
            text = "感谢你今天参加面试。"
        checked = self.guardrails.check_model_output(text)
        return HarnessResult(text=checked.text, findings=checked.findings)

    def generate_evaluation_result(self, state: InterviewState) -> HarnessResult:
        payload = self._scripted_evaluation_payload(state)
        text = render_evaluation_text(payload, self.config.mode)
        checked = self.guardrails.check_model_output(text)
        return HarnessResult(text=checked.text, findings=checked.findings, structured=payload)

    def _scripted_evaluation_payload(self, state: InterviewState) -> dict:
        from interview_agent.core.evaluation import (
            INTERVIEWER_DIMENSIONS,
            empty_payload,
        )

        if self.config.mode == InterviewMode.CANDIDATE:
            user_questions = [
                turn.interviewer
                for turn in state.turns
                if turn.stage == InterviewStage.QUESTIONING and turn.interviewer
            ]
            payload = empty_payload(InterviewMode.CANDIDATE)
            payload["verdict"] = "良好"
            payload["total_score"] = 78
            payload["dimension_scores"] = {
                "question_depth": 4,
                "coverage": 3,
                "differentiation": 4,
            }
            payload["per_question"] = [
                {
                    "question": question[:40],
                    "score": 4,
                    "comment": "问题聚焦项目细节，有一定区分度；可再追问量化指标。",
                }
                for question in user_questions
            ]
            payload["strength_tags"] = ["追问具体", "结合项目"]
            payload["weakness_tags"] = ["方向偏窄", "指标追问少"]
            payload["suggestions"] = [
                {
                    "title": "扩展考察方向",
                    "category": "interviewer_skill",
                    "detail": "除项目深挖外，增加系统设计、生产故障复盘和行为类问题。",
                }
            ]
            payload["summary"] = "脚本模拟评估：提问整体聚焦且有层次，建议扩大方向覆盖并加强指标口径追问。"
            return payload

        answered = [turn for turn in state.turns if turn.candidate]
        payload = empty_payload(InterviewMode.INTERVIEWER)
        payload["verdict"] = "谨慎通过"
        payload["total_score"] = 72
        payload["dimension_scores"] = {key: 3 for key in INTERVIEWER_DIMENSIONS}
        payload["dimension_scores"]["communication"] = 4
        payload["per_question"] = [
            {
                "question": turn.interviewer[:40],
                "score": 3,
                "comment": "回答有方向，但缺少量化指标与故障复盘证据。",
            }
            for turn in answered
        ]
        payload["evidence"] = [
            {"quote": (turn.candidate or "")[:60], "point": "候选人提供了项目事实与技术选型。"}
            for turn in answered[:2]
        ]
        payload["strength_tags"] = ["表达清晰", "项目真实"]
        payload["weakness_tags"] = ["指标不足", "复盘偏少"]
        payload["suggestions"] = [
            {"title": "补强 RAG 评测体系", "category": "rag", "detail": "练习召回率、命中率、答案相关性等离线评测集设计。"},
            {"title": "梳理 Agent 可观测性", "category": "agent", "detail": "总结一次 LangGraph 状态追踪与失败重试的生产实践。"},
            {"title": "准备系统设计故事", "category": "system_design", "detail": "用一个高并发场景讲清容量估算、降级与灰度。"},
        ]
        payload["summary"] = "脚本模拟评估：具备基础 AI 工程认知，建议补强量化指标、生产复盘与系统设计表达。"
        return payload

    def respond_to_candidate_question_result(
        self, question: str, state: InterviewState
    ) -> HarnessResult:
        active_question = state.turns[-1].interviewer if state.turns else "当前问题"
        text = (
            f"简短说明：你问的是澄清问题，我不会把它计入面试回答。"
            f"请继续回答当前问题：{active_question}"
        )
        checked = self.guardrails.check_model_output(text)
        return HarnessResult(text=checked.text, findings=checked.findings)
