from interview_agent.infrastructure.telemetry_privacy import REDACTED, sanitize_error_message, sanitize_telemetry


def test_sanitize_telemetry_redacts_nested_user_and_secret_content() -> None:
    payload = {
        "workflow": "evaluation",
        "resume_text": "private resume",
        "cases": [{"question": "secret question", "answer": "private answer", "score": 80}],
        "auth_token": "bearer secret",
        "metrics": {"duration_ms": 12.5, "count": 2},
    }

    sanitized = sanitize_telemetry(payload)

    assert sanitized["workflow"] == "evaluation"
    assert sanitized["resume_text"] == REDACTED
    assert sanitized["cases"][0]["question"] == REDACTED
    assert sanitized["cases"][0]["answer"] == REDACTED
    assert sanitized["auth_token"] == REDACTED
    assert sanitized["metrics"] == {"duration_ms": 12.5, "count": 2}


def test_trace_error_message_never_persists_exception_content() -> None:
    assert sanitize_error_message("provider rejected answer: private response") == (
        "operation failed; inspect server logs with the correlated request or trace id"
    )
