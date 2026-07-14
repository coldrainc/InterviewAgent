from __future__ import annotations

from dataclasses import dataclass, field

from interview_agent.core.guardrails import GuardrailFinding
from interview_agent.domain.billing import TokenUsage


@dataclass
class HarnessResult:
    text: str
    findings: list[GuardrailFinding] = field(default_factory=list)
    fallback_used: bool = False
    usage: TokenUsage | None = None

    def warning_text(self) -> str:
        if not self.findings:
            return ""
        messages = "；".join(finding.message for finding in self.findings)
        return f"（Harness 护栏：{messages}）"
