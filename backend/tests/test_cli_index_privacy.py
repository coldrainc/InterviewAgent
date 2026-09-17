from __future__ import annotations

import json

from typer.testing import CliRunner

from interview_agent.interfaces.cli import app


runner = CliRunner()


def test_index_defaults_to_public_knowledge_only(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "public.md").write_text("# Public\n\nShared interview guidance.", encoding="utf-8")
    memory = tmp_path / ".interview_agent" / "memory"
    memory.mkdir(parents=True)
    (memory / "private.md").write_text("OTHER_USER_PRIVATE_RESUME", encoding="utf-8")
    output = tmp_path / "index.json"

    result = runner.invoke(
        app,
        ["index", "--knowledge-base", str(knowledge), "--output", str(output), "--no-embeddings"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "Shared interview guidance" in serialized
    assert "OTHER_USER_PRIVATE_RESUME" not in serialized


def test_index_rejects_private_memory_flag(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / "public.md").write_text("# Public", encoding="utf-8")

    result = runner.invoke(
        app,
        ["index", "--knowledge-base", str(knowledge), "--include-memory"],
    )

    assert result.exit_code != 0
    assert "不能加入共享 RAG 索引" in result.output
