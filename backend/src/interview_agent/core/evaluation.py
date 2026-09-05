"""面试结构化评估协议：JSON schema、容错解析与可读文本渲染。

面试官模式产出候选人能力报告（7 维评分），候选人模式产出面试官提问质量报告。
LLM 返回非法 JSON 时降级为文本评估（total_score=None），保证会话正常收尾。
"""

from __future__ import annotations

import json
import re
from typing import Any

from interview_agent.core.config import InterviewMode

# 面试官模式：7 个评分维度（与 InterviewConfig.rubric 的 key 对齐）
INTERVIEWER_DIMENSIONS: dict[str, str] = {
    "technical_depth": "技术深度",
    "communication": "沟通表达",
    "problem_solving": "问题拆解",
    "role_fit": "岗位匹配",
    "resume_truthfulness": "简历真实性",
    "ai_engineering": "AI 工程化",
    "agent_frameworks": "框架理解",
}

# 候选人模式：评估用户（扮演面试官）的提问质量
CANDIDATE_DIMENSIONS: dict[str, str] = {
    "question_depth": "追问深度",
    "coverage": "方向覆盖",
    "differentiation": "问题区分度",
}

SUGGESTION_CATEGORIES = {
    "rag", "agent", "system_design", "llmops", "behavior",
    "resume", "interviewer_skill", "general",
}


def dimensions_for_mode(mode: str | InterviewMode) -> dict[str, str]:
    if isinstance(mode, InterviewMode):
        is_candidate = mode == InterviewMode.CANDIDATE
    else:
        is_candidate = str(mode) == "candidate"
    return CANDIDATE_DIMENSIONS if is_candidate else INTERVIEWER_DIMENSIONS


def empty_payload(mode: str | InterviewMode) -> dict[str, Any]:
    return {
        "version": "v1",
        "mode": "candidate" if dimensions_for_mode(mode) is CANDIDATE_DIMENSIONS else "interviewer",
        "degraded": False,
        "verdict": None,
        "total_score": None,
        "dimension_scores": {},
        "per_question": [],
        "evidence": [],
        "strength_tags": [],
        "weakness_tags": [],
        "suggestions": [],
        "summary": "",
    }


def degraded_payload(raw_text: str, mode: str | InterviewMode) -> dict[str, Any]:
    """LLM 输出无法解析时的降级结构：总分留空，文本整体存入 summary/suggestions。"""
    payload = empty_payload(mode)
    payload["degraded"] = True
    text = (raw_text or "").strip()
    payload["summary"] = text
    if text:
        payload["suggestions"] = [
            {"title": "面试官文字评价", "category": "general", "detail": text}
        ]
    return payload


def parse_evaluation_json(raw_text: str, mode: str | InterviewMode) -> dict[str, Any]:
    """从 LLM 输出中提取结构化评估；失败时返回降级 payload。"""
    text = (raw_text or "").strip()
    if not text:
        return degraded_payload(raw_text, mode)
    candidate = _extract_json_object(text)
    if candidate is None:
        return degraded_payload(raw_text, mode)
    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return degraded_payload(raw_text, mode)
    if not isinstance(data, dict):
        return degraded_payload(raw_text, mode)
    return _normalize_payload(data, mode)


def _extract_json_object(text: str) -> str | None:
    """容忍 ```json 代码块和前后缀文字，截取最外层 { ... }。"""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return None


def _clamp_int(value: Any, low: int, high: int) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return max(low, min(high, number))


