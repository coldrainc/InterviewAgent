from interview_agent.core.agent_loop import AgentLoop
from interview_agent.core.config import CandidateProfile, InterviewConfig, InterviewMode, InterviewStage
from interview_agent.core.harness import ScriptedInterviewHarness
from interview_agent.core.industry import Industry


def test_agent_loop_reaches_evaluation_after_focus_areas() -> None:
    config = InterviewConfig(
        candidate=CandidateProfile(name="Sam"),
        focus_areas=["python", "system design"],
        max_turns=10,
        max_followups_per_focus=1,
    )
    loop = AgentLoop(config, ScriptedInterviewHarness(config))

    first = loop.start()
    assert first.state.stage == InterviewStage.INTRO
    assert "Sam" in first.message
    assert "最有代表性的 AI 项目" in first.message

    second = loop.step("I worked on a Python service.")
    assert second.state.stage == InterviewStage.FOLLOW_UP

    third = loop.step("I validated it with load tests.")
    assert third.state.stage == InterviewStage.QUESTIONING

    fourth = loop.step("I would shard by tenant.")
    assert fourth.state.stage == InterviewStage.FOLLOW_UP

    final = loop.step("I would measure saturation and error budgets.")
    assert final.state.stage == InterviewStage.EVALUATION
    assert final.state.completed is True


def test_agent_loop_keeps_digging_when_answer_lacks_project_evidence() -> None:
    config = InterviewConfig(
        focus_areas=["简历项目深挖", "RAG 生产化"],
        max_turns=6,
        max_followups_per_focus=3,
    )
    loop = AgentLoop(config, ScriptedInterviewHarness(config))
    loop.start()

    first = loop.step("我做过RAG项目，主要就是把文档放进去然后让模型回答。")
    assert first.state.stage == InterviewStage.FOLLOW_UP

    second = loop.step("就是用了向量检索，效果还可以。")
    assert second.state.stage == InterviewStage.FOLLOW_UP
    assert second.state.current_focus_index == 0


def test_agent_loop_switches_focus_when_answer_has_enough_evidence() -> None:
    config = InterviewConfig(
        focus_areas=["简历项目深挖", "RAG 生产化"],
        max_turns=6,
        max_followups_per_focus=3,
    )
    loop = AgentLoop(config, ScriptedInterviewHarness(config))
    loop.start()
    loop.step(
        "我负责设计 RAG 检索链路，包括 chunk 切分、embedding、BM25 混合检索和 rerank，"
        "上线前用 120 条标注问题评测召回率和忠实度，p95 延迟控制在 800ms 内。"
    )

    result = loop.step(
        "我主导了灰度上线和监控告警，权衡了召回率、延迟和成本，失败时会降级到关键词检索，"
        "并通过日志复盘 badcase。"
    )

    assert result.state.stage == InterviewStage.QUESTIONING
    assert result.state.current_focus_index == 1


def test_agent_loop_accepts_chinese_long_answer_without_spaces() -> None:
    config = InterviewConfig(focus_areas=["RAG"], max_turns=3)
    loop = AgentLoop(config, ScriptedInterviewHarness(config))
    loop.start()

    result = loop.handle_input("我负责设计检索链路并处理权限过滤和上线监控")

    assert result.advanced is True
    assert result.state.turns[0].candidate is not None


def test_agent_loop_respects_max_turns() -> None:
    config = InterviewConfig(focus_areas=["python", "design", "testing"], max_turns=1)
    loop = AgentLoop(config, ScriptedInterviewHarness(config))
    loop.start()

    result = loop.step("I would design the Python service with explicit retries and observability.")

    assert result.state.stage == InterviewStage.EVALUATION
    assert result.state.completed is True


def test_agent_loop_answers_clarifying_question_without_advancing() -> None:
    config = InterviewConfig(focus_areas=["RAG"], max_turns=3)
    loop = AgentLoop(config, ScriptedInterviewHarness(config))
    loop.start()

    result = loop.handle_input("什么是RAG")

    assert result.advanced is False
    assert result.state.stage == InterviewStage.INTRO
    assert len(result.state.turns) == 1
    assert result.state.turns[0].candidate is None


def test_agent_loop_asks_for_more_detail_on_short_input() -> None:
    config = InterviewConfig(focus_areas=["agent loop"], max_turns=3)
    loop = AgentLoop(config, ScriptedInterviewHarness(config))
    loop.start()

    result = loop.handle_input("不知道")

    assert result.advanced is False
    assert "请展开一点" in result.message
    assert len(result.state.turns) == 1


def test_agent_loop_candidate_mode_answers_interviewer_question() -> None:
    config = InterviewConfig(
        mode=InterviewMode.CANDIDATE,
        focus_areas=["互联网行业 RAG 项目"],
        max_turns=3,
    )
    loop = AgentLoop(config, ScriptedInterviewHarness(config))

    first = loop.start()
    assert "被面试候选人模式" in first.message

    result = loop.step("请介绍你做过的 RAG 项目。")

    assert result.advanced is True
    assert result.state.stage == InterviewStage.QUESTIONING
    assert result.state.turns[-1].interviewer == "请介绍你做过的 RAG 项目。"
    assert result.state.turns[-1].candidate is not None
    assert "我的回答是" in result.message


def test_agent_loop_uses_industry_signals_for_depth_assessment() -> None:
    config = InterviewConfig(
        industry=Industry.FINTECH,
        focus_areas=["金融科技 RAG 项目", "合规上线治理"],
        max_turns=6,
        max_followups_per_focus=3,
    )
    loop = AgentLoop(config, ScriptedInterviewHarness(config))
    loop.start()
    loop.step(
        "我负责金融投研 RAG 链路，先做权限隔离和数据脱敏，再用 embedding、BM25 和 rerank 做混合检索，"
        "每条回答都带引用证据和版本号。"
    )

    result = loop.step(
        "我主导上线门禁和审计日志设计，权衡召回率、误报率、SLA 和合规留痕，"
        "通过人工复核通过率和 badcase 复盘验证效果，灰度失败会回滚到关键词检索。"
    )

    assert result.state.stage == InterviewStage.QUESTIONING
    assert result.state.current_focus_index == 1
