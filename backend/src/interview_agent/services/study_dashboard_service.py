"""学习驾驶舱聚合服务：streak/今日任务/时长/面试/刷题/计划完成率/薄弱点/AI 建议。"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.repositories.interview_report_repository import InterviewReportRepository
from interview_agent.repositories.practice_question_repository import PracticeQuestionRepository
from interview_agent.repositories.review_checkin_repository import ReviewCheckinRepository
from interview_agent.repositories.review_site_repository import ReviewSiteRepository
from interview_agent.services.interview_report_service import InterviewReportService
from interview_agent.services.review_checkin_service import ReviewCheckinService

logger = logging.getLogger(__name__)

AdviceProvider = Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]]


class StudyDashboardService:
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
        self.advice_provider = advice_provider
        self.review_repo = ReviewSiteRepository(session, tenant_id=tenant_id, user_id=user_id)
        self.checkin_repo = ReviewCheckinRepository(session, tenant_id=tenant_id, user_id=user_id)
        self.practice_repo = PracticeQuestionRepository(session, tenant_id=tenant_id, user_id=user_id)
        self.report_repo = InterviewReportRepository(session, tenant_id=tenant_id, user_id=user_id)

    async def build_dashboard(self, *, today: date | None = None) -> dict[str, Any]:
        target = today or date.today()
        week_start = target - timedelta(days=6)
        today_start = datetime(target.year, target.month, target.day, tzinfo=timezone.utc)

        streak = await self.checkin_repo.compute_streak(today=target)
        plan_block = await self._plan_block(target)
        minutes_block = await self._minutes_block(target, week_start)
        interview_block = await self._interview_block()
        practice_block = await self._practice_block(today_start, week_start)
        weak_points = await self._weak_points()

        snapshot = {
            "date": target.isoformat(),
            "streak": streak,
            "today": plan_block.get("today"),
            "study_minutes": minutes_block,
            "interviews": interview_block,
            "practice": practice_block,
            "plan": plan_block.get("plan"),
            "weak_points": weak_points,
        }
        snapshot["advice"] = await self._advice(snapshot)
        return snapshot

    async def _plan_block(self, target: date) -> dict[str, Any]:
        plans = await self.review_repo.list_plans(include_archived=False)
        active = next((plan for plan in plans if plan.status == "active"), None)
        if active is None:
            return {
                "plan": {
                    "active_plan_id": None,
                    "active_plan_title": None,
                    "completion_rate": 0.0,
                    "tasks_done": 0,
                    "total_tasks": 0,
                },
                "today": {
                    "plan_id": None,
                    "tasks_done": 0,
                    "total_tasks": 0,
                    "elapsed_minutes": 0,
                    "tasks": [],
                },
            }
        days = await self.review_repo.list_days(active.id, with_tasks=True)
        progresses = await self.review_repo.list_progresses(active.id)
        done_ids = {p.task_id for p in progresses if p.done}
        total_tasks = sum(len(day.tasks or []) for day in days)
        tasks_done = sum(1 for day in days for task in (day.tasks or []) if task.id in done_ids)
        today_view = await ReviewCheckinService(
            self.session, tenant_id=self.tenant_id, user_id=self.user_id
        ).get_today(str(active.id), today=target)
        return {
            "plan": {
                "active_plan_id": str(active.id),
                "active_plan_title": active.title,
                "completion_rate": round(tasks_done / total_tasks, 3) if total_tasks else 0.0,
                "tasks_done": tasks_done,
                "total_tasks": total_tasks,
            },
            "today": {
                "plan_id": str(active.id),
                "plan_title": active.title,
                "day": today_view.get("day"),
                "tasks_done": today_view["summary"]["tasks_done"],
                "total_tasks": today_view["summary"]["total_tasks"],
                "elapsed_minutes": today_view["summary"]["elapsed_minutes"],
                "tasks": today_view.get("tasks", []),
            },
        }

    async def _minutes_block(self, target: date, week_start: date) -> dict[str, Any]:
        checkins = await self.checkin_repo.list_checkins(date_from=week_start, date_to=target)
        week_minutes = sum(item.elapsed_minutes for item in checkins)
        today_minutes = sum(item.elapsed_minutes for item in checkins if item.checkin_date == target)
        all_checkins = await self.checkin_repo.list_checkins()
        total_minutes = sum(item.elapsed_minutes for item in all_checkins)

        week_start_dt = datetime(week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc)
        today_start = datetime(target.year, target.month, target.day, tzinfo=timezone.utc)
        overview = await self.practice_repo.attempt_overview(since=week_start_dt)
        today_overview = await self.practice_repo.attempt_overview(since=today_start)
        return {
            "today_minutes": today_minutes + today_overview["since_elapsed_seconds"] // 60,
            "week_minutes": week_minutes + overview["since_elapsed_seconds"] // 60,
            "total_minutes": total_minutes + overview["elapsed_seconds_total"] // 60,
        }

    async def _interview_block(self) -> dict[str, Any]:
        service = InterviewReportService(self.session, tenant_id=self.tenant_id, user_id=self.user_id)
        result = await service.list_reports(limit=50)
        reports = result["reports"]
        trend = result["trend"]
        return {
            "total_reports": trend.get("total_reports", 0),
            "scored_reports": trend.get("scored_reports", 0),
            "latest_score": trend.get("latest_score"),
            "average_score": trend.get("average_score"),
            "recent_average": trend.get("recent_average"),
            "latest_report_id": reports[0]["id"] if reports else None,
        }

    async def _practice_block(self, today_start: datetime, week_start: date) -> dict[str, Any]:
        overview = await self.practice_repo.attempt_overview(since=today_start)
        week_start_dt = datetime(week_start.year, week_start.month, week_start.day, tzinfo=timezone.utc)
        week_overview = await self.practice_repo.attempt_overview(since=week_start_dt)
        wrong = await self.practice_repo.wrong_book_overview()
        return {
            "total_attempts": overview["total_attempts"],
            "correct_rate": overview["correct_rate"],
            "today_attempts": overview["since_attempts"],
            "week_attempts": week_overview["since_attempts"],
            "wrong_book_count": wrong["wrong_count"],
            "mastered_count": wrong["mastered_count"],
        }

    async def _weak_points(self) -> list[dict[str, Any]]:
        counter: Counter[str] = Counter()
        sources: dict[str, str] = {}
        reports = await self.report_repo.list_reports(limit=20)
        for report in reports:
            for tag in report.get("weakness_tags") or []:
                label = str(tag).strip()
                if label:
                    counter[label] += 1
                    sources.setdefault(label, "report")
        wrong_entries = await self.practice_repo.list_wrong_book(mark_type="wrong", limit=200)
        for entry in wrong_entries:
            question = entry.get("question") or {}
            label = str(
                question.get("subject")
                or question.get("practice_category")
                or entry.get("practice_category")
                or ""
            ).strip()
            if label:
                counter[label] += 1
                sources.setdefault(label, "wrong_book")
        return [
            {"tag": tag, "count": count, "source": sources.get(tag, "report")}
            for tag, count in counter.most_common(3)
        ]

    async def _advice(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        if self.advice_provider is not None:
            try:
                llm_advice = await self.advice_provider(snapshot)
                if llm_advice and llm_advice.get("text"):
                    return {
                        "text": str(llm_advice["text"])[:300],
                        "action": str(llm_advice.get("action") or "")[:200],
                        "source": "llm",
                    }
            except Exception:  # noqa: BLE001 - LLM 建议失败降级规则文案
                logger.exception("dashboard llm advice failed, fallback to rule")
        return self._rule_advice(snapshot)

    @staticmethod
    def _rule_advice(snapshot: dict[str, Any]) -> dict[str, Any]:
        streak = snapshot["streak"]
        today = snapshot["today"] or {}
        interviews = snapshot["interviews"]
        practice = snapshot["practice"]
        weak_points = snapshot["weak_points"]

        if interviews["total_reports"] == 0 and practice["total_attempts"] == 0:
            return {
                "text": "欢迎开始备考：先完成一场模拟面试或一组刷题，让系统为你定位水平。",
                "action": "去模拟面试",
                "source": "rule",
            }
        if today.get("total_tasks", 0) > 0 and today.get("tasks_done", 0) < today["total_tasks"]:
            remaining = today["total_tasks"] - today["tasks_done"]
            return {
                "text": f"今天还有 {remaining} 个复习任务未完成，先打卡保持连续 {streak['current_streak']} 天的记录。",
                "action": "完成今日任务",
                "source": "rule",
            }
        if weak_points:
            top = weak_points[0]
            return {
                "text": f"最近评估显示「{top['tag']}」是你的高频薄弱项，建议今天针对性刷 2-3 道相关题目。",
                "action": f"专攻{top['tag']}",
                "source": "rule",
            }
        if streak["current_streak"] == 0:
            return {
                "text": "昨天没有学习记录，今天从 15 分钟轻量任务开始恢复节奏。",
                "action": "今日打卡",
                "source": "rule",
            }
        return {
            "text": "今天的任务已完成，可以加一场模拟面试保持手感。",
            "action": "加练模拟面试",
            "source": "rule",
        }
