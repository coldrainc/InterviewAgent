from __future__ import annotations

from typing import Any

from interview_agent.learning.verifiers.base import VerificationResult


class SelfAttestedTaskVerifier:
    async def verify(self, task: Any, run: Any, submitted: dict[str, Any]) -> VerificationResult:
        return VerificationResult(
            status="verified",
            mode="self_attested",
            reason=str(submitted.get("note") or "用户已确认完成")[:300],
            evidence=submitted,
            verifier="self_attested",
        )
