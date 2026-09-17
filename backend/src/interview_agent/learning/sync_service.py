from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.learning.models import LearningEffectReceiptModel
from interview_agent.learning.sync_cursor import decode_cursor, encode_cursor


class LearningSyncService:
    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def pull(self, *, cursor: str | None, limit: int = 100) -> dict:
        parsed = decode_cursor(cursor)
        statement = select(LearningEffectReceiptModel).where(
            LearningEffectReceiptModel.tenant_id == self.tenant_id,
            LearningEffectReceiptModel.user_id == self.user_id,
        )
        if parsed is not None:
            statement = statement.where(
                or_(
                    LearningEffectReceiptModel.created_at > parsed.occurred_at,
                    and_(
                        LearningEffectReceiptModel.created_at == parsed.occurred_at,
                        LearningEffectReceiptModel.id > parsed.event_id,
                    ),
                )
            )
        rows = list(
            (
                await self.session.execute(
                    statement.order_by(
                        LearningEffectReceiptModel.created_at.asc(),
                        LearningEffectReceiptModel.id.asc(),
                    ).limit(limit + 1)
                )
            ).scalars()
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = cursor
        if page:
            last = page[-1]
            next_cursor = encode_cursor(last.created_at, last.id)
        return {
            "schema_version": 1,
            "authority": "server",
            "events": [self._event(item) for item in page],
            "next_cursor": next_cursor,
            "has_more": has_more,
            "server_time": datetime.now(timezone.utc).isoformat(),
            "bootstrap": {"today": "/learning/today"} if cursor is None else None,
        }

    @staticmethod
    def _event(model: LearningEffectReceiptModel) -> dict:
        return {
            "event_id": str(model.id),
            "entity": "learning_task_run",
            "entity_id": str(model.run_id),
            "task_id": str(model.task_id),
            "operation": "updated",
            "version": model.current_version,
            "status": model.current_status,
            "accepted": model.accepted,
            "receipt": dict(model.receipt_json or {}),
            "changed_at": model.created_at.isoformat(),
        }
