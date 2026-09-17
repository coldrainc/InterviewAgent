from fastapi import APIRouter

from interview_agent.learning.routes.tasks import router as tasks_router
from interview_agent.learning.routes.today import router as today_router
from interview_agent.learning.routes.planning import router as planning_router
from interview_agent.learning.routes.sync import router as sync_router


def create_learning_router() -> APIRouter:
    router = APIRouter(prefix="/learning", tags=["learning"])
    router.include_router(today_router)
    router.include_router(planning_router)
    router.include_router(tasks_router)
    router.include_router(sync_router)
    return router


__all__ = ["create_learning_router"]
