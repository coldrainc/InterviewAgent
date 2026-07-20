from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db.models import CivilServiceQuestionModel


class CivilServiceQuestionRepository:
    def __init__(self, session: AsyncSession, tenant_id: str = "default") -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def upsert_many(self, questions: list[dict[str, Any]]) -> dict[str, int]:
        created = 0
        updated = 0
        for payload in questions:
            normalized = normalize_question_payload(payload)
            content_hash = question_content_hash(normalized)
            existing = await self._get_by_hash(content_hash)
            if existing:
                apply_question_payload(existing, normalized, content_hash)
                updated += 1
            else:
                model = CivilServiceQuestionModel(
                    id=uuid.uuid4(),
                    tenant_id=self.tenant_id,
                    content_hash=content_hash,
                )
                apply_question_payload(model, normalized, content_hash)
                self.session.add(model)
                created += 1
        await self.session.flush()
        return {"created": created, "updated": updated, "total": created + updated}

    async def list_questions(
        self,
        *,
        year: int | None = None,
        subject: str | None = None,
        question_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        filters = [CivilServiceQuestionModel.tenant_id == self.tenant_id]
        if year:
            filters.append(CivilServiceQuestionModel.exam_year == year)
        if subject:
            filters.append(CivilServiceQuestionModel.subject == subject)
        if question_type:
            filters.append(CivilServiceQuestionModel.question_type == question_type)

        total_result = await self.session.execute(
            select(func.count()).select_from(CivilServiceQuestionModel).where(*filters)
        )
        total = int(total_result.scalar_one() or 0)
        result = await self.session.execute(
            select(CivilServiceQuestionModel)
            .where(*filters)
            .order_by(
                CivilServiceQuestionModel.exam_year.desc(),
                CivilServiceQuestionModel.updated_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return [question_to_dict(item) for item in result.scalars().all()], total

    async def _get_by_hash(self, content_hash: str) -> CivilServiceQuestionModel | None:
        result = await self.session.execute(
            select(CivilServiceQuestionModel).where(
                CivilServiceQuestionModel.tenant_id == self.tenant_id,
                CivilServiceQuestionModel.content_hash == content_hash,
            )
        )
        return result.scalar_one_or_none()


def normalize_question_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": str(payload.get("source") or "manual").strip()[:128],
        "source_url": str(payload.get("source_url") or "").strip() or None,
        "exam_year": int(payload.get("exam_year") or payload.get("year") or 0),
        "exam_name": str(payload.get("exam_name") or "考公训练题").strip()[:255],
        "subject": normalize_subject(payload.get("subject")),
        "question_type": str(payload.get("question_type") or payload.get("type") or "综合训练").strip()[:64],
        "prompt": str(payload.get("prompt") or payload.get("question") or "").strip(),
        "choices": payload.get("choices") if isinstance(payload.get("choices"), list) else [],
        "answer": str(payload.get("answer") or "").strip() or None,
        "explanation": str(payload.get("explanation") or "").strip() or None,
        "difficulty": normalize_difficulty(payload.get("difficulty")),
        "tags": payload.get("tags") if isinstance(payload.get("tags"), list) else [],
        "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    }


def normalize_subject(value: Any) -> str:
    cleaned = str(value or "xingce").strip().lower()
    aliases = {
        "行测": "xingce",
        "行政职业能力测验": "xingce",
        "申论": "shenlun",
        "面试": "interview",
        "结构化面试": "interview",
    }
    return aliases.get(cleaned, cleaned or "xingce")[:64]


def normalize_difficulty(value: Any) -> str:
    cleaned = str(value or "medium").strip().lower()
    return cleaned if cleaned in {"easy", "medium", "hard"} else "medium"


def question_content_hash(payload: dict[str, Any]) -> str:
    signature = "\n".join(
        [
            str(payload["exam_year"]),
            payload["exam_name"],
            payload["subject"],
            payload["question_type"],
            payload["prompt"],
        ]
    )
    return hashlib.sha256(signature.encode("utf-8")).hexdigest()


def apply_question_payload(model: CivilServiceQuestionModel, payload: dict[str, Any], content_hash: str) -> None:
    model.source = payload["source"]
    model.source_url = payload["source_url"]
    model.exam_year = payload["exam_year"]
    model.exam_name = payload["exam_name"]
    model.subject = payload["subject"]
    model.question_type = payload["question_type"]
    model.prompt = payload["prompt"]
    model.choices_json = payload["choices"]
    model.answer = payload["answer"]
    model.explanation = payload["explanation"]
    model.difficulty = payload["difficulty"]
    model.tags_json = payload["tags"]
    model.metadata_json = payload["metadata"]
    model.content_hash = content_hash


def question_to_dict(model: CivilServiceQuestionModel) -> dict[str, Any]:
    return {
        "id": str(model.id),
        "source": model.source,
        "source_url": model.source_url,
        "exam_year": model.exam_year,
        "exam_name": model.exam_name,
        "subject": model.subject,
        "question_type": model.question_type,
        "prompt": model.prompt,
        "choices": model.choices_json,
        "answer": model.answer,
        "explanation": model.explanation,
        "difficulty": model.difficulty,
        "tags": model.tags_json,
        "metadata": model.metadata_json,
        "created_at": model.created_at.isoformat(),
        "updated_at": model.updated_at.isoformat(),
    }
