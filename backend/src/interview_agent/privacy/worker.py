from __future__ import annotations

import asyncio
import logging

from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.object_storage import ObjectStorage
from interview_agent.privacy.deletion_service import execute_due_deletions
from interview_agent.services.security_service import SecurityService


logger = logging.getLogger("interview_agent.privacy")


async def run_deletion_worker(
    object_storage: ObjectStorage,
    *,
    interval_seconds: int = 3600,
) -> None:
    while True:
        try:
            async with session_scope() as db:
                results = await execute_due_deletions(db, object_storage=object_storage)
                for result in results:
                    request = result["request"]
                    await SecurityService(db, tenant_id=result["tenant_id"]).record_event(
                        event_type="privacy_deletion_executed",
                        severity="info",
                        user_id=result["user_id"],
                        metadata={
                            "request_id": request["id"],
                            "deleted_counts": request["scope"].get("deleted_counts", {}),
                        },
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("privacy_deletion_worker_failed")
        await asyncio.sleep(interval_seconds)
