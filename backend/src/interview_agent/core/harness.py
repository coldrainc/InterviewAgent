from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from interview_agent.core.config import InterviewConfig, InterviewMode, InterviewStage
from interview_agent.core.guardrails import HarnessGuardrails
from interview_agent.core.harness_result import HarnessResult
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

    def respond_to_candidate_question(self, question: str, state: InterviewState) -> str:
        ...

    def respond_to_candidate_question_result(
        self, question: str, state: InterviewState
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

    @abstractmethod
    def respond_to_candidate_question_result(
        self, question: str, state: InterviewState
    ) -> HarnessResult:
        raise NotImplementedError

    def respond_to_candidate_question(self, question: str, state: InterviewState) -> str:
        return self.respond_to_candidate_question_result(question, state).text


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

    def respond_to_candidate_question_result(
        self, question: str, state: InterviewState
    ) -> HarnessResult:
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
        return self._safe_invoke(messages, fallback=fallback)

    def _system_prompt(self) -> str:
        context = self.config.to_prompt_context()
        if self.config.mode == InterviewMode.CANDIDATE:
            return self._candidate_system_prompt(context)
        return self._interviewer_system_prompt(context)

    def _interviewer_system_prompt(self, context: dict[str, Any]) -> str:
        return f"""你是一位严格但支持性的技术面试官。

候选人信息：
- 姓名：{context["candidate_name"]}
- 目标岗位：{context["target_role"]}
- 级别：{context["seniority"]}
- 行业：{context["industry_label"]}
- 简历摘要：{context["resume_summary"]}
- 面试目标：{context["interview_goal"]}

行业画像：
{context["industry_profile"]}

面试重点：{context["focus_areas"]}
推荐重点：{context["recommended_focus_areas"]}
每个重点的问题数：{context["questions_per_area"]}

评分标准：
{context["rubric"]}

规则：
- 默认全程使用中文提问和回答，除非候选人明确要求使用其他语言。
- 每次只问一个清晰的问题。
- 面试必须围绕候选人提供的简历和做过的事情展开，不要变成泛泛的八股问答。
- 如果面试目标中包含“面试官要求”，必须把它作为优先约束：题目、追问、判断和最终评价都要同时对齐候选人简历证据与面试官要求。
- 每轮都要结合候选人的回答做判断：如果回答具体、有指标、有取舍，继续深挖；如果回答空泛，要求补充细节；如果当前方向已足够，明确给出阶段性判断后切换到下一个重点。
- 你会收到 AgentLoop 的回答质量信号；它不是最终评分，但要作为追问、收束或切题的重要参考。
- 追问要结合 AI 相关知识库，重点覆盖 RAG、Agent、LLMOps、评测、上线、安全、观测和成本治理。
- 不要只问概念，要问候选人在项目中如何设计、如何排查、如何验证、如何上线、出了问题如何复盘。
- 结合行业画像选择追问角度：优先验证行业核心指标、真实约束、风险控制和生产化证据。
- 候选人回答缺少行业指标时，要要求补充指标口径，例如 {context["industry_signals"]}。
- 候选人回答缺少风险意识时，要追问风险治理，例如 {context["industry_risks"]}。
- 面试过程中不要向候选人透露评分标准。
- 最终评价要基于简历匹配度和面试证据，给出通过倾向、风险点和后续学习建议。"""

    def _candidate_system_prompt(self, context: dict[str, Any]) -> str:
        return f"""你正在扮演一位参加技术面试的候选人，而不是面试官。

候选人设定：
- 姓名：{context["candidate_name"]}
- 目标岗位：{context["target_role"]}
- 级别：{context["seniority"]}
- 行业：{context["industry_label"]}
- 简历摘要：{context["resume_summary"]}
- 项目经历：{context["project_experience"]}

行业画像：
{context["industry_profile"]}

回答目标：{context["interview_goal"]}
重点方向：{context["focus_areas"]}

规则：
- 默认全程使用中文回答。
- 你要直接回答用户提出的面试问题，不要反过来提问。
- 如果回答目标中包含“面试官要求”，必须优先贴合这些要求，同时用候选人简历摘要、项目经历和完整简历中的事实支撑回答。
- 回答要像真实候选人：先给结论，再讲项目背景、个人职责、设计方案、技术取舍、指标结果、失败复盘和后续优化。
- 回答要贴合当前行业画像，体现该行业真实业务约束、核心指标、风险治理和生产环境细节。
- 如果用户追问行业方案，要主动覆盖这些生产化信号：{context["industry_signals"]}。
- 如果用户追问安全或上线，要主动覆盖这些风险控制：{context["industry_risks"]}。
- 遇到 RAG、Agent、LLMOps、评测、上线、安全、观测相关问题时，优先结合简历和知识库上下文给出工程化回答。
- 不要编造过于夸张或无法自洽的数据；如果简历没有提供具体事实，可以使用保守、合理的表达。"""

    def _stage_prompt(self, stage: InterviewStage, state: InterviewState) -> str:
        transcript = state.transcript() or "No prior turns."
        focus = self._current_focus(state)
        query = self._context_query(stage, state, focus)
        if self._should_retrieve_context(stage, state):
            knowledge_context = self._knowledge_context(query)
            web_context = self._web_context(query)
        else:
            knowledge_context = "开场题阶段暂不检索知识库。"
            web_context = "开场题阶段暂不联网搜索。"
        if stage == InterviewStage.INTRO:
            if self.config.mode == InterviewMode.CANDIDATE:
                instruction = """用中文简短说明你已进入被面试候选人模式。
请提示用户可以直接向你提面试问题，例如项目深挖、RAG、Agent、系统设计或行为面试题。不要主动反问面试题。"""
            else:
                instruction = """用中文简短开场，然后基于候选人简历和做过的事情提出第一个问题。
优先选择简历中最能体现 AI 工程深度的项目切入，要求候选人讲清楚背景、本人职责、架构、难点、指标和结果。"""
        elif stage == InterviewStage.QUESTIONING:
            if self.config.mode == InterviewMode.CANDIDATE:
                instruction = """用户是面试官，刚才输入的是一道新的面试题或追问。
请以候选人身份完整回答，覆盖结论、项目事实、技术方案、工程取舍、指标和复盘。"""
            else:
                instruction = f"""用中文围绕这个重点提出下一道面试题：{focus}。
先用一句话说明为什么切换到这个方向，再问一个贴近候选人经历和 AI 行业要求的问题。"""
        elif stage == InterviewStage.FOLLOW_UP:
            if self.config.mode == InterviewMode.CANDIDATE:
                instruction = """用户是面试官，刚才输入的是追问。
请继续以候选人身份回答，直接补充更深层细节。回答要更具体，包含真实项目口吻、关键决策、风险处理和量化验证。"""
            else:
                instruction = """基于候选人的上一个回答，用中文输出：
1. 阶段性判断：用 1-2 句话指出回答中的有效证据和缺口。
2. 深挖追问：只问一个最关键的追问，优先追问真实项目细节、指标、失败排查、工程取舍或 AI 生产化能力。
如果回答明显空泛，要求候选人补充具体项目事实，不要直接换题。
如果同一方向已经连续追问多轮仍缺证据，要收束判断并准备切换方向。"""
        elif stage == InterviewStage.EVALUATION:
            if self.config.mode == InterviewMode.CANDIDATE:
                instruction = """如果用户要求总结，请以候选人身份总结本轮回答亮点和仍可补充的点。
如果用户没有要求总结，请继续回答用户最近的问题。"""
            else:
                instruction = """用中文根据简历、做过的事情和面试记录给出最终评价：
1. 通过倾向：通过 / 谨慎通过 / 暂不通过。
2. 关键证据：列出 3 条来自候选人回答的证据。
3. 风险点：列出 2-3 条需要继续验证或补强的点。
4. AI 工程能力判断：覆盖 RAG、Agent、评测、生产化、安全或观测中已验证的能力。
5. 后续建议：给出具体学习或项目补强方向。"""
        else:
            instruction = "用中文结束面试。"

        return f"""当前阶段：{stage.value}
当前模式：{self.config.to_prompt_context()["mode_label"]}
当前行业：{self.config.to_prompt_context()["industry_label"]}
当前重点：{focus}
当前方向连续追问次数：{state.focus_followup_count}/{self.config.max_followups_per_focus}
上一轮回答质量信号：
{state.last_answer_assessment or "暂无。"}

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

面试记录：
{transcript}

知识库上下文：
{knowledge_context}

联网搜索上下文：
{web_context}

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
