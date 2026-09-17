from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class VerificationResult:
    status: str
    mode: str
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)
    verifier: str = "learning"

    @property
    def accepted(self) -> bool:
        return self.status == "verified"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "reason": self.reason,
            "evidence": self.evidence,
        }


class TaskVerifier(Protocol):
    async def verify(self, task: Any, run: Any, submitted: dict[str, Any]) -> VerificationResult: ...
