from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import APIRouter, Depends

from interview_agent.infrastructure.db.session import session_scope
from interview_agent.infrastructure.security import RequestContext, request_context
from interview_agent.interfaces.routes.review_plans import _require_authenticated
from interview_agent.services.achievement_service import AchievementService
from interview_agent.services.billing_service import InsufficientCreditsError
from interview_agent.services.study_dashboard_service import StudyDashboardService


logger = logging.getLogger("interview_agent.api.study_dashboard")


def create_study_dashboard_router(
    *,
    build_advice_provider: Callable,
    billing_service_factory: Callable,
) -> APIRouter:
    router = APIRouter()

    @router.get("/study/dashboard")
    async def get_study_dashboard(
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            advice_provider = None
            model_id = ""
            try:
                advice_provider, model_id = await build_advice_provider(db, context)
            except InsufficientCreditsError:
                advice_provider = None
            except Exception:
                logger.exception("dashboard advice provider unavailable, fallback to rule advice")
                advice_provider = None
            dashboard = await StudyDashboardService(
                db,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                advice_provider=advice_provider,
            ).build_dashboard()
            if advice_provider is not None and dashboard.get("advice", {}).get("source") == "llm":
                try:
                    await billing_service_factory(db).record_generation_usage(
                        tenant_id=context.tenant_id,
                        user_id=context.user_id,
                        session_id=None,
                        event_type="dashboard_advice",
                        model_id=model_id,
                        prompt_text="study-dashboard-advice",
                        response_text=str(dashboard["advice"].get("text") or "")[:500],
                    )
                except InsufficientCreditsError:
                    pass
            return dashboard

    @router.get("/study/achievements")
    async def get_study_achievements(
        context: RequestContext = Depends(request_context),
    ) -> dict:
        _require_authenticated(context)
        async with session_scope() as db:
            return await AchievementService(
                db, tenant_id=context.tenant_id, user_id=context.user_id
            ).list_achievements()

    return router