def _normalize_payload(data: dict[str, Any], mode: str | InterviewMode) -> dict[str, Any]:
    payload = empty_payload(mode)
    dimensions = dimensions_for_mode(mode)

    verdict = data.get("verdict")
    if isinstance(verdict, str) and verdict.strip():
        payload["verdict"] = verdict.strip()

    total = _clamp_int(data.get("total_score"), 0, 100)
    payload["total_score"] = total

    raw_dims = data.get("dimension_scores")
    if isinstance(raw_dims, dict):
        normalized_dims: dict[str, int] = {}
        for key in dimensions:
            score = _clamp_int(raw_dims.get(key), 0, 5)
            if score is not None:
                normalized_dims[key] = score
        payload["dimension_scores"] = normalized_dims

    raw_questions = data.get("per_question")
    if isinstance(raw_questions, list):
        questions: list[dict[str, Any]] = []
        for item in raw_questions:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or item.get("topic") or "").strip()
            comment = str(item.get("comment") or item.get("feedback") or "").strip()
            if not question and not comment:
                continue
            questions.append(
                {
                    "question": question,
                    "score": _clamp_int(item.get("score"), 0, 5),
                    "comment": comment,
                }
            )
        payload["per_question"] = questions

    raw_evidence = data.get("evidence")
    if isinstance(raw_evidence, list):
        evidence: list[dict[str, str]] = []
        for item in raw_evidence:
            if isinstance(item, str) and item.strip():
                evidence.append({"quote": item.strip(), "point": ""})
            elif isinstance(item, dict):
                quote = str(item.get("quote") or item.get("text") or "").strip()
                point = str(item.get("point") or item.get("supports") or "").strip()
                if quote or point:
                    evidence.append({"quote": quote, "point": point})
        payload["evidence"] = evidence

    payload["strength_tags"] = _normalize_tags(data.get("strength_tags"))
    payload["weakness_tags"] = _normalize_tags(data.get("weakness_tags"))

    raw_suggestions = data.get("suggestions")
    if isinstance(raw_suggestions, list):
        suggestions: list[dict[str, str]] = []
        for index, item in enumerate(raw_suggestions):
            if isinstance(item, str) and item.strip():
                suggestions.append(
                    {"title": item.strip()[:80], "category": "general", "detail": item.strip()}
                )
            elif isinstance(item, dict):
                title = str(item.get("title") or item.get("topic") or f"建议 {index + 1}").strip()
                detail = str(item.get("detail") or item.get("suggestion") or item.get("action") or "").strip()
                category = str(item.get("category") or "general").strip()
                if category not in SUGGESTION_CATEGORIES:
                    category = "general"
                if title or detail:
                    suggestions.append({"title": title[:80], "category": category, "detail": detail or title})
        payload["suggestions"] = suggestions

    summary = data.get("summary")
    if isinstance(summary, str) and summary.strip():
        payload["summary"] = summary.strip()

    # 维度完全缺失且没有任何题目点评时，视为解析失败，走降级
    if not payload["dimension_scores"] and not payload["per_question"] and not payload["summary"]:
        return degraded_payload(json.dumps(data, ensure_ascii=False), mode)
    return payload


def _normalize_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            tags.append(item.strip()[:40])
    return tags


def render_evaluation_text(payload: dict[str, Any], mode: str | InterviewMode) -> str:
    """把结构化评估渲染成会话中展示的中文文本。"""
    dimensions = dimensions_for_mode(mode)
    is_candidate = dimensions is CANDIDATE_DIMENSIONS
    subject = "你的提问表现" if is_candidate else "候选人表现"

    if payload.get("degraded"):
        summary = (payload.get("summary") or "").strip()
        header = "面试评估（文本版）\n" if not is_candidate else "提问质量评估（文本版）\n"
        return f"{header}\n{summary}".strip()

    lines: list[str] = []
    title = "提问质量评估" if is_candidate else "面试评估报告"
    lines.append(f"## {title}")
    if payload.get("verdict"):
        lines.append(f"结论：{payload['verdict']}")
    if payload.get("total_score") is not None:
        lines.append(f"{subject}总分：{payload['total_score']}/100")

    dims = payload.get("dimension_scores") or {}
    if dims:
        lines.append("")
        lines.append("维度评分：")
        for key, label in dimensions.items():
            if key in dims:
                lines.append(f"- {label}：{dims[key]}/5")

    questions = payload.get("per_question") or []
    if questions:
        lines.append("")
        lines.append("逐题点评：")
        for item in questions:
            score = f"（{item['score']}/5）" if item.get("score") is not None else ""
            question = item.get("question") or "本题"
            lines.append(f"- {question}{score}：{item.get('comment') or '—'}")

    evidence = payload.get("evidence") or []
    if evidence:
        lines.append("")
        lines.append("关键证据：")
        for item in evidence[:5]:
            point = f" —— {item['point']}" if item.get("point") else ""
            lines.append(f"- {item.get('quote') or '—'}{point}")

    strengths = payload.get("strength_tags") or []
    if strengths:
        lines.append("")
        lines.append(f"亮点：{'、'.join(strengths)}")
    weaknesses = payload.get("weakness_tags") or []
    if weaknesses:
        lines.append(f"待提升：{'、'.join(weaknesses)}")

    suggestions = payload.get("suggestions") or []
    if suggestions:
        lines.append("")
        lines.append("改进建议：")
        for item in suggestions:
            lines.append(f"- {item.get('title') or '建议'}：{item.get('detail') or ''}".rstrip("："))

    summary = (payload.get("summary") or "").strip()
    if summary:
        lines.append("")
        lines.append(summary)
    return "\n".join(lines)


