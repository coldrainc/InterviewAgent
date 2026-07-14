from interview_agent.core.agent_loop import AgentLoop
from interview_agent.core.config import InterviewConfig
from interview_agent.core.guardrails import HarnessGuardrails
from interview_agent.core.harness import ScriptedInterviewHarness


def test_guardrails_redact_candidate_secret_before_storing() -> None:
    config = InterviewConfig(focus_areas=["安全"])
    guardrails = HarnessGuardrails()
    loop = AgentLoop(config, ScriptedInterviewHarness(config, guardrails=guardrails))
    loop.start()

    result = loop.step("我的方案会用 api_key=super-secret-token 做鉴权，并在服务端隔离权限。")

    assert result.guardrail_findings
    assert result.state.turns[0].candidate is not None
    assert "super-secret-token" not in result.state.turns[0].candidate
    assert "[已脱敏]" in result.state.turns[0].candidate


def test_guardrails_remove_rubric_from_output() -> None:
    guardrails = HarnessGuardrails()

    result = guardrails.check_model_output("这里是回答。\n\n评分标准：technical_depth 最高权重。")

    assert result.repaired is True
    assert "technical_depth" not in result.text
    assert "评分标准已隐藏" in result.text


def test_guardrails_truncate_long_output() -> None:
    guardrails = HarnessGuardrails(max_output_chars=20)

    result = guardrails.check_model_output("这是一个非常非常非常非常非常长的中文回答。")

    assert result.repaired is True
    assert "已自动截断" in result.text
