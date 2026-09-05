"""刷题判分：选择题规则判分 + 主观题关键词覆盖率判分。

纯函数、无副作用，供 v1/v2 接口与 LLM 降级路径复用。
"""

from __future__ import annotations

import re
from typing import Any


def normalize_choice_answer(value: str) -> str:
    cleaned = (value or "").strip().upper()
    match = re.search(r"[A-D]", cleaned)
    return match.group(0) if match else cleaned


def is_choice_question(question: dict[str, Any]) -> bool:
    choices = question.get("choices")
    return isinstance(choices, list) and bool(choices)


def grade_choice(answer: str, reference_answer: str) -> bool:
    return normalize_choice_answer(answer) == normalize_choice_answer(reference_answer)


def _practice_terms(text: str) -> set[str]:
    normalized = re.sub(r"[\s，。、；：！？,.;:!?（）()【】\[\]\"'`]+", " ", (text or "").lower())
    english = set(re.findall(r"[a-z0-9][a-z0-9_+\-]{1,}", normalized))
    chinese = set(re.findall(r"[\u4e00-\u9fff]{2,}", normalized))
    return english | chinese


def keyword_overlap(answer: str, reference: str) -> float:
    answer_terms = _practice_terms(answer)
    reference_terms = _practice_terms(reference)
    if not reference_terms:
        return 0.6
    return len(answer_terms & reference_terms) / len(reference_terms)


def _question_field(question: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = question.get(key)
        if value:
            return str(value)
    return default


def grade_question(question: dict[str, Any], user_answer: str) -> dict[str, Any]:
    """对一道题判分，返回 {correct, score, feedback, reference_answer, explanation, suggestions, graded_by}。

    correct 为 None 表示主观题无绝对对错（用 score 表达）。
    """
    answer = (user_answer or "").strip()
    reference_answer = _question_field(question, "answer").strip()
    explanation = _question_field(question, "answer_detail", "explanation").strip()
    choices = question.get("choices") if isinstance(question.get("choices"), list) else []

    if not answer:
        return {
            "correct": False if reference_answer else None,
            "score": 0,
            "feedback": "还没有作答，先写出你的判断或答题思路。",
            "reference_answer": reference_answer or "开放题",
            "explanation": explanation or "暂无解析。",
            "suggestions": ["先给结论", "补充关键依据", "对照解析复盘遗漏点"],
            "graded_by": "rule",
        }

    if is_choice_question(question) and reference_answer:
        correct = grade_choice(answer, reference_answer)
        return {
            "correct": correct,
            "score": 100 if correct else 0,
            "feedback": "回答正确。" if correct else "答案不一致，建议回看题干限定条件和选项差异。",
            "reference_answer": reference_answer,
            "explanation": explanation or "暂无解析。",
            "suggestions": ["定位题干关键词", "排除绝对化或偷换概念选项", "复做同题型 2-3 道巩固方法"],
            "graded_by": "rule",
        }

    reference_text = " ".join(part for part in [reference_answer, explanation] if part)
    overlap = keyword_overlap(answer, reference_text)
    score = min(100, max(20, int(overlap * 100))) if reference_text else 60
    if score >= 75:
        feedback = "要点覆盖较充分，可以继续优化表达结构和案例证据。"
    elif score >= 45:
        feedback = "覆盖了部分要点，但还需要补足关键步骤、指标或依据。"
    else:
        feedback = "回答和参考要点重合较少，建议先按结论、依据、步骤、风险重新组织。"
    return {
        "correct": score >= 75 if reference_text else None,
        "score": score,
        "feedback": feedback,
        "reference_answer": reference_answer or "开放题",
        "explanation": explanation or "暂无解析。",
        "suggestions": ["先讲结论，再讲依据", "补充具体步骤或项目例子", "复盘遗漏关键词并重答一次"],
        "graded_by": "keyword",
    }
