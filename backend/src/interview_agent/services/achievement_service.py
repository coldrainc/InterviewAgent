"""成就引擎：基于学习事件幂等评估并解锁成就。

规则覆盖面试、打卡 streak、刷题、错题本、计划完成、自我介绍专项练习。
评估方法只读聚合当前状态后比对阈值，已解锁成就靠 (tenant, user, key)
唯一约束 + 预查保证幂等，可在任意事件后安全重复调用。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from interview_agent.infrastructure.db.models import (
    InterviewReportModel,
    InterviewSessionModel,
    PracticeAttemptModel,
    PracticeQuestionModel,
    ReviewPlanModel,
    ReviewProgressModel,
    ReviewTaskModel,
    UserAchievementModel,
)
from interview_agent.repositories.practice_question_repository import PracticeQuestionRepository
from interview_agent.repositories.review_checkin_repository import ReviewCheckinRepository

logger = logging.getLogger(__name__)


ACHIEVEMENT_RULES: list[dict[str, Any]] = [
    {
        "key": "first_interview",
        "title": "初次登台",
        "description": "完成第一场模拟面试",
        "icon": "Mic",
        "category": "interview",
        "goal": 1,
        "metric": "interview_count",
    },
    {
        "key": "first_report",
        "title": "首份战报",
        "description": "生成第一份面试评估报告",
        "icon": "FileText",
        "category": "interview",
        "goal": 1,
        "metric": "report_count",
    },
    {
        "key": "streak_7",
        "title": "七日坚持",
        "description": "连续打卡满 7 天",
        "icon": "Flame",
        "category": "streak",
        "goal": 7,
        "metric": "longest_streak",
    },
    {
        "key": "streak_30",
        "title": "月度达人",
        "description": "连续打卡满 30 天",
        "icon": "Trophy",
        "category": "streak",
        "goal": 30,
        "metric": "longest_streak",
    },
    {
        "key": "practice_50",
        "title": "刷题新手",
        "description": "累计作答 50 道题",
        "icon": "PenLine",
        "category": "practice",
        "goal": 50,
        "metric": "total_attempts",
    },
    {
        "key": "practice_100",
        "title": "刷题达人",
        "description": "累计作答 100 道题",
        "icon": "PencilRuler",
        "category": "practice",
        "goal": 100,
        "metric": "total_attempts",
    },
    {
        "key": "wrong_book_clear",
        "title": "错题清零",
        "description": "错题本中的题目全部攻克",
        "icon": "ShieldCheck",
        "category": "practice",
        "goal": 1,
        "metric": "wrong_book_cleared",
    },
    {
        "key": "plan_completed",
        "title": "计划通关",
        "description": "完成一个复习计划的全部任务",
        "icon": "CheckCircle2",
        "category": "plan",
        "goal": 1,
        "metric": "plan_completed_count",
    },
    {
        "key": "intro_10",
        "title": "自我介绍大师",
        "description": "完成 10 次自我介绍专项练习",
        "icon": "Sparkles",
        "category": "interview",
        "goal": 10,
        "metric": "intro_practice_count",
    },
]


class AchievementService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        user_id: str,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id

    async def evaluate(self) -> list[str]:
        """评估所有规则，幂等写入新成就；返回本次新解锁的成就 key 列表。"""
        try:
            metrics = await self._collect_metrics()
            existing = await self._existing_keys()
            unlocked: list[str] = []
            for rule in ACHIEVEMENT_RULES:
                if rule["key"] in existing:
                    continue
                value = metrics.get(rule["metric"], 0) or 0
                if value >= rule["goal"]:
                    await self._unlock(rule, metrics)
                    unlocked.append(rule["key"])
            return unlocked
        except Exception:
            logger.exception("achievement evaluation failed")
            return []

    async def list_achievements(self) -> dict[str, Any]:
        """返回成就清单（含未解锁进度）与汇总；调用时顺带执行一次评估。"""
        await self.evaluate()
        metrics = await self._collect_metrics()
        result = await self.session.execute(
            select(UserAchievementModel).where(
                UserAchievementModel.tenant_id == self.tenant_id,
                UserAchievementModel.user_id == self.user_id,
            )
        )
        unlocked_map = {
            model.achievement_key: model.unlocked_at for model in result.scalars().all()
        }
        items = []
        unlocked_count = 0
        for rule in ACHIEVEMENT_RULES:
            unlocked_at = unlocked_map.get(rule["key"])
            if unlocked_at is not None:
                unlocked_count += 1
            value = metrics.get(rule["metric"], 0) or 0
            items.append({
                "key": rule["key"],
                "title": rule["title"],
                "description": rule["description"],
                "icon": rule["icon"],
                "category": rule["category"],
                "goal": rule["goal"],
                "progress": min(int(value), rule["goal"]),
                "unlocked": unlocked_at is not None,
                "unlocked_at": unlocked_at.isoformat() if unlocked_at else None,
            })
        return {
            "achievements": items,
            "unlocked_count": unlocked_count,
            "total_count": len(ACHIEVEMENT_RULES),
            "metrics": metrics,
        }

    async def _unlock(self, rule: dict[str, Any], metrics: dict[str, Any]) -> None:
        model = UserAchievementModel(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            achievement_key=rule["key"],
            metadata_json={
                "title": rule["title"],
                "description": rule["description"],
                "icon": rule["icon"],
                "category": rule["category"],
                "metric": rule["metric"],
                "value": metrics.get(rule["metric"], 0),
                "goal": rule["goal"],
            },
        )
        try:
            async with self.session.begin_nested():  # 唯一约束冲突时仅回滚 savepoint
                self.session.add(model)
        except Exception:
            logger.debug("achievement %s already unlocked", rule["key"])

    async def _existing_keys(self) -> set[str]:
        result = await self.session.execute(
            select(UserAchievementModel.achievement_key).where(
                UserAchievementModel.tenant_id == self.tenant_id,
                UserAchievementModel.user_id == self.user_id,
            )
        )
        return {row[0] for row in result.all()}

    async def _collect_metrics(self) -> dict[str, int]:
        interview_count = await self._scalar(
            select(func.count()).select_from(InterviewSessionModel).where(
                InterviewSessionModel.tenant_id == self.tenant_id,
                InterviewSessionModel.user_id == self.user_id,
                InterviewSessionModel.status == "completed",
            )
        )
        report_count = await self._scalar(
            select(func.count()).select_from(InterviewReportModel).where(
                InterviewReportModel.tenant_id == self.tenant_id,
                InterviewReportModel.user_id == self.user_id,
            )
        )
        streak = await ReviewCheckinRepository(
            self.session, tenant_id=self.tenant_id, user_id=self.user_id
        ).compute_streak()
        practice_overview = await PracticeQuestionRepository(
            self.session, tenant_id=self.tenant_id, user_id=self.user_id
        ).attempt_overview()
        wrong_overview = await PracticeQuestionRepository(
            self.session, tenant_id=self.tenant_id, user_id=self.user_id
        ).wrong_book_overview()
        plan_completed_count = await self._count_completed_plans()
        intro_practice_count = await self._count_intro_practice()

        wrong_total = int(wrong_overview.get("total", 0))
        wrong_left = int(wrong_overview.get("wrong_count", 0))
        return {
            "interview_count": int(interview_count or 0),
            "report_count": int(report_count or 0),
            "longest_streak": int(streak.get("longest_streak", 0) or 0),
            "current_streak": int(streak.get("current_streak", 0) or 0),
            "total_attempts": int(practice_overview.get("total_attempts", 0) or 0),
            "wrong_book_cleared": 1 if wrong_total > 0 and wrong_left == 0 else 0,
            "plan_completed_count": plan_completed_count,
            "intro_practice_count": intro_practice_count,
        }

    async def _count_completed_plans(self) -> int:
        result = await self.session.execute(
            select(ReviewPlanModel.id).where(
                ReviewPlanModel.tenant_id == self.tenant_id,
                ReviewPlanModel.user_id == self.user_id,
            )
        )
        plan_ids = [row[0] for row in result.all()]
        completed = 0
        for plan_id in plan_ids:
            total = await self._scalar(
                select(func.count()).select_from(ReviewTaskModel).where(
                    ReviewTaskModel.plan_id == plan_id,
                    ReviewTaskModel.tenant_id == self.tenant_id,
                    ReviewTaskModel.user_id == self.user_id,
                )
            )
            if not total:
                continue
            done = await self._scalar(
                select(func.count())
                .select_from(ReviewProgressModel)
                .where(
                    ReviewProgressModel.plan_id == plan_id,
                    ReviewProgressModel.tenant_id == self.tenant_id,
                    ReviewProgressModel.user_id == self.user_id,
                    ReviewProgressModel.done.is_(True),
                )
            )
            if done and done >= total:
                completed += 1
        return completed

    async def _count_intro_practice(self) -> int:
        # 自我介绍类题目作答（题库 question_type=自我介绍）
        attempt_count = await self._scalar(
            select(func.count())
            .select_from(PracticeAttemptModel)
            .join(
                PracticeQuestionModel,
                PracticeQuestionModel.id == PracticeAttemptModel.question_id,
            )
            .where(
                PracticeAttemptModel.tenant_id == self.tenant_id,
                PracticeAttemptModel.user_id == self.user_id,
                PracticeQuestionModel.question_type == "自我介绍",
            )
        )
        # 自我介绍专项模拟面试（config.focus_areas 含“自我介绍”）
        session_count = await self._scalar(
            select(func.count()).select_from(InterviewSessionModel).where(
                InterviewSessionModel.tenant_id == self.tenant_id,
                InterviewSessionModel.user_id == self.user_id,
                InterviewSessionModel.status == "completed",
                cast(InterviewSessionModel.config_json, String).like("%自我介绍%"),
            )
        )
        return int(attempt_count or 0) + int(session_count or 0)

    async def _scalar(self, stmt) -> int:
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)


async def safe_evaluate(session: AsyncSession, *, tenant_id: str, user_id: str) -> list[str]:
    """事件钩子用：成就评估失败不影响主流程。"""
    try:
        return await AchievementService(session, tenant_id=tenant_id, user_id=user_id).evaluate()
    except Exception:
        logger.exception("safe_evaluate failed")
        return []
