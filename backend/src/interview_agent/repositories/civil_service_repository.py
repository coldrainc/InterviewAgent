from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db.models import CivilServiceQuestionModel


class CivilServiceQuestionRepository:
    def __init__(
        self,
        session: AsyncSession,
        tenant_id: str = "default",
        user_id: str = "anonymous",
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

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
                    user_id=self.user_id,
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
        category: str | None = None,
        year: int | None = None,
        subject: str | None = None,
        question_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        filters = [
            CivilServiceQuestionModel.tenant_id == self.tenant_id,
            CivilServiceQuestionModel.user_id == self.user_id,
        ]
        if category:
            filters.append(CivilServiceQuestionModel.practice_category == normalize_practice_category(category))
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
                CivilServiceQuestionModel.user_id == self.user_id,
                CivilServiceQuestionModel.content_hash == content_hash,
            )
        )
        return result.scalar_one_or_none()


def normalize_question_payload(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = str(payload.get("prompt") or payload.get("question") or "").strip()
    if not prompt:
        raise ValueError("题目内容不能为空。")
    exam_year = int(payload.get("exam_year") or payload.get("year") or 0)
    if exam_year <= 0:
        raise ValueError("题目年份必须是有效数字。")
    return {
        "practice_category": normalize_practice_category(
            payload.get("practice_category") or payload.get("category") or infer_practice_category(payload)
        ),
        "source": str(payload.get("source") or "manual").strip()[:128],
        "source_url": str(payload.get("source_url") or "").strip() or None,
        "exam_year": exam_year,
        "exam_name": str(payload.get("exam_name") or "练习题").strip()[:255],
        "subject": normalize_subject(payload.get("subject")),
        "question_type": str(payload.get("question_type") or payload.get("type") or "综合训练").strip()[:64],
        "prompt": prompt,
        "choices": payload.get("choices") if isinstance(payload.get("choices"), list) else [],
        "answer": str(payload.get("answer") or "").strip() or None,
        "explanation": str(payload.get("explanation") or "").strip() or None,
        "difficulty": normalize_difficulty(payload.get("difficulty")),
        "tags": payload.get("tags") if isinstance(payload.get("tags"), list) else [],
        "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    }


def normalize_subject(value: Any) -> str:
    cleaned = str(value or "general").strip().lower()
    aliases = {
        "行测": "xingce",
        "行政职业能力测验": "xingce",
        "申论": "shenlun",
        "面试": "interview",
        "结构化面试": "interview",
    }
    return aliases.get(cleaned, cleaned or "general")[:64]


def normalize_practice_category(value: Any) -> str:
    cleaned = str(value or "internet").strip().lower()
    aliases = {
        "考公": "civil_service",
        "公考": "civil_service",
        "公务员": "civil_service",
        "公职考试": "civil_service",
        "civil-service": "civil_service",
        "civil service": "civil_service",
        "互联网": "internet",
        "互联网面试": "internet",
        "技术面试": "internet",
        "面试": "interview",
        "ai": "ai_engineering",
        "ai工程": "ai_engineering",
        "ai 工程": "ai_engineering",
        "ai工程面试": "ai_engineering",
    }
    return aliases.get(cleaned, cleaned or "internet")[:64]


def infer_practice_category(payload: dict[str, Any]) -> str:
    subject = normalize_subject(payload.get("subject"))
    exam_name = str(payload.get("exam_name") or "").lower()
    tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
    joined_tags = " ".join(str(tag).lower() for tag in tags)
    if subject in {"xingce", "shenlun"} or any(marker in exam_name for marker in ("考公", "国考", "省考", "申论", "行测")):
        return "civil_service"
    if any(marker in joined_tags for marker in ("考公", "国考", "省考", "申论", "行测")):
        return "civil_service"
    if any(marker in exam_name for marker in ("ai", "agent", "rag", "llm")):
        return "ai_engineering"
    return "internet"


def normalize_difficulty(value: Any) -> str:
    cleaned = str(value or "medium").strip().lower()
    return cleaned if cleaned in {"easy", "medium", "hard"} else "medium"


def question_content_hash(payload: dict[str, Any]) -> str:
    signature = "\n".join(
        [
            payload["practice_category"],
            str(payload["exam_year"]),
            payload["exam_name"],
            payload["subject"],
            payload["question_type"],
            payload["prompt"],
        ]
    )
    return hashlib.sha256(signature.encode("utf-8")).hexdigest()


def apply_question_payload(model: CivilServiceQuestionModel, payload: dict[str, Any], content_hash: str) -> None:
    model.practice_category = payload["practice_category"]
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
        "practice_category": model.practice_category,
        "category": model.practice_category,
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
