import base64
from pathlib import Path

from interview_agent.infrastructure.resume_store import ResumeStore


def test_resume_store_saves_and_deduplicates_markdown_resume(tmp_path: Path) -> None:
    store = ResumeStore(tmp_path / "resumes")
    content = "# 张三\n\nAI 应用工程师\n\n做过 RAG 和 Agent 项目。"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

    first = store.save_base64("resume.md", encoded, source_path="/tmp/resume.md")
    second = store.save_base64("resume.md", encoded, source_path="/tmp/resume.md")

    assert first.id == second.id
    assert len(store.list()) == 1
    assert store.get(first.id) is not None
    assert "AI 应用工程师" in first.summary
