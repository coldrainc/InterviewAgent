from __future__ import annotations

import pytest

from interview_agent.learning.errors import IdempotencyConflictError, VersionConflictError
from interview_agent.learning.observability import learning_command_metrics, observe_learning_command


@pytest.fixture(autouse=True)
def reset_metrics():
    learning_command_metrics.reset()
    yield
    learning_command_metrics.reset()


class StubCommands:
    @observe_learning_command
    async def execute(self, *, action: str, result: str):
        if result == "version_conflict":
            raise VersionConflictError(expected=1, current=2)
        if result == "idempotency_conflict":
            raise IdempotencyConflictError("duplicate key")
        if result == "invalid":
            raise ValueError("invalid")
        return {
            "idempotent_replay": result == "replay",
            "receipt": {"accepted": result != "rejected"},
        }


@pytest.mark.asyncio
async def test_learning_metrics_classify_commands_without_identifiers_or_content() -> None:
    service = StubCommands()
    await service.execute(action="start", result="success")
    await service.execute(action="start", result="replay")
    await service.execute(action="complete", result="rejected")
    with pytest.raises(VersionConflictError):
        await service.execute(action="reopen", result="version_conflict")
    with pytest.raises(IdempotencyConflictError):
        await service.execute(action="verify", result="idempotency_conflict")
    with pytest.raises(ValueError):
        await service.execute(action="unexpected-action", result="invalid")

    snapshot = learning_command_metrics.snapshot()

    assert snapshot["commands"]["total"] == 6
    assert snapshot["commands"]["by_outcome"] == {
        "idempotency_conflict": 1,
        "idempotent_replay": 1,
        "invalid_request": 1,
        "succeeded": 1,
        "verification_rejected": 1,
        "version_conflict": 1,
    }
    assert snapshot["commands"]["by_action"]["unknown"] == 1
    assert snapshot["latency_ms"]["sample_count"] == 6
    assert "task_id" not in str(snapshot)
    assert "result" not in str(snapshot)
