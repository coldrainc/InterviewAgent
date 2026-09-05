"""刷题作答服务：判分 -> 落 practice_attempts -> 错题本自动闭环。

错题闭环规则：
- 答错：自动收录错题本（mark_type=wrong），attempt_count+1，mastery_level -1（下限 0）。
- 答对：attempt_count+1，correct_count+1，mastery_level +1（上限 5）；
  已在错题本且 mastery 达到 3 时标记 mastered，提示可移出。
- 开放题无参考答案（correct=None）：仅作答落库，不自动收录错题本。
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.domain.practice_grading import grade_question, is_choice_question
from interview_agent.repositories.practice_question_repository import PracticeQuestionRepository

logger = logging.getLogger(__name__)

SubjectiveGrader = Callable[[dict[str, Any], str], Awaitable[dict[str, Any] | None]]

MASTERY_REMOVE_THRESHOLD = 3


class PracticeAttemptService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        subjective_grader: SubjectiveGrader | None = None,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.repo = PracticeQuestionRepository(session, tenant_id=tenant_id, user_id=user_id)
        self.subjective_grader = subjective_grader

    async def submit_attempt(
        self,
        *,
        question_id: str,
        answer: str,
        elapsed_seconds: int | None = None,
    ) -> dict[str, Any]:
        question = await self.repo.get_question(question_id)
        if question is None:
            raise LookupError("practice question not found")

        graded = grade_question(question, answer)
        answer_text = (answer or "").strip()

        if (
            answer_text
            and not is_choice_question(question)
            and self.subjective_grader is not None
        ):
            try:
                llm_result = await self.subjective_grader(question, answer_text)
                if llm_result:
                    graded = self._merge_llm_grade(graded, llm_result)
            except Exception:  # noqa: BLE001 - LLM 评分失败时降级关键词判分
                logger.exception("subjective practice grading failed, fallback to keyword")

        correct = graded["correct"]
        is_correct = bool(correct) if correct is not None else graded["score"] >= 75

        attempt = await self.repo.add_attempt(
            question_id=question["id"],
            question_type=str(question.get("question_type") or ""),
            answer=answer_text,
            is_correct=is_correct,
            score=int(graded["score"]),
            elapsed_seconds=elapsed_seconds,
            feedback=str(graded["feedback"] or ""),
        )

        wrong_entry = None
        if answer_text:
            wrong_entry = await self.repo.touch_wrong_entry(
                question_id=question["id"],
                is_correct=is_correct,
            )

        can_remove = bool(wrong_entry and wrong_entry.get("mark_type") == "mastered")
        return {
            "question_id": question["id"],
            "attempt_id": attempt["id"],
            "correct": graded["correct"],
            "score": graded["score"],
            "feedback": graded["feedback"],
            "reference_answer": graded["reference_answer"],
            "explanation": graded["explanation"],
            "suggestions": graded["suggestions"],
            "graded_by": graded["graded_by"],
            "elapsed_seconds": elapsed_seconds,
            "wrong_book": wrong_entry,
            "in_wrong_book": bool(wrong_entry and wrong_entry.get("mark_type") == "wrong"),
            "can_remove_from_wrong_book": can_remove,
        }

    @staticmethod
    def _merge_llm_grade(base: dict[str, Any], llm_result: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        score = llm_result.get("score")
        if score is not None:
            merged["score"] = max(0, min(100, int(score)))
        feedback = str(llm_result.get("feedback") or "").strip()
        if feedback:
            merged["feedback"] = feedback
        suggestions = llm_result.get("suggestions")
        if isinstance(suggestions, list) and suggestions:
            merged["suggestions"] = [str(item) for item in suggestions[:5] if item]
        merged["graded_by"] = "llm"
        merged["correct"] = merged["score"] >= 75 if merged["reference_answer"] != "开放题" else None
        return merged
