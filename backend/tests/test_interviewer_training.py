from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from interview_agent.infrastructure.db.models import Base
from interview_agent.core.state import InterviewState
from interview_agent.interfaces.cli import load_config
from interview_agent.repositories.interview_repository import InterviewRepository
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.interviewer.service import InterviewerWorkspaceService
from interview_agent.repositories.practice_question_repository import PracticeQuestionRepository
from interview_agent.training.drill_service import TrainingDrillService
from interview_agent.training.spaced_review_service import SpacedReviewService

TENANT = "default"
USER = "phase4-user"


@pytest_asyncio.fixture
async def db_factory():
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_interviewer_kit_edit_and_evidence_are_versioned_and_idempotent(db_factory) -> None:
    async with db_factory() as db:
        service = InterviewerWorkspaceService(db, tenant_id=TENANT, user_id=USER)
        kit = await service.create_kit({"target_role": "Backend Engineer", "duration_minutes": 45})
        assert len(kit["questions"]) == 3
        questions = [{**item, "text": f"Q{index + 1}: {item['text']}"} for index, item in enumerate(kit["questions"])]
        updated = await service.update_questions(kit["id"], questions, expected_version=1)
        assert updated["version"] == 2
        assert updated["questions"][0]["text"].startswith("Q1")

        payload = {
            "client_key": "evidence-one",
            "dimension": updated["dimensions"][0],
            "signal": "positive",
            "note": "给出了量化结果",
        }
        first = await service.add_evidence(kit["id"], payload)
        replay = await service.add_evidence(kit["id"], payload)
        assert first["id"] == replay["id"]


@pytest.mark.asyncio
async def test_kit_and_evidence_session_are_isolated_by_owner(db_factory) -> None:
    async with db_factory() as db:
        owner = InterviewerWorkspaceService(db, tenant_id=TENANT, user_id=USER)
        kit = await owner.create_kit({"target_role": "Backend Engineer"})
        with pytest.raises(LookupError):
            await InterviewerWorkspaceService(
                db, tenant_id=TENANT, user_id="another-user"
            ).require_owned_kit(kit["id"])
        with pytest.raises(LookupError):
            await owner.require_owned_kit("not-a-uuid")

        config = load_config(None)
        session_id = "ad6147d0-f1ca-4c73-bb41-7ec8bb58999a"
        await InterviewRepository(db, tenant_id=TENANT, user_id=USER).create_session(
            session_id=session_id,
            config=config,
            state=InterviewState(),
            interviewer_kit_id=kit["id"],
        )
        linked = await owner.add_evidence(
            kit["id"],
            {
                "client_key": "linked-evidence",
                "session_id": session_id,
                "dimension": kit["dimensions"][0],
                "note": "来自当前题纲对应的面试会话",
            },
        )
        assert linked["session_id"] == session_id

        other_kit = await owner.create_kit({"target_role": "Frontend Engineer"})
        with pytest.raises(ValueError, match="not linked"):
            await owner.add_evidence(
                other_kit["id"],
                {
                    "session_id": session_id,
                    "dimension": other_kit["dimensions"][0],
                    "note": "不应允许跨题纲绑定",
                },
            )


@pytest.mark.asyncio
async def test_specialized_drill_and_spaced_review_progression(db_factory) -> None:
    async with db_factory() as db:
        repo = PracticeQuestionRepository(db, tenant_id=TENANT, user_id=USER)
        question, _ = await repo.upsert_question(
            practice_category="internet",
            subject="system_design",
            prompt="Design a rate limiter",
            answer="token bucket",
            difficulty="hard",
        )
        drill = await TrainingDrillService(db, tenant_id=TENANT, user_id=USER).create(
            focus="system_design", count=5
        )
        assert drill["question_count"] == 1
        assert drill["questions"][0]["id"] == question["id"]

        await repo.touch_wrong_entry(question_id=question["id"], is_correct=False)
        reviews = SpacedReviewService(db, tenant_id=TENANT, user_id=USER)
        assert (await reviews.sync_wrong_book())["created"] == 1
        assert (await reviews.sync_wrong_book())["created"] == 0
        due = await reviews.due(now=datetime.now(timezone.utc))
        assert due["total"] == 1
        graded = await reviews.grade(due["items"][0]["id"], 5)
        assert graded["repetitions"] == 1
        assert graded["interval_days"] == 1