def evaluation_prompt_instruction(mode: str | InterviewMode) -> str:
    """EVALUATION 阶段给 LLM 的结构化输出指令。"""
    dimensions = dimensions_for_mode(mode)
    is_candidate = dimensions is CANDIDATE_DIMENSIONS
    dim_list = "、".join(f"{key}（{label}）" for key, label in dimensions.items())
    if is_candidate:
        return f"""面试轮次已达上限，请对用户（扮演面试官）的提问质量做最终评估。
必须只输出一个 JSON 对象（不要输出 JSON 以外的文字、不要用代码块），字段如下：
{{
  "verdict": "提问水平结论：优秀 / 良好 / 待提升",
  "total_score": 0到100的整数,
  "dimension_scores": {{ {", ".join(f'"{k}": 0到5的整数' for k in dimensions)} }},
  "per_question": [{{"question": "用户提过的问题摘要", "score": 0到5的整数, "comment": "该问题的质量点评"}}],
  "strength_tags": ["提问亮点标签，4-8字"],
  "weakness_tags": ["提问不足标签，4-8字"],
  "suggestions": [{{"title": "建议标题", "category": "interviewer_skill", "detail": "具体可操作的提问改进建议"}}],
  "summary": "一段话总体评价"
}}
评分维度说明：{dim_list}。
评分要基于面试记录中用户实际提出的问题：追问是否有深度、方向是否覆盖岗位关键能力、问题是否有区分度。
建议要具体，针对如何追问项目细节、指标、取舍、故障复盘。"""
    return f"""面试结束，请基于简历、面试目标和完整面试记录给出最终结构化评估。
必须只输出一个 JSON 对象（不要输出 JSON 以外的文字、不要用代码块），字段如下：
{{
  "verdict": "通过 / 谨慎通过 / 暂不通过",
  "total_score": 0到100的整数,
  "dimension_scores": {{ {", ".join(f'"{k}": 0到5的整数' for k in dimensions)} }},
  "per_question": [{{"question": "面试题摘要", "score": 0到5的整数, "comment": "候选人该题表现简评"}}],
  "evidence": [{{"quote": "候选人回答中的关键原话或要点", "point": "该证据证明了什么"}}],
  "strength_tags": ["优势标签，4-8字"],
  "weakness_tags": ["薄弱标签，4-8字"],
  "suggestions": [{{"title": "补强方向标题", "category": "rag|agent|system_design|llmops|behavior|resume|general", "detail": "具体学习或练习建议"}}],
  "summary": "一段话总体评价"
}}
评分维度说明：{dim_list}。
评分必须基于面试记录中的真实证据，不要臆造候选人没有说过的内容；
suggestions 给出 3 条最关键的补强建议，要能直接转化为复习任务。"""
