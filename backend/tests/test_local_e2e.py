import asyncio
import base64

from fastapi.testclient import TestClient

from interview_agent.infrastructure.db.session import create_engine_for_url
from interview_agent.infrastructure.object_storage import LocalObjectStorage
from interview_agent.interfaces.api import create_app


def _register_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": "local-e2e@example.com",
            "password": "passw0rd!",
            "display_name": "Local E2E",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_local_offline_interview_e2e_with_restore_and_orchestration(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("INTERVIEW_AUTH_TOKEN_SECRET", "local-e2e-secret")
    monkeypatch.setenv("INTERVIEW_RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setenv("INTERVIEW_STORAGE_BACKEND", "database")
    monkeypatch.setenv("INTERVIEW_OBJECT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("INTERVIEW_TRIAL_USES", "10")

    engine = create_engine_for_url("sqlite+aiosqlite:///:memory:")
    storage = LocalObjectStorage(root=tmp_path / "objects", bucket="local-e2e")
    app = create_app(object_storage=storage, database_engine=engine)

    try:
        with TestClient(app) as client:
            headers = _register_headers(client)
            resume_text = (
                "# 张三\n\n"
                "5 年 AI 应用工程经验，主导过 RAG、Agent 工具调用、LangChain provider 封装、"
                "LangGraph 状态图编排、评测、监控和灰度上线。"
            )
            encoded_resume = base64.b64encode(resume_text.encode("utf-8")).decode("ascii")
            resume = client.post(
                "/resumes",
                headers=headers,
                json={"filename": "local-e2e-resume.md", "content_base64": encoded_resume},
            )
            assert resume.status_code == 200
            resume_id = resume.json()["id"]

            created = client.post(
                "/sessions",
                headers=headers,
                json={
                    "offline": True,
                    "resume_id": resume_id,
                    "candidate_name": "张三",
                    "target_role": "AI Agent 工程师",
                    "seniority": "高级",
                    "industry": "ai_application",
                    "resume_summary": "主导 RAG 和 Agent 平台生产化。",
                    "project_experience": "负责 LangChain 模型适配和 LangGraph 面试状态图。",
                    "interview_goal": "本地 E2E 验证完整面试链路。",
                    "focus_areas": ["LangChain 与 LangGraph 工程化", "RAG 生产化"],
                },
            )
            assert created.status_code == 200
            created_payload = created.json()
            session_id = created_payload["session_id"]
            assert created_payload["message"]
            assert created_payload["completed"] is False
            assert created_payload["orchestration"]["thread_id"] == session_id
            assert created_payload["orchestration"]["engine"] in {"langgraph", "explicit"}

            message = client.post(
                f"/sessions/{session_id}/messages",
                headers=headers,
                json={
                    "message": (
                        "我负责把 LangChain 的 ChatModel、检索器和 prompt 统一封装，"
                        "再用 LangGraph 拆成 guard_input、assess_answer、generate_next_turn 节点，"
                        "每个节点记录 trace 和耗时，checkpoint 用 session_id 做 thread_id。"
                    )
                },
            )
            assert message.status_code == 200
            message_payload = message.json()
            assert message_payload["session_id"] == session_id
            assert message_payload["turn_index"] >= 2
            assert message_payload["orchestration"]["thread_id"] == session_id
            if message_payload["orchestration"]["engine"] == "langgraph":
                nodes = {event["node"] for event in message_payload["orchestration"]["events"]}
                assert {"route_mode", "guard_input", "assess_answer", "generate_next_turn"} <= nodes

            from interview_agent.interfaces import api as api_module

            api_module.sessions.pop(session_id, None)
            restored = client.post(
                f"/sessions/{session_id}/messages",
                headers=headers,
                json={
                    "message": (
                        "恢复后我继续补充：上线前用 120 条标注集评测召回率和忠实度，"
                        "p95 延迟控制在 800ms，并配置失败降级和回滚。"
                    )
                },
            )
            assert restored.status_code == 200
            restored_payload = restored.json()
            assert restored_payload["session_id"] == session_id
            assert restored_payload["orchestration"]["thread_id"] == session_id

            detail = client.get(f"/sessions/{session_id}", headers=headers)
            assert detail.status_code == 200
            detail_payload = detail.json()
            assert detail_payload["id"] == session_id
            assert len(detail_payload["turns"]) >= 2
    finally:
        asyncio.run(engine.dispose())
