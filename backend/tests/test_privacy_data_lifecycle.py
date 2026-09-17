from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from interview_agent.infrastructure.db.models import Base, ResumeModel, UserAccountModel
from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.infrastructure.object_storage import LocalObjectStorage
from interview_agent.interviewer.service import InterviewerWorkspaceService
from interview_agent.privacy.deletion_service import DataDeletionService
from interview_agent.privacy.export_service import UserDataExportService
from interview_agent.services.billing_service import BillingService


TENANT = "default"
USER = "privacy-user"


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
async def test_export_is_owned_and_excludes_credentials(db_factory) -> None:
    async with db_factory() as db:
        db.add_all(
            [
                UserAccountModel(
                    tenant_id=TENANT,
                    user_id=USER,
                    email="owner@example.com",
                    password_hash="secret-hash",
                    display_name="Owner",
                ),
                UserAccountModel(
                    tenant_id=TENANT,
                    user_id="other-user",
                    email="other@example.com",
                    password_hash="other-secret",
                    display_name="Other",
                ),
            ]
        )
        await InterviewerWorkspaceService(db, tenant_id=TENANT, user_id=USER).create_kit(
            {"target_role": "Backend Engineer"}
        )
        await InterviewerWorkspaceService(
            db, tenant_id=TENANT, user_id="other-user"
        ).create_kit({"target_role": "Frontend Engineer"})

        exported = await UserDataExportService(
            db, tenant_id=TENANT, user_id=USER
        ).export()
        account = exported["data"]["account"]["user_accounts"][0]
        assert account["email"] == "owner@example.com"
        assert "password_hash" not in account
        kits = exported["data"]["interviewer_training"]["interviewer_kits"]
        assert [item["target_role"] for item in kits] == ["Backend Engineer"]


@pytest.mark.asyncio
async def test_deletion_cooling_off_cancel_and_execute_removes_object(db_factory, tmp_path) -> None:
    storage = LocalObjectStorage(root=tmp_path, bucket="privacy")
    ref = storage.put_bytes("resumes/privacy-user/cv.txt", b"resume", "text/plain")
    async with db_factory() as db:
        account = UserAccountModel(
            tenant_id=TENANT,
            user_id=USER,
            email="owner@example.com",
            password_hash="secret-hash",
            display_name="Owner",
        )
        db.add(account)
        db.add(
            ResumeModel(
                tenant_id=TENANT,
                user_id=USER,
                filename="cv.txt",
                file_type="txt",
                content_hash="hash",
                summary="summary",
                text="resume text",
                object_bucket=ref.bucket,
                object_key=ref.key,
                size_bytes=ref.size_bytes,
            )
        )
        service = DataDeletionService(
            db,
            tenant_id=TENANT,
            user_id=USER,
            object_storage=storage,
        )
        scheduled = await service.schedule(reason="privacy request")
        assert scheduled["status"] == "scheduled"
        with pytest.raises(ValueError, match="cooling-off"):
            await service.execute_if_due()
        cancelled = await service.cancel()
        assert cancelled["status"] == "cancelled"

        scheduled = await service.schedule(reason="confirmed")
        executed = await service.execute_if_due(
            now=datetime.now(timezone.utc) + timedelta(days=8)
        )
        assert executed["status"] == "executed"
        assert not (tmp_path / ref.bucket / ref.key).exists()
        assert await db.scalar(
            select(ResumeModel).where(ResumeModel.user_id == USER)
        ) is None
        await db.refresh(account)
        assert account.status == "deleted"
        assert account.email is None
        assert account.password_hash is None


@pytest.mark.asyncio
async def test_deleted_account_cannot_authenticate_with_retained_password_hash(db_factory) -> None:
    async with db_factory() as db:
        service = BillingService(db)
        account = await service.register_with_password(
            tenant_id=TENANT,
            email="deleted@example.com",
            password="passw0rd!",
            display_name="Deleted",
        )
        account.status = "deleted"
        await db.flush()

        authenticated = await service.authenticate_password(
            tenant_id=TENANT,
            email="deleted@example.com",
            password="passw0rd!",
        )

        assert authenticated is None
