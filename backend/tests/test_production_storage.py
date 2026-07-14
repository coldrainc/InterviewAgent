import base64

import pytest

from interview_agent.core.config import InterviewConfig, InterviewStage
from interview_agent.core.state import InterviewState
from interview_agent.infrastructure.db.models import Base
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.infrastructure.object_storage import LocalObjectStorage
from interview_agent.repositories.interview_repository import InterviewRepository
from interview_agent.services.billing_service import BillingService
from interview_agent.services.interview_persistence_service import InterviewPersistenceService
from interview_agent.services.resume_service import ResumeService


@pytest.mark.asyncio
async def test_resume_service_persists_resume_to_database_and_object_storage(tmp_path):
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        storage = LocalObjectStorage(root=tmp_path / "objects", bucket="test-bucket")
        service = ResumeService(session, storage)
        content = "# 张三\n\nAI 应用工程师\n\n做过 RAG 和 Agent 项目。"
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

        first = await service.save_base64("resume.md", encoded, source_path="/tmp/resume.md")
        second = await service.save_base64("resume.md", encoded, source_path="/tmp/resume.md")
        await session.commit()

        assert first.content_hash == second.content_hash
        assert first.object_bucket == "test-bucket"
        assert first.object_key is not None
        assert (tmp_path / "objects" / "test-bucket" / first.object_key).exists()

    await engine.dispose()


@pytest.mark.asyncio
async def test_billing_usage_idempotency_does_not_double_charge(tmp_path):
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        service = BillingService(session, trial_uses=1)
        first = await service.record_generation_usage(
            tenant_id="default",
            user_id="email:billing@example.com",
            session_id="session-1",
            event_type="turn",
            model_id="gpt-5.4-mini",
            prompt_text="请说明 RAG 的生产链路。",
            response_text="RAG 包含索引构建、召回、重排、上下文注入、评测和监控。",
            idempotency_key="usage:test:session-1:turn:1",
        )
        second = await service.record_generation_usage(
            tenant_id="default",
            user_id="email:billing@example.com",
            session_id="session-1",
            event_type="turn",
            model_id="gpt-5.4-mini",
            prompt_text="请说明 RAG 的生产链路。",
            response_text="RAG 包含索引构建、召回、重排、上下文注入、评测和监控。",
            idempotency_key="usage:test:session-1:turn:1",
        )

        assert first.trial_used is True
        assert second.trial_used is True
        assert second.account.trial_uses_remaining == 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_interview_persistence_writes_turns_and_memory(tmp_path):
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        config = InterviewConfig()
        state = InterviewState(stage=InterviewStage.FOLLOW_UP)
        state.add_interviewer_message(InterviewStage.INTRO, "请设计一个生产级 RAG 系统。")
        state.add_candidate_message(
            "我会负责文档解析、chunk 切分、embedding 向量化、Qdrant 检索、rerank、缓存、权限过滤和监控告警，"
            "上线时用召回率、忠实度、p95 延迟和成本做评估。"
        )
        service = InterviewPersistenceService(
            session,
            export_markdown=True,
            export_root=tmp_path / "conversations",
            memory_root=tmp_path / "memory",
        )

        await service.create_session(session_id="00000000-0000-0000-0000-000000000001", config=config, state=state)
        await service.persist_turn(
            session_id="00000000-0000-0000-0000-000000000001",
            config=config,
            state=state,
            event_type="turn",
            message="继续追问",
            advanced=True,
            fallback_used=False,
            guardrails=[],
        )
        memory = await InterviewRepository(session).list_memory()

        assert memory
        assert "生产级 RAG" in memory[0]
        assert (tmp_path / "conversations" / "00000000-0000-0000-0000-000000000001.md").exists()

    await engine.dispose()
