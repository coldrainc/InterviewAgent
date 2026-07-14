import base64

import pytest

from interview_agent.infrastructure.resume_parser import (
    ResumeParseError,
    build_resume_summary,
    parse_resume_base64,
)


def test_parse_markdown_resume_from_base64() -> None:
    content = "# 张三\n\n高级 AI 应用工程师\n\n## 项目\n\n主导 RAG 知识库和 Agent 工具调用平台。"
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")

    parsed = parse_resume_base64("resume.md", encoded)

    assert parsed.file_type == "markdown"
    assert "高级 AI 应用工程师" in parsed.text
    assert "主导 RAG" in parsed.summary


def test_parse_resume_rejects_unsupported_file_type() -> None:
    encoded = base64.b64encode(b"hello").decode("ascii")

    with pytest.raises(ResumeParseError):
        parse_resume_base64("resume.docx", encoded)


def test_build_resume_summary_uses_first_meaningful_lines() -> None:
    summary = build_resume_summary("\n# 李四\n\n- AI Agent 工程师\n\n负责评测、上线和安全治理。\n")

    assert "李四" in summary
    assert "AI Agent 工程师" in summary
    assert "负责评测" in summary
