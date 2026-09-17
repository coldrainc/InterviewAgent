from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.learning.command_service import LearningCommandService
from interview_agent.services.study_dashboard_service import AdviceProvider, StudyDashboardService


class LearningTodayService:
    """Product read model for the Today workspace.

    The old dashboard remains a data source during the dual-read migration. Tasks are
    re-projected from the formal ledger so clients receive versions and durable state.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: str = "default",
        user_id: str = "anonymous",
        advice_provider: AdviceProvider | None = None,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.dashboard = StudyDashboardService(
            session,
            tenant_id=tenant_id,
            user_id=user_id,
            advice_provider=advice_provider,
        )
        self.commands = LearningCommandService(session, tenant_id=tenant_id, user_id=user_id)

    async def get_today(self, *, today: date | None = None) -> dict[str, Any]:
        result = await self.dashboard.build_dashboard(today=today)
        task_summaries = list((result.get("today") or {}).get("tasks") or [])
        projected = []
        for summary in task_summaries:
            task = await self.commands.task_view(str(summary["id"]))
            if not task.get("deferred"):
                projected.append(task)
        if result.get("today") is not None:
            result["today"]["tasks"] = projected
            result["today"]["total_tasks"] = len(projected)
            result["today"]["tasks_done"] = sum(1 for task in projected if task.get("done"))
        result["next_best_action"] = self._next_best_action(result)
        result["risks"] = self._risks(result)
        result["contract_version"] = "learning.today.v1"
        return result

    @staticmethod
    def _next_best_action(result: dict[str, Any]) -> dict[str, Any]:
        tasks = list((result.get("today") or {}).get("tasks") or [])
        actionable = next((task for task in tasks if task.get("status") != "completed"), None)
        if actionable:
            return {
                "kind": "task",
                "task_id": actionable["id"],
                "title": actionable["title"],
                "reason": actionable.get("reason") or "优先完成今日计划中尚未验证的任务",
                "action": actionable["primary_action"],
            }
        return {
            "kind": "interview",
            "task_id": None,
            "title": "完成一次轻量模拟面试",
            "reason": "今日计划已完成，用一次短模拟保持表达手感",
            "action": {"command": "start_interview", "label": "开始模拟"},
        }

    @staticmethod
    def _risks(result: dict[str, Any]) -> list[dict[str, str]]:
        risks: list[dict[str, str]] = []
        today = result.get("today") or {}
        blocked = [task for task in today.get("tasks") or [] if task.get("status") == "blocked"]
        if blocked:
            risks.append({"code": "blocked_tasks", "level": "warning", "message": f"{len(blocked)} 个任务缺少完成证据"})
        if not (result.get("plan") or {}).get("active_plan_id"):
            risks.append({"code": "no_active_plan", "level": "info", "message": "尚未激活学习计划"})
        return risks
