import base64
import hashlib
import hmac
import json
from datetime import timedelta

import pytest

from fastapi.testclient import TestClient

from interview_agent.core.config import InterviewConfig
from interview_agent.domain.resume import StoredResume
from interview_agent.infrastructure.db.models import SecurityEventModel, utcnow
from interview_agent.infrastructure.db.session import create_engine_for_url, session_scope
from interview_agent.infrastructure.security import issue_client_token
from interview_agent.infrastructure.settings import load_settings
from interview_agent.infrastructure.settings import AppSettings
from interview_agent.infrastructure.object_storage import LocalObjectStorage
from interview_agent.interfaces.api import SessionRequest, apply_session_request, create_app


def _register_headers(client: TestClient, email: str = "candidate@example.com") -> dict[str, str]:
    ip_suffix = int(hashlib.sha256(email.encode("utf-8")).hexdigest()[:2], 16)
    response = client.post(
        "/auth/register",
        headers={"X-Forwarded-For": f"198.51.100.{ip_suffix}"},
        json={
            "email": email,
            "password": "passw0rd!",
            "display_name": email.split("@")[0],
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _admin_headers() -> dict[str, str]:
    token, _ = issue_client_token(
        load_settings(),
        tenant_id="default",
        user_id="fixture-admin",
        platform="test",
        role="admin",
    )
    return {"Authorization": f"Bearer {token}"}


def _client_password_derived(email: str, password: str) -> str:
    normalized_email = email.strip().lower()
    normalized_password = password.strip()
    return hashlib.sha256(
        f"interview-agent:password:v1:{normalized_email}\0{normalized_password}".encode("utf-8")
    ).hexdigest()


def test_password_auth_trims_outer_spaces_and_accepts_client_derived(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        raw_registered = client.post(
            "/auth/register",
            json={
                "email": " Spacey@example.com ",
                "password": "  passw0rd!  ",
                "display_name": "Spacey",
            },
        )
        assert raw_registered.status_code == 200, raw_registered.text
        raw_login = client.post(
            "/auth/login",
            json={"email": " spacey@example.com ", "password": "  passw0rd!  "},
        )
        assert raw_login.status_code == 200, raw_login.text
        raw_derived = _client_password_derived("spacey@example.com", "  passw0rd!  ")
        migrated_login = client.post(
            "/auth/login",
            json={
                "email": " spacey@example.com ",
                "password": "  passw0rd!  ",
                "password_derived": raw_derived,
                "password_scheme": "client_sha256_v1",
            },
        )
        assert migrated_login.status_code == 200, migrated_login.text
        derived_only_after_migration = client.post(
            "/auth/login",
            json={
                "email": "spacey@example.com",
                "password_derived": raw_derived,
                "password_scheme": "client_sha256_v1",
            },
        )
        assert derived_only_after_migration.status_code == 200, derived_only_after_migration.text

        derived_email = "derived@example.com"
        derived_password = "  Test123456!  "
        derived_registered = client.post(
            "/auth/register",
            json={
                "email": derived_email,
                "password_derived": _client_password_derived(derived_email, derived_password),
                "password_scheme": "client_sha256_v1",
                "display_name": "Derived",
            },
        )
        assert derived_registered.status_code == 200, derived_registered.text
        derived_login = client.post(
            "/auth/login",
            json={
                "email": f" {derived_email} ",
                "password_derived": _client_password_derived(derived_email, derived_password),
                "password_scheme": "client_sha256_v1",
            },
        )
        assert derived_login.status_code == 200, derived_login.text
        derived_account_raw_login = client.post(
            "/auth/login",
            json={"email": f" {derived_email} ", "password": derived_password},
        )
        assert derived_account_raw_login.status_code == 200, derived_account_raw_login.text

    import asyncio

    asyncio.run(engine.dispose())


def test_login_failed_attempt_limit_is_scoped_to_email_and_ip(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        registered = client.post(
            "/auth/register",
            json={
                "email": "scoped-login@example.com",
                "password": "Test123456!",
                "display_name": "Scoped Login",
            },
        )
        assert registered.status_code == 200, registered.text

        async def seed_other_account_failures() -> None:
            async with session_scope() as db:
                for index in range(8):
                    db.add(
                        SecurityEventModel(
                            tenant_id="default",
                            user_id="email:other-scoped-login@example.com",
                            event_type="login_failed",
                            severity="warning",
                            ip_address="198.51.100.24",
                            created_at=utcnow() - timedelta(minutes=index),
                        )
                    )

        import asyncio

        asyncio.run(seed_other_account_failures())

        blocked_other = client.post(
            "/auth/login",
            headers={"X-Forwarded-For": "198.51.100.24"},
            json={"email": "other-scoped-login@example.com", "password": "wrong"},
        )
        assert blocked_other.status_code == 429, blocked_other.text

        login = client.post(
            "/auth/login",
            headers={"X-Forwarded-For": "198.51.100.24"},
            json={"email": "scoped-login@example.com", "password": "Test123456!"},
        )
        assert login.status_code == 200, login.text

    asyncio.run(engine.dispose())


def test_login_failed_attempt_limit_blocks_same_email_and_ip(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        for _ in range(8):
            failed = client.post(
                "/auth/login",
                headers={"X-Forwarded-For": "198.51.100.25"},
                json={"email": "same-scoped-login@example.com", "password": "wrong"},
            )
            assert failed.status_code == 401, failed.text

        blocked = client.post(
            "/auth/login",
            headers={"X-Forwarded-For": "198.51.100.25"},
            json={"email": "same-scoped-login@example.com", "password": "wrong"},
        )
        assert blocked.status_code == 429, blocked.text

    import asyncio

    asyncio.run(engine.dispose())


def test_refresh_token_rotates_and_rejects_reuse_with_sqlite(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        registered = client.post(
            "/auth/register",
            json={
                "email": "refresh-sqlite@example.com",
                "password": "passw0rd!",
                "display_name": "Refresh SQLite",
            },
        )
        assert registered.status_code == 200
        original = registered.json()["refresh_token"]

        rotated = client.post("/auth/refresh", json={"refresh_token": original})
        assert rotated.status_code == 200, rotated.text
        assert rotated.json()["refresh_token"] != original

        replayed = client.post("/auth/refresh", json={"refresh_token": original})
        assert replayed.status_code == 401

    import asyncio

    asyncio.run(engine.dispose())


def test_apply_session_request_updates_resume_profile() -> None:
    config = InterviewConfig()
    request = SessionRequest(
        candidate_name="张三",
        target_role="AI Agent 工程师",
        seniority="高级",
        resume_summary="5 年后端经验，做过 RAG 和 Agent 平台。",
        resume_text="完整简历内容",
        project_experience="主导知识库问答、评测和上线治理。",
        interview_goal="重点深挖真实项目。",
        focus_areas=["简历项目深挖", "Agent 工具调用"],
    )

    updated = apply_session_request(config, request)

    assert updated.candidate.name == "张三"
    assert updated.candidate.target_role == "AI Agent 工程师"
    assert updated.candidate.resume_text == "完整简历内容"
    assert updated.candidate.project_experience == "主导知识库问答、评测和上线治理。"
    assert updated.candidate.interview_goal == "重点深挖真实项目。"
    assert updated.focus_areas == ["简历项目深挖", "Agent 工具调用"]


def test_stored_resume_is_authoritative_over_client_resume_fields() -> None:
    stored = StoredResume(
        id="owned-resume",
        filename="owned.md",
        file_type="markdown",
        summary="当前用户服务端简历摘要",
        text="当前用户服务端简历正文",
        truncated=False,
        created_at="2026-09-05T00:00:00+00:00",
        updated_at="2026-09-05T00:00:00+00:00",
    )
    request = SessionRequest(
        resume_id="owned-resume",
        resume_summary="客户端伪造的其他用户摘要",
        resume_text="客户端伪造的其他用户正文",
    )

    updated = apply_session_request(InterviewConfig(), request, stored_resume=stored)

    assert updated.candidate.resume_summary == stored.summary
    assert updated.candidate.resume_text == stored.text
    assert "其他用户" not in updated.candidate.resume_text


def test_apply_session_request_ignores_blank_values() -> None:
    config = InterviewConfig()
    request = SessionRequest(candidate_name="  ", target_role="  RAG 工程师  ")

    updated = apply_session_request(config, request)

    assert updated.candidate.name == config.candidate.name
    assert updated.candidate.target_role == "RAG 工程师"


def test_apply_session_request_updates_mode_and_industry() -> None:
    config = InterviewConfig()
    request = SessionRequest(mode="candidate", industry="fintech")

    updated = apply_session_request(config, request)

    assert updated.mode == "candidate"
    assert updated.industry == "fintech"


def test_api_exposes_industry_metadata(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        response = client.get("/metadata/industries?target_role=Agent%20%E5%B7%A5%E7%A8%8B%E5%B8%88")

    assert response.status_code == 200
    payload = response.json()
    values = {item["value"] for item in payload}
    assert {"internet", "ai_application", "ecommerce", "fintech", "enterprise_saas"} <= values
    ai_option = next(item for item in payload if item["value"] == "ai_application")
    assert "Agent 工程师" in " ".join(ai_option["recommended_focus_areas"])
    assert ai_option["production_signals"]

    import asyncio

    asyncio.run(engine.dispose())


def test_practice_categories_include_leetcode_questions(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "leetcode@example.com")
        categories = client.get("/practice/categories", headers=headers)
        canonical = client.get("/practice/questions?category=leetcode&limit=20", headers=headers)
        alias = client.get("/practice/questions?category=%E5%8A%9B%E6%89%A3&limit=20", headers=headers)

    assert categories.status_code == 200
    assert "leetcode" in {item["value"] for item in categories.json()}
    assert canonical.status_code == 200
    assert canonical.json()["total"] == 8
    assert {item["practice_category"] for item in canonical.json()["items"]} == {"leetcode"}
    assert alias.status_code == 200
    assert alias.json()["total"] == canonical.json()["total"]

    import asyncio

    asyncio.run(engine.dispose())


def test_practice_question_pages_prefetch_without_cross_user_leakage(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        owner = _register_headers(client, "paging-owner@example.com")
        other = _register_headers(client, "paging-other@example.com")
        private_prompt = "owner-only-pagination-question-6fbeff5b"
        imported = client.post(
            "/practice/questions/import",
            headers=owner,
            json={
                "questions": [{
                    "prompt": private_prompt,
                    "exam_year": 2026,
                    "practice_category": "leetcode",
                    "question_type": "subjective",
                    "difficulty": "medium",
                    "answer": "owner answer",
                }]
            },
        )
        first = client.get(
            "/practice/questions?category=leetcode&limit=3&offset=0", headers=owner
        )
        second = client.get(
            "/practice/questions?category=leetcode&limit=3&offset=3", headers=owner
        )
        other_first = client.get(
            "/practice/questions?category=leetcode&limit=3&offset=0", headers=other
        )

        owner_all = client.get(
            "/practice/questions?category=leetcode&limit=100&offset=0", headers=owner
        )
        other_all = client.get(
            "/practice/questions?category=leetcode&limit=100&offset=0", headers=other
        )

    assert imported.status_code == 200, imported.text
    assert first.status_code == second.status_code == other_first.status_code == 200
    assert first.json()["has_more"] is True
    assert first.json()["next_offset"] == 3
    assert second.json()["offset"] == 3
    first_ids = {item["id"] for item in first.json()["items"]}
    second_ids = {item["id"] for item in second.json()["items"]}
    assert first_ids.isdisjoint(second_ids)
    assert private_prompt in {item["prompt"] for item in owner_all.json()["items"]}
    assert private_prompt not in {item["prompt"] for item in other_all.json()["items"]}

    import asyncio

    asyncio.run(engine.dispose())


def test_seeded_practice_questions_can_create_training_drill(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "seed-to-drill@example.com")
        seeded = client.post("/practice/questions/seed", headers=headers)
        assert seeded.status_code == 200, seeded.text

        questions = client.get("/review-site/practice-questions", headers=headers)
        assert questions.status_code == 200
        assert questions.json()["total"] > 0

        drill = client.post("/training/drills", headers=headers, json={"count": 3})
        assert drill.status_code == 200, drill.text
        assert drill.json()["question_count"] == 3

    import asyncio

    asyncio.run(engine.dispose())


def test_practice_attempt_grades_choice_question(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "practice-choice@example.com")
        questions = client.get(
            "/practice/questions?category=civil_service&subject=xingce&limit=1",
            headers=headers,
        )
        assert questions.status_code == 200
        question = questions.json()["items"][0]

        correct = client.post(
            "/practice/attempt",
            headers=headers,
            json={"question_id": question["id"], "answer": question["answer"], "elapsed_seconds": 12},
        )
        wrong = client.post(
            "/practice/attempt",
            headers=headers,
            json={"question_id": question["id"], "answer": "A"},
        )

    assert correct.status_code == 200
    assert correct.json()["correct"] is True
    assert correct.json()["score"] == 100
    assert correct.json()["elapsed_seconds"] == 12
    assert wrong.status_code == 200
    if question["answer"] != "A":
        assert wrong.json()["correct"] is False

    import asyncio

    asyncio.run(engine.dispose())


def test_practice_attempt_scores_open_question(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "practice-open@example.com")
        questions = client.get(
            "/practice/questions?category=internet&subject=system_design&limit=1",
            headers=headers,
        )
        assert questions.status_code == 200
        question = questions.json()["items"][0]
        response = client.post(
            "/practice/attempt",
            headers=headers,
            json={
                "question_id": question["id"],
                "answer": "短链服务要考虑短码生成、缓存、限流、监控和降级。",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["correct"] is None
    assert 0 <= payload["score"] <= 100
    assert payload["reference_answer"]
    assert payload["suggestions"]

    import asyncio

    asyncio.run(engine.dispose())


def test_admin_can_create_anonymous_review_fixture_and_save_progress(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _admin_headers()
        imported = client.post("/admin/test-data/review-site", headers=headers)
        assert imported.status_code == 200
        assert imported.json()["plan_count"] == 1

        plans = client.get("/review-site/plans", headers=headers)
        assert plans.status_code == 200
        assert len(plans.json()) == 1
        plan_id = plans.json()[0]["id"]

        plan = client.get(f"/review-site/plans/{plan_id}", headers=headers)
        assert plan.status_code == 200
        payload = plan.json()
        assert payload["title"] == "管理员测试计划"
        assert payload["metadata"]["fixture_kind"] == "admin_test"
        assert len(payload["days"]) == 7
        first_task_id = payload["days"][0]["tasks"][0]["id"]

        progress = client.patch(
            f"/review-site/progress/task/{first_task_id}",
            headers=headers,
            json={"done": True, "elapsed_minutes": 45, "mastery_score": 4, "note": "测试任务已完成"},
        )
        assert progress.status_code == 200
        assert progress.json()["done"] is True
        assert progress.json()["elapsed_minutes"] == 45

        refreshed = client.get(f"/review-site/plans/{plan_id}", headers=headers)
        assert refreshed.status_code == 200
        assert refreshed.json()["progresses"][0]["task_id"] == first_task_id

    import asyncio

    asyncio.run(engine.dispose())


def test_review_plan_response_hides_local_document_links(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "review-doc-owner@example.com")
        created = client.post("/review-site/plans", headers=headers, json={"title": "资料访问测试"})
        assert created.status_code == 200
        plan_id = created.json()["id"]

        updated = client.patch(
            f"/review-site/plans/{plan_id}",
            headers=headers,
            json={
                "source_root": "/Users/example/private/interview",
                "source_documents": ["file:///Users/example/private/interview/codex.md"],
            },
        )
        assert updated.status_code == 200

        day = client.post(
            f"/review-site/plans/{plan_id}/days",
            headers=headers,
            json={"day_key": "day-1", "day_label": "Day 1", "title": "资料日"},
        )
        assert day.status_code == 201
        task = client.post(
            f"/review-site/days/{day.json()['id']}/tasks",
            headers=headers,
            json={
                "task_key": "doc-task",
                "title": "Codex 资料阅读",
                "docs": [{"label": "Codex 文档", "url": "file:///Users/example/private/interview/codex.md"}],
                "link_payload": {
                    "detail": {
                        "materials": [
                            {
                                "label": "Codex 文档",
                                "path": "/Users/example/private/interview/codex.md",
                                "content": "# Codex\n\n任务隔离、上下文和交付闭环。",
                            }
                        ]
                    }
                },
            },
        )
        assert task.status_code == 201

        plan = client.get(f"/review-site/plans/{plan_id}", headers=headers)
        assert plan.status_code == 200
        body = plan.json()
        body_text = json.dumps(body, ensure_ascii=False)
        assert "file://" not in body_text
        assert "/Users/example/private" not in body_text
        assert body["source_root"] == ""
        assert body["source_documents"] == [{"label": "codex.md", "source_index": 0}]
        public_task = body["days"][0]["tasks"][0]
        assert public_task["docs"] == [
            {"label": "Codex 文档", "source_index": 0, "page_url": "/review-site/materials/0"}
        ]
        assert public_task["link_payload"]["detail"]["materials"] == [
            {
                "label": "Codex 文档",
                "source_index": 0,
                "page_url": "/review-site/materials/0",
                "content": "# Codex\n\n任务隔离、上下文和交付闭环。",
            }
        ]

    import asyncio

    asyncio.run(engine.dispose())


def test_regular_user_cannot_create_admin_review_fixture(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "review-site-user@example.com")
        response = client.post("/admin/test-data/review-site", headers=headers)
        assert response.status_code == 403

    import asyncio

    asyncio.run(engine.dispose())


def test_production_rejects_admin_review_fixture(tmp_path, monkeypatch) -> None:
    import interview_agent.interfaces.api as api_module

    production_settings = AppSettings(environment="production")
    monkeypatch.setattr(api_module, "load_settings", lambda: production_settings)
    monkeypatch.setattr(api_module, "validate_production_security", lambda _settings: None)
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)
    token, _ = issue_client_token(
        production_settings,
        tenant_id="default",
        user_id="fixture-admin",
        platform="test",
        role="admin",
    )

    with TestClient(app) as client:
        response = client.post(
            "/admin/test-data/review-site",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    import asyncio

    asyncio.run(engine.dispose())


def test_review_site_generates_custom_plan(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "review-planner@example.com")
        generated = client.post(
            "/review-site/planner/generate",
            headers=headers,
            json={
                "target_role": "AI Native 全栈",
                "seniority": "senior",
                "target_company": "蚂蚁证券",
                "total_days": 7,
                "hours_per_day": 3,
                "focus_areas": ["AI", "项目深挖", "模拟"],
                "template": "7d-sprint",
            },
        )
        assert generated.status_code == 200
        plan_id = generated.json()["plan_id"]

        plan = client.get(f"/review-site/plans/{plan_id}", headers=headers)
        assert plan.status_code == 200
        payload = plan.json()
        assert payload["metadata"]["target_company"] == "蚂蚁证券"
        assert len(payload["days"]) == 7
        assert payload["days"][0]["tasks"]

    import asyncio

    asyncio.run(engine.dispose())


def test_api_resume_endpoints_use_database_storage(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    content = "# 李四\n\n做过 AgentLoop 和 RAG 系统。"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    with TestClient(app) as client:
        headers = _register_headers(client, "resume-owner@example.com")
        response = client.post(
            "/resumes",
            headers=headers,
            json={
                "filename": "resume.md",
                "content_base64": encoded,
                "source_path": "/tmp/resume.md",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["filename"] == "resume.md"

        list_response = client.get("/resumes", headers=headers)
        assert list_response.status_code == 200
        assert list_response.json()[0]["id"] == payload["id"]

    import asyncio

    asyncio.run(engine.dispose())


def test_api_token_auth_and_tenant_isolation(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("INTERVIEW_API_TOKENS", "token-a:tenant_a,token-b:tenant_b")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    content = "# 王五\n\n做过 RAG 系统。"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    with TestClient(app) as client:
        unauthorized = client.get("/resumes")
        assert unauthorized.status_code == 401

        created = client.post(
            "/resumes",
            headers={"Authorization": "Bearer token-a"},
            json={"filename": "resume.md", "content_base64": encoded},
        )
        assert created.status_code == 200
        resume_id = created.json()["id"]

        tenant_b_list = client.get("/resumes", headers={"Authorization": "Bearer token-b"})
        assert tenant_b_list.status_code == 200
        assert tenant_b_list.json() == []

        tenant_b_get = client.get(
            f"/resumes/{resume_id}",
            headers={"Authorization": "Bearer token-b"},
        )
        assert tenant_b_get.status_code == 404

    import asyncio

    asyncio.run(engine.dispose())


def test_api_dev_login_issues_client_token_and_me(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("INTERVIEW_API_TOKENS", "")
    monkeypatch.setenv("INTERVIEW_AUTH_TOKEN_SECRET", "test-secret")
    monkeypatch.setenv("INTERVIEW_AUTH_DEV_LOGIN_ENABLED", "true")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        login = client.post(
            "/auth/dev-login",
            json={
                "user_id": "ios-user",
                "tenant_id": "tenant_ios",
                "display_name": "iOS 用户",
                "platform": "ios",
            },
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        me = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["tenant_id"] == "tenant_ios"
        assert me.json()["user_id"] == "ios-user"
        assert me.json()["platform"] == "ios"
        assert me.json()["authenticated"] is True

    import asyncio

    asyncio.run(engine.dispose())


def test_api_provider_login_requires_real_provider_when_mock_disabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_AUTH_MOCK_PROVIDER_LOGIN_ENABLED", "false")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        response = client.post("/auth/wechat/login", json={"code": "mock-code"})
        assert response.status_code == 501

    import asyncio

    asyncio.run(engine.dispose())


def test_api_session_history_delete_and_restore(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "history@example.com")
        created = client.post("/sessions", headers=headers, json={"offline": True})
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        list_response = client.get("/sessions", headers=headers)
        assert list_response.status_code == 200
        assert list_response.json()[0]["id"] == session_id

        detail = client.get(f"/sessions/{session_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["turns"]

        from interview_agent.interfaces import api as api_module

        api_module.sessions.pop(session_id, None)
        restored_message = client.post(
            f"/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "我负责 RAG 检索、embedding、rerank、监控和灰度上线，p95 延迟控制在 800ms。"},
        )
        assert restored_message.status_code == 200

        deleted = client.delete(f"/sessions/{session_id}", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True

        missing = client.get(f"/sessions/{session_id}", headers=headers)
        assert missing.status_code == 404

    import asyncio

    asyncio.run(engine.dispose())


def test_api_wechat_login_exchanges_code(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("WECHAT_MINIAPP_APP_ID", "wx-app")
    monkeypatch.setenv("WECHAT_MINIAPP_APP_SECRET", "wx-secret")
    monkeypatch.setenv("INTERVIEW_AUTH_TOKEN_SECRET", "test-secret")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"openid": "openid-123", "session_key": "session-key"}

    def fake_get(url, params, timeout):
        assert params["appid"] == "wx-app"
        assert params["secret"] == "wx-secret"
        assert params["js_code"] == "login-code"
        return FakeResponse()

    monkeypatch.setattr("interview_agent.infrastructure.auth_providers.requests.get", fake_get)

    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        response = client.post("/auth/wechat/login", json={"code": "login-code"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["user_id"] == "wechat:openid-123"
        assert payload["platform"] == "miniapp"
        assert payload["access_token"]

    import asyncio

    asyncio.run(engine.dispose())


def test_api_stream_message_returns_sse_events(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "stream@example.com")
        created = client.post("/sessions", headers=headers, json={"offline": True})
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        response = client.post(
            f"/sessions/{session_id}/stream",
            headers=headers,
            json={"message": "我负责 RAG embedding rerank 灰度上线和监控，p95 延迟 800ms。"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        text = response.text
        assert "event: tool.notice" in text
        assert "event: message.done" in text
        assert "session_id" in text

    import asyncio

    asyncio.run(engine.dispose())


def test_api_account_trial_recharge_and_usage_billing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("INTERVIEW_AUTH_TOKEN_SECRET", "billing-secret")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        models = client.get("/metadata/models")
        assert models.status_code == 200
        model_payload = models.json()
        model_ids = {item["id"] for item in model_payload}
        assert "gpt-5.5" in model_ids
        assert "gpt-4o-mini" not in model_ids
        assert "claude-fable-5" in model_ids
        assert "deepseek-chat" not in model_ids
        assert all("runtime_supported" in item for item in model_payload)
        assert all("category" in item for item in model_payload)

        registered = client.post(
            "/auth/register",
            json={
                "email": "candidate@example.com",
                "password": "passw0rd!",
                "display_name": "候选人",
            },
        )
        assert registered.status_code == 200
        token = registered.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert registered.json()["trial_uses_remaining"] == 2

        first = client.post(
            "/sessions",
            headers=headers,
            json={"offline": True, "model_id": "gpt-4o-mini"},
        )
        assert first.status_code == 200
        assert first.json()["usage"]["trial_used"] is True
        assert first.json()["usage"]["trial_uses_remaining"] == 1
        session_id = first.json()["session_id"]

        second = client.post(
            f"/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "我负责 RAG embedding rerank 灰度上线和监控，p95 延迟 800ms，成本下降 30%。"},
        )
        assert second.status_code == 200
        assert second.json()["usage"]["trial_used"] is True
        assert second.json()["usage"]["trial_uses_remaining"] == 0

        blocked = client.post(
            f"/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "我继续补充一次上线复盘，包含监控、回滚和安全治理。"},
        )
        assert blocked.status_code == 402

        recharged = client.post(
            "/account/recharge",
            headers=headers,
            json={"amount_credits": "1.5", "external_order_id": "order-001"},
        )
        assert recharged.status_code == 200
        assert recharged.json()["credit_balance_micros"] == 1_500_000

        paid = client.post(
            f"/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "我继续补充一次上线复盘，包含监控、回滚和安全治理。"},
        )
        assert paid.status_code == 200
        usage = paid.json()["usage"]
        assert usage["trial_used"] is False
        assert usage["cost_credits_micros"] > 0
        assert usage["credit_balance_micros"] < 1_500_000

    import asyncio

    asyncio.run(engine.dispose())


def test_api_rejects_oversized_upload_and_message(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_MAX_UPLOAD_BYTES", "8")
    monkeypatch.setenv("INTERVIEW_MAX_MESSAGE_CHARS", "12")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "limits@example.com")
        upload = client.post(
            "/resumes",
            headers=headers,
            json={
                "filename": "resume.md",
                "content_base64": base64.b64encode(b"this is too long").decode("ascii"),
            },
        )
        assert upload.status_code == 413

        created = client.post("/sessions", headers=headers, json={"offline": True})
        assert created.status_code == 200
        session_id = created.json()["session_id"]

        message = client.post(
            f"/sessions/{session_id}/messages",
            headers=headers,
            json={"message": "这是一段明显超过长度限制的消息"},
        )
        assert message.status_code == 413


def test_api_user_isolation_within_same_tenant(tmp_path) -> None:
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    content = "# 用户 A\n\n负责生产级 RAG。"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    with TestClient(app) as client:
        user_a = _register_headers(client, "user-a@example.com")
        user_b = _register_headers(client, "user-b@example.com")

        created_resume = client.post(
            "/resumes",
            headers=user_a,
            json={"filename": "resume.md", "content_base64": encoded},
        )
        assert created_resume.status_code == 200
        resume_id = created_resume.json()["id"]

        created_session = client.post("/sessions", headers=user_a, json={"offline": True})
        assert created_session.status_code == 200
        session_id = created_session.json()["session_id"]

        assert client.get("/resumes", headers=user_b).json() == []
        assert client.get(f"/resumes/{resume_id}", headers=user_b).status_code == 404
        assert client.get("/sessions", headers=user_b).json() == []
        assert client.get(f"/sessions/{session_id}", headers=user_b).status_code == 404

        forged = client.post(
            "/sessions",
            headers=user_b,
            json={
                "offline": True,
                "resume_id": resume_id,
                "resume_summary": "尝试绑定用户 A 简历",
                "resume_text": content,
            },
        )
        assert forged.status_code == 404
        assert client.get("/sessions", headers=user_b).json() == []

    import asyncio

    asyncio.run(engine.dispose())


def test_api_signed_payment_webhook_applies_and_is_idempotent(monkeypatch, tmp_path) -> None:
    secret = "payment-secret-long-enough"
    monkeypatch.setenv("INTERVIEW_PAYMENT_WEBHOOK_SECRET", secret)
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    payload = {
        "tenant_id": "default",
        "user_id": "email:pay@example.com",
        "amount_credits": "2.5",
        "payment_provider": "stripe",
        "external_order_id": "pay-order-001",
        "status": "paid",
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    with TestClient(app) as client:
        first = client.post(
            "/payments/webhook",
            content=body,
            headers={"X-Payment-Signature": signature, "Content-Type": "application/json"},
        )
        assert first.status_code == 200
        assert first.json()["applied"] is True
        assert first.json()["account"]["credit_balance_micros"] == 2_500_000

        second = client.post(
            "/payments/webhook",
            content=body,
            headers={"X-Payment-Signature": signature, "Content-Type": "application/json"},
        )
        assert second.status_code == 200
        assert second.json()["applied"] is False
        assert second.json()["account"]["credit_balance_micros"] == 2_500_000

    import asyncio

    asyncio.run(engine.dispose())


def test_api_payment_order_requires_webhook_to_credit(monkeypatch, tmp_path) -> None:
    secret = "payment-secret-long-enough"
    monkeypatch.setenv("INTERVIEW_PAYMENT_WEBHOOK_SECRET", secret)
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "order-flow@example.com")
        order = client.post(
            "/payments/orders",
            headers=headers,
            json={
                "amount_credits": "3",
                "payment_provider": "stripe",
                "external_order_id": "pay-order-created-001",
            },
        )
        assert order.status_code == 200
        assert order.json()["status"] == "pending"
        assert order.json()["created"] is True

        account_before = client.get("/account", headers=headers)
        assert account_before.status_code == 200
        assert account_before.json()["credit_balance_micros"] == 0

        payload = {
            "tenant_id": "default",
            "user_id": "email:order-flow@example.com",
            "amount_credits": "3",
            "payment_provider": "stripe",
            "external_order_id": "pay-order-created-001",
            "status": "paid",
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        paid = client.post(
            "/payments/webhook",
            content=body,
            headers={"X-Payment-Signature": signature, "Content-Type": "application/json"},
        )
        assert paid.status_code == 200
        assert paid.json()["applied"] is True
        assert paid.json()["account"]["credit_balance_micros"] == 3_000_000

    import asyncio

    asyncio.run(engine.dispose())


def test_api_payment_webhook_rejects_bad_signature(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_PAYMENT_WEBHOOK_SECRET", "payment-secret-long-enough")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        response = client.post(
            "/payments/webhook",
            json={
                "tenant_id": "default",
                "user_id": "email:pay@example.com",
                "amount_credits": "2.5",
                "payment_provider": "stripe",
                "external_order_id": "pay-order-002",
                "status": "paid",
            },
            headers={"X-Payment-Signature": "bad"},
        )
        assert response.status_code == 401

    import asyncio

    asyncio.run(engine.dispose())


def test_api_manual_recharge_forbidden_when_mock_disabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_ALLOW_MOCK_RECHARGE", "false")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")
    app = create_app(object_storage=storage, database_engine=engine)

    with TestClient(app) as client:
        headers = _register_headers(client, "blocked-recharge@example.com")
        response = client.post(
            "/account/recharge",
            headers=headers,
            json={"amount_credits": "1", "external_order_id": "manual-blocked"},
        )
        assert response.status_code == 403

    import asyncio

    asyncio.run(engine.dispose())


def test_api_production_security_fails_closed(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_ENV", "production")
    monkeypatch.setenv("INTERVIEW_API_AUTH_REQUIRED", "false")
    monkeypatch.setenv("INTERVIEW_AUTH_TOKEN_SECRET", "short")
    monkeypatch.setenv("INTERVIEW_ALLOW_MOCK_RECHARGE", "true")
    monkeypatch.setenv("INTERVIEW_PAYMENT_WEBHOOK_SECRET", "")
    monkeypatch.setenv("INTERVIEW_OBJECT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("INTERVIEW_ALLOWED_ORIGINS", "*")
    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="api-test")

    with pytest.raises(RuntimeError, match="生产安全配置未通过"):
        create_app(object_storage=storage, database_engine=engine)

    import asyncio

    asyncio.run(engine.dispose())

    import asyncio

    asyncio.run(engine.dispose())
