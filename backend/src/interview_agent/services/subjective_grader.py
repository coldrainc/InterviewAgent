"""主观题 LLM 评分器：要求模型只输出 JSON 评分对象。

输出格式：{"score": 0-100, "feedback": "中文讲评", "suggestions": ["改进点", ...]}
模型异常 / 输出非法时由调用方降级到关键词判分。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from interview_agent.core.prompt_policy import (
    subjective_grader_system_prompt,
    subjective_grader_user_prompt,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = subjective_grader_system_prompt()


class LlmSubjectiveGrader:
    def __init__(self, llm: Any, model_id: str = "") -> None:
        self.llm = llm
        self.model_id = model_id

    async def __call__(self, question: dict[str, Any], answer: str) -> dict[str, Any] | None:
        from langchain_core.messages import HumanMessage, SystemMessage

        prompt = self._build_prompt(question, answer)
        response = self.llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        raw = getattr(response, "content", response)
        if not isinstance(raw, str):
            raw = str(raw)
        return self._parse(raw)

    @staticmethod
    def _build_prompt(question: dict[str, Any], answer: str) -> str:
        return subjective_grader_user_prompt(question, answer)

    @staticmethod
    def _parse(raw: str) -> dict[str, Any] | None:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            payload = json.loads(text[start : end + 1])
        except (json.JSONDecodeError, ValueError):
            logger.warning("subjective grader returned non-json content")
            return None
        if not isinstance(payload, dict):
            return None
        score = payload.get("score")
        try:
            score = int(score)
        except (TypeError, ValueError):
            return None
        score = max(0, min(100, score))
        feedback = str(payload.get("feedback") or "").strip()
        suggestions_raw = payload.get("suggestions") or []
        suggestions = [str(item).strip() for item in suggestions_raw if str(item).strip()]
        if not feedback:
            return None
        return {"score": score, "feedback": feedback, "suggestions": suggestions[:5]}
