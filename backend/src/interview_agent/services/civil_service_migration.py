"""v1 公考题库（civil_service_questions）一次性迁移到 v2 题库（practice_questions）。

字段映射：explanation -> answer_detail；exam_year/exam_name 等 v1 专有字段入 metadata。
去重沿用 v2 content_hash（prompt + answer），重复执行幂等。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db.models import CivilServiceQuestionModel
from interview_agent.repositories.practice_question_repository import PracticeQuestionRepository


def map_civil_question(row: dict[str, Any]) -> dict[str, Any]:
    """把 v1 题目字典映射为 v2 upsert payload。"""
    metadata = dict(row.get("metadata") or {})
    metadata.update(
        {
            "migrated_from": "civil_service_questions",
            "original_id": row.get("id"),
            "exam_year": row.get("exam_year"),
            "exam_name": row.get("exam_name"),
        }
    )
    return {
        "practice_category": row.get("practice_category") or "civil_service",
        "source": row.get("source") or "migration",
        "source_url": row.get("source_url"),
        "subject": row.get("subject") or "",
        "question_type": row.get("question_type") or "",
        "prompt": row.get("prompt") or "",
        "choices": row.get("choices") if isinstance(row.get("choices"), list) else [],
        "answer": row.get("answer") or "",
        "answer_detail": row.get("explanation") or row.get("answer_detail") or "",
        "difficulty": row.get("difficulty") or "medium",
        "tags": row.get("tags") if isinstance(row.get("tags"), list) else [],
        "metadata": metadata,
    }


async def migrate_civil_service_questions(session: AsyncSession) -> dict[str, int]:
    """扫描全部 v1 题目并按租户/用户批量 upsert 到 v2，返回计数。"""
    result = await session.execute(select(CivilServiceQuestionModel))
    rows = result.scalars().all()

    payloads_by_owner: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        payload = map_civil_question(
            {
                "id": str(row.id),
                "practice_category": row.practice_category,
                "source": row.source,
                "source_url": row.source_url,
                "exam_year": row.exam_year,
                "exam_name": row.exam_name,
                "subject": row.subject,
                "question_type": row.question_type,
                "prompt": row.prompt,
                "choices": row.choices_json or [],
                "answer": row.answer or "",
                "explanation": row.explanation or "",
                "difficulty": row.difficulty,
                "tags": row.tags_json or [],
                "metadata": row.metadata_json or {},
            }
        )
        payloads_by_owner.setdefault((row.tenant_id, row.user_id), []).append(payload)

    stats = {"scanned": len(rows), "created": 0, "updated": 0, "owners": len(payloads_by_owner)}
    for (tenant_id, user_id), payloads in payloads_by_owner.items():
        repo = PracticeQuestionRepository(session, tenant_id=tenant_id, user_id=user_id)
        counts = await repo.bulk_upsert(payloads)
        stats["created"] += counts["created"]
        stats["updated"] += counts["updated"]
    return stats
