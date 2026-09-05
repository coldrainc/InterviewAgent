"""主观题 LLM 评分器：要求模型只输出 JSON 评分对象。

输出格式：{"score": 0-100, "feedback": "中文讲评", "suggestions": ["改进点", ...]}
模型异常 / 输出非法时由调用方降级到关键词判分。
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一名严谨的公考/技术面试刷题阅卷官。根据题目、参考答案与用户作答评分，"
    "只输出一个 JSON 对象，不要使用代码块，不要输出多余文字。格式：\n"
    '{"score": 0到100的整数, "feedback": "一句话中文讲评", '
    '"suggestions": ["改进建议1", "改进建议2", "改进建议3"]}'
)


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
        reference = str(question.get("answer") or "").strip() or "（无标准答案，按要点完整性评分）"
        explanation = str(question.get("answer_detail") or question.get("explanation") or "").strip()
        subject = str(question.get("subject") or "").strip()
        parts = [
            f"题型：{question.get('question_type') or '主观题'}",
            f"科目/方向：{subject or '综合'}",
            f"题目：{question.get('prompt') or ''}",
            f"参考答案：{reference}",
        ]
        if explanation:
            parts.append(f"参考解析：{explanation}")
        parts.append(f"用户作答：{answer}")
        parts.append("请按要点覆盖率、逻辑结构、术语准确性给出 0-100 分与中文讲评。")
        return "\n\n".join(parts)

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
            logger.warning("subjective grader returned non-json content: %s", raw[:200])
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
