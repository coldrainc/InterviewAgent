from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Integer, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db.models import (
    PracticeAttemptModel,
    PracticeQuestionModel,
    PracticeWrongBookModel,
    utcnow,
)


class PracticeQuestionRepository:
    def __init__(
        self,
        session: AsyncSession,
        tenant_id: str = "default",
        user_id: str = "anonymous",
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def list_questions(
        self,
        *,
        category: str | None = None,
        subject: str | None = None,
        question_type: str | None = None,
        difficulty: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        filters = [
            PracticeQuestionModel.tenant_id == self.tenant_id,
            PracticeQuestionModel.user_id == self.user_id,
        ]
        if category:
            filters.append(PracticeQuestionModel.practice_category == category)
        if subject:
            filters.append(PracticeQuestionModel.subject == subject)
        if question_type:
            filters.append(PracticeQuestionModel.question_type == question_type)
        if difficulty:
            filters.append(PracticeQuestionModel.difficulty == difficulty)
        if keyword:
            like = f"%{keyword.strip()}%"
            filters.append(
                or_(
                    PracticeQuestionModel.prompt.ilike(like),
                    PracticeQuestionModel.answer.ilike(like),
                    PracticeQuestionModel.answer_detail.ilike(like),
                )
            )

        count_stmt = select(func.count(PracticeQuestionModel.id)).where(*filters)
        total_result = await self.session.execute(count_stmt)
        total = int(total_result.scalar_one() or 0)

        stmt = (
            select(PracticeQuestionModel)
            .where(*filters)
            .order_by(PracticeQuestionModel.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        items = [question_to_dict(item) for item in result.scalars().all()]
        return items, total

    async def get_question(self, question_id: str | uuid.UUID) -> dict[str, Any] | None:
        try:
            parsed = question_id if isinstance(question_id, uuid.UUID) else uuid.UUID(str(question_id))
        except ValueError:
            parsed = None
        if parsed is not None:
            result = await self.session.execute(
                select(PracticeQuestionModel).where(
                    PracticeQuestionModel.tenant_id == self.tenant_id,
                    PracticeQuestionModel.user_id == self.user_id,
                    PracticeQuestionModel.id == parsed,
                )
            )
            model = result.scalar_one_or_none()
            if model:
                return question_to_dict(model)
        return None

    async def upsert_question(self, **fields: Any) -> tuple[dict[str, Any], bool]:
        payload = dict(fields)
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("prompt is required")
        answer_text = str(payload.get("answer") or "")
        content_hash = question_content_hash(prompt, answer_text)
        existing = await self._get_by_hash(content_hash)
        if existing:
            _apply_question_payload(existing, payload, content_hash)
            await self.session.flush()
            return question_to_dict(existing), False
        model = PracticeQuestionModel(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            content_hash=content_hash,
        )
        _apply_question_payload(model, payload, content_hash)
        self.session.add(model)
        await self.session.flush()
        return question_to_dict(model), True

    async def bulk_upsert(self, questions: list[dict[str, Any]]) -> dict[str, int]:
        created = 0
        updated = 0
        for payload in questions:
            prompt = str(payload.get("prompt") or "").strip()
            if not prompt:
                continue
            answer_text = str(payload.get("answer") or "")
            content_hash = question_content_hash(prompt, answer_text)
            existing = await self._get_by_hash(content_hash)
            if existing:
                _apply_question_payload(existing, payload, content_hash)
                updated += 1
            else:
                model = PracticeQuestionModel(
                    id=uuid.uuid4(),
                    tenant_id=self.tenant_id,
                    user_id=self.user_id,
                    content_hash=content_hash,
                )
                _apply_question_payload(model, payload, content_hash)
                self.session.add(model)
                created += 1
        await self.session.flush()
        return {"created": created, "updated": updated, "total": created + updated}

    async def list_wrong_book(
        self,
        mark_type: str | None = None,
        mastery_max: int | None = None,
        category: str | None = None,
        keyword: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        filters = [
            PracticeWrongBookModel.tenant_id == self.tenant_id,
            PracticeWrongBookModel.user_id == self.user_id,
        ]
        if mark_type:
            filters.append(PracticeWrongBookModel.mark_type == mark_type)
        if mastery_max is not None:
            filters.append(PracticeWrongBookModel.mastery_level <= int(mastery_max))
        join_needed = bool(category or keyword)
        stmt = select(PracticeWrongBookModel)
        if join_needed:
            stmt = stmt.join(
                PracticeQuestionModel,
                PracticeQuestionModel.id == PracticeWrongBookModel.question_id,
            )
            if category:
                filters.append(PracticeQuestionModel.practice_category == category)
            if keyword:
                like = f"%{keyword.strip()}%"
                filters.append(
                    or_(
                        PracticeQuestionModel.prompt.ilike(like),
                        PracticeQuestionModel.answer.ilike(like),
                        PracticeQuestionModel.answer_detail.ilike(like),
                    )
                )
        result = await self.session.execute(
            stmt.where(*filters)
            .order_by(PracticeWrongBookModel.updated_at.desc())
            .limit(limit)
        )
        entries = [wrong_entry_to_dict(item) for item in result.scalars().all()]
        if not entries:
            return entries
        question_ids = {uuid.UUID(entry["question_id"]) for entry in entries}
        question_rows = await self.session.execute(
            select(PracticeQuestionModel).where(PracticeQuestionModel.id.in_(question_ids))
        )
        questions_by_id = {str(item.id): question_to_dict(item) for item in question_rows.scalars().all()}
        for entry in entries:
            question = questions_by_id.get(entry["question_id"])
            entry["question"] = question
            if question:
                entry["prompt"] = question.get("prompt")
                entry["practice_category"] = question.get("practice_category")
        return entries

    async def add_attempt(
        self,
        *,
        question_id: str | uuid.UUID,
        question_type: str,
        answer: str,
        is_correct: bool,
        score: int,
        elapsed_seconds: int | None,
        feedback: str,
    ) -> dict[str, Any]:
        try:
            parsed = question_id if isinstance(question_id, uuid.UUID) else uuid.UUID(str(question_id))
        except ValueError as exc:
            raise ValueError("question_id is invalid") from exc
        model = PracticeAttemptModel(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            question_id=parsed,
            question_type=str(question_type or "")[:64],
            answer=str(answer or "")[:8000],
            is_correct=bool(is_correct),
            score=max(0, min(100, int(score))),
            elapsed_seconds=int(elapsed_seconds) if elapsed_seconds is not None else None,
            feedback=str(feedback or "")[:2000],
        )
        self.session.add(model)
        await self.session.flush()
        return attempt_to_dict(model)

    async def list_attempts(
        self,
        *,
        question_id: str | uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        filters = [
            PracticeAttemptModel.tenant_id == self.tenant_id,
            PracticeAttemptModel.user_id == self.user_id,
        ]
        if question_id is not None:
            try:
                parsed = question_id if isinstance(question_id, uuid.UUID) else uuid.UUID(str(question_id))
            except ValueError:
                parsed = None
            if parsed is not None:
                filters.append(PracticeAttemptModel.question_id == parsed)
        result = await self.session.execute(
            select(PracticeAttemptModel)
            .where(*filters)
            .order_by(PracticeAttemptModel.created_at.desc())
            .limit(max(1, min(200, int(limit))))
        )
        return [attempt_to_dict(item) for item in result.scalars().all()]

    async def attempt_overview(self, *, since: datetime | None = None) -> dict[str, Any]:
        """作答总览：总数、答对数、正确率、指定时间（含）以来作答数与累计秒数。"""
        filters = [
            PracticeAttemptModel.tenant_id == self.tenant_id,
            PracticeAttemptModel.user_id == self.user_id,
        ]
        result = await self.session.execute(
            select(
                func.count(PracticeAttemptModel.id),
                func.coalesce(func.sum(func.cast(PracticeAttemptModel.is_correct, Integer)), 0),
                func.coalesce(func.sum(PracticeAttemptModel.elapsed_seconds), 0),
            ).where(*filters)
        )
        total, correct, elapsed_seconds = result.one()
        since_filters = list(filters)
        if since is not None:
            since_filters.append(PracticeAttemptModel.created_at >= since)
        since_result = await self.session.execute(
            select(
                func.count(PracticeAttemptModel.id),
                func.coalesce(func.sum(PracticeAttemptModel.elapsed_seconds), 0),
            ).where(*since_filters)
        )
        since_count, since_elapsed = since_result.one()
        total = int(total or 0)
        return {
            "total_attempts": total,
            "correct_count": int(correct or 0),
            "correct_rate": round(int(correct or 0) / total, 3) if total else 0.0,
            "elapsed_seconds_total": int(elapsed_seconds or 0),
            "since_attempts": int(since_count or 0),
            "since_elapsed_seconds": int(since_elapsed or 0),
        }

    async def wrong_book_overview(self) -> dict[str, Any]:
        result = await self.session.execute(
            select(
                PracticeWrongBookModel.mark_type,
                func.count(PracticeWrongBookModel.id),
            )
            .where(
                PracticeWrongBookModel.tenant_id == self.tenant_id,
                PracticeWrongBookModel.user_id == self.user_id,
            )
            .group_by(PracticeWrongBookModel.mark_type)
        )
        counts = {str(mark): int(count) for mark, count in result.all()}
        return {
            "wrong_count": counts.get("wrong", 0),
            "mastered_count": counts.get("mastered", 0),
            "total": sum(counts.values()),
        }

    async def get_or_create_wrong_entry(
        self,
        question_id: str | uuid.UUID,
    ) -> PracticeWrongBookModel:
        try:
            parsed = question_id if isinstance(question_id, uuid.UUID) else uuid.UUID(str(question_id))
        except ValueError:
            raise ValueError("question_id is invalid")
        result = await self.session.execute(
            select(PracticeWrongBookModel).where(
                PracticeWrongBookModel.tenant_id == self.tenant_id,
                PracticeWrongBookModel.user_id == self.user_id,
                PracticeWrongBookModel.question_id == parsed,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        question_result = await self.session.execute(
            select(PracticeQuestionModel).where(
                PracticeQuestionModel.id == parsed,
                PracticeQuestionModel.tenant_id == self.tenant_id,
                PracticeQuestionModel.user_id == self.user_id,
            )
        )
        question = question_result.scalar_one_or_none()
        if not question:
            raise ValueError("question not found")
        new_entry = PracticeWrongBookModel(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            question_id=question.id,
        )
        self.session.add(new_entry)
        await self.session.flush()
        return new_entry

    async def update_wrong_entry(
        self,
        question_id: str | uuid.UUID,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        entry = await self.get_or_create_wrong_entry(question_id)
        if "mark_type" in data and data["mark_type"] is not None:
            entry.mark_type = str(data["mark_type"])
        if "mastery_level" in data and data["mastery_level"] is not None:
            entry.mastery_level = max(0, min(5, int(data["mastery_level"])))
        if "note" in data:
            entry.note = str(data["note"]) if data["note"] is not None else None
        if "metadata" in data and isinstance(data["metadata"], dict):
            entry.metadata_json = data["metadata"]
        if "attempt_count" in data and data["attempt_count"] is not None:
            entry.attempt_count = int(data["attempt_count"])
        if "correct_count" in data and data["correct_count"] is not None:
            entry.correct_count = int(data["correct_count"])
        if "last_attempt_at" in data and data["last_attempt_at"] is not None:
            entry.last_attempt_at = data["last_attempt_at"]
        elif data.get("attempt"):
            entry.last_attempt_at = utcnow()
        await self.session.flush()
        return wrong_entry_to_dict(entry)

    async def touch_wrong_entry(
        self,
        *,
        question_id: str | uuid.UUID,
        is_correct: bool,
    ) -> dict[str, Any] | None:
        """作答后自动维护错题本：答错收录、计数、掌握度升降。

        - 答错：无记录则新建（mark_type=wrong）；mastery -1（下限 0），mark_type 置 wrong。
        - 答对：无记录则不创建；mastery +1（上限 5），达到 3 且原为 wrong 时置 mastered。
        """
        try:
            parsed = question_id if isinstance(question_id, uuid.UUID) else uuid.UUID(str(question_id))
        except ValueError as exc:
            raise ValueError("question_id is invalid") from exc
        result = await self.session.execute(
            select(PracticeWrongBookModel).where(
                PracticeWrongBookModel.tenant_id == self.tenant_id,
                PracticeWrongBookModel.user_id == self.user_id,
                PracticeWrongBookModel.question_id == parsed,
            )
        )
        entry = result.scalar_one_or_none()
        now = utcnow()
        if entry is None:
            if is_correct:
                return None
            question_result = await self.session.execute(
                select(PracticeQuestionModel).where(
                    PracticeQuestionModel.id == parsed,
                    PracticeQuestionModel.tenant_id == self.tenant_id,
                    PracticeQuestionModel.user_id == self.user_id,
                )
            )
            question = question_result.scalar_one_or_none()
            if not question:
                raise ValueError("question not found")
            entry = PracticeWrongBookModel(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                question_id=question.id,
                mark_type="wrong",
                mastery_level=0,
                attempt_count=1,
                correct_count=0,
                last_attempt_at=now,
            )
            self.session.add(entry)
            await self.session.flush()
            return wrong_entry_to_dict(entry)

        entry.attempt_count = int(entry.attempt_count or 0) + 1
        entry.last_attempt_at = now
        if is_correct:
            entry.correct_count = int(entry.correct_count or 0) + 1
            entry.mastery_level = min(5, int(entry.mastery_level or 0) + 1)
            if entry.mastery_level >= 3 and entry.mark_type == "wrong":
                entry.mark_type = "mastered"
        else:
            entry.mastery_level = max(0, int(entry.mastery_level or 0) - 1)
            entry.mark_type = "wrong"
        await self.session.flush()
        return wrong_entry_to_dict(entry)

    async def _get_by_hash(self, content_hash: str) -> PracticeQuestionModel | None:
        result = await self.session.execute(
            select(PracticeQuestionModel).where(
                PracticeQuestionModel.tenant_id == self.tenant_id,
                PracticeQuestionModel.user_id == self.user_id,
                PracticeQuestionModel.content_hash == content_hash,
            )
        )
        return result.scalar_one_or_none()


def question_content_hash(prompt: str, answer: str) -> str:
    signature = f"{prompt.strip()}\n{answer.strip()}"
    return hashlib.sha256(signature.encode("utf-8")).hexdigest()


def _apply_question_payload(
    model: PracticeQuestionModel,
    payload: dict[str, Any],
    content_hash: str,
) -> None:
    model.practice_category = str(payload.get("practice_category") or payload.get("category") or model.practice_category or "internet")[:64]
    model.source = str(payload.get("source") or model.source or "manual")[:128]
    model.source_url = str(payload.get("source_url") or "") or None if payload.get("source_url") is not None else model.source_url
    model.subject = str(payload.get("subject") or "")[:64] if payload.get("subject") is not None else model.subject
    model.question_type = str(payload.get("question_type") or payload.get("type") or "")[:64] if (payload.get("question_type") or payload.get("type")) is not None else model.question_type
    model.prompt = str(payload.get("prompt") or model.prompt or "")
    choices = payload.get("choices_json") if "choices_json" in payload else payload.get("choices")
    if choices is not None:
        model.choices_json = choices if isinstance(choices, list) else []
    model.answer = str(payload.get("answer") or "") or None if "answer" in payload else model.answer
    model.answer_detail = str(payload.get("answer_detail") or payload.get("explanation") or "") or None if ("answer_detail" in payload or "explanation" in payload) else model.answer_detail
    difficulty = str(payload.get("difficulty") or model.difficulty or "medium").lower()
    model.difficulty = difficulty if difficulty in {"easy", "medium", "hard"} else "medium"
    tags = payload.get("tags_json") if "tags_json" in payload else payload.get("tags")
    if tags is not None:
        model.tags_json = tags if isinstance(tags, list) else []
    if "metadata_json" in payload or "metadata" in payload:
        metadata = payload.get("metadata_json") if "metadata_json" in payload else payload.get("metadata")
        model.metadata_json = metadata if isinstance(metadata, dict) else {}
    model.content_hash = content_hash


def question_to_dict(model: PracticeQuestionModel) -> dict[str, Any]:
    return {
        "id": str(model.id),
        "practice_category": model.practice_category,
        "category": model.practice_category,
        "source": model.source,
        "source_url": model.source_url,
        "subject": model.subject,
        "question_type": model.question_type,
        "prompt": model.prompt,
        "choices": model.choices_json or [],
        "answer": model.answer,
        "answer_detail": model.answer_detail,
        "difficulty": model.difficulty,
        "tags": model.tags_json or [],
        "metadata": model.metadata_json,
        "content_hash": model.content_hash,
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "updated_at": model.updated_at.isoformat() if model.updated_at else None,
    }


def attempt_to_dict(model: PracticeAttemptModel) -> dict[str, Any]:
    return {
        "id": str(model.id),
        "question_id": str(model.question_id),
        "question_type": model.question_type,
        "answer": model.answer,
        "is_correct": model.is_correct,
        "score": model.score,
        "elapsed_seconds": model.elapsed_seconds,
        "feedback": model.feedback,
        "created_at": model.created_at.isoformat() if model.created_at else None,
    }


def wrong_entry_to_dict(model: PracticeWrongBookModel) -> dict[str, Any]:
    return {
        "id": str(model.id),
        "question_id": str(model.question_id),
        "mark_type": model.mark_type,
        "mastery_level": model.mastery_level,
        "last_attempt_at": model.last_attempt_at.isoformat() if model.last_attempt_at else None,
        "attempt_count": model.attempt_count,
        "correct_count": model.correct_count,
        "note": model.note,
        "metadata": model.metadata_json,
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "updated_at": model.updated_at.isoformat() if model.updated_at else None,
    }
