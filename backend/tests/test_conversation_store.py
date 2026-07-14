from pathlib import Path

from interview_agent.core.config import InterviewConfig, InterviewStage
from interview_agent.infrastructure.conversation_store import ConversationStore, memory_decision
from interview_agent.core.state import InterviewState


def test_conversation_store_saves_transcript_and_memory(tmp_path: Path) -> None:
    store = ConversationStore(
        root=tmp_path / "conversations",
        memory_root=tmp_path / "memory",
    )
    config = InterviewConfig()
    state = InterviewState(stage=InterviewStage.FOLLOW_UP)
    state.add_interviewer_message(InterviewStage.INTRO, "请设计 AgentLoop。")
    state.add_candidate_message(
        "我会维护会话状态、工具调用记录、失败重试次数和终止条件，并用监控指标观察循环是否失控。"
    )

    store.save_state(config, state)

    assert store.markdown_path.exists()
    assert store.memory_path.exists()
    assert "请设计 AgentLoop" in store.markdown_path.read_text(encoding="utf-8")
    assert "历史面试问答" in store.memory_path.read_text(encoding="utf-8")


def test_memory_filters_low_value_turns() -> None:
    state = InterviewState(stage=InterviewStage.FOLLOW_UP)
    state.add_interviewer_message(InterviewStage.INTRO, "请设计 AgentLoop。")
    state.add_candidate_message("不知道")

    decision = memory_decision(state.turns[0])

    assert decision.keep is False


def test_memory_filters_clarifying_questions() -> None:
    state = InterviewState(stage=InterviewStage.FOLLOW_UP)
    state.add_interviewer_message(InterviewStage.INTRO, "请设计 RAG。")
    state.add_candidate_message("什么是 RAG？可以解释一下吗？")

    decision = memory_decision(state.turns[0])

    assert decision.keep is False


def test_memory_keeps_substantive_technical_answer() -> None:
    state = InterviewState(stage=InterviewStage.FOLLOW_UP)
    state.add_interviewer_message(InterviewStage.INTRO, "请设计 RAG。")
    state.add_candidate_message(
        "我会先构建离线索引链路，包括文档解析、chunk 切分、embedding 向量化和 metadata 权限控制；"
        "在线查询时使用混合检索、rerank 和缓存，并用召回率、忠实度和延迟监控效果。"
    )

    decision = memory_decision(state.turns[0])

    assert decision.keep is True
