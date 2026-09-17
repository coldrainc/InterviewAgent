from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.fixtures.review_site_admin import ADMIN_REVIEW_SITE_FIXTURE
from interview_agent.repositories.review_site_repository import ReviewSiteRepository


class AdminTestDataService:
    def __init__(self, session: AsyncSession, *, tenant_id: str, user_id: str) -> None:
        self.plan_repo = ReviewSiteRepository(session, tenant_id, user_id)

    async def ensure_review_site_fixture(self) -> dict[str, int | str]:
        plan_info = ADMIN_REVIEW_SITE_FIXTURE["plan"]
        plan_key = str(plan_info["plan_key"])
        existing = await self.plan_repo.get_plan_by_key(plan_key)
        if existing:
            return {"plan_count": 0, "plan_id": str(existing.id)}
        plan = await self.plan_repo.create_plan_from_fixture(ADMIN_REVIEW_SITE_FIXTURE)
        return {"plan_count": 1, "plan_id": str(plan.id)}
