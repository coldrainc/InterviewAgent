from __future__ import annotations

import base64
import re
import shlex
import subprocess
from dataclasses import dataclass, field

from interview_agent.infrastructure.settings import AppSettings


@dataclass(frozen=True)
class SecurityFinding:
    code: str
    message: str
    severity: str = "warning"
    score: int = 0


@dataclass
class SecurityScanResult:
    blocked: bool = False
    score: int = 0
    findings: list[SecurityFinding] = field(default_factory=list)

    def add(self, finding: SecurityFinding) -> None:
        self.findings.append(finding)
        self.score += finding.score


PROMPT_INJECTION_PATTERNS = [
    (r"(?i)ignore (all|previous|above|system|developer) (instructions|rules|prompt)", "ignore_instructions", 35),
    (r"(?i)reveal (the )?(system|developer) (prompt|message|instructions)", "reveal_system_prompt", 40),
    (r"(?i)print (the )?(hidden|system|developer) (prompt|instructions)", "print_hidden_prompt", 40),
    (r"(?i)you are now (dan|developer mode|root|admin)", "role_override", 30),
    (r"(?i)disable (safety|guardrails|filters|policy)", "disable_safety", 35),
    (r"(?i)exfiltrate|leak|dump.*(secret|token|api key|password)", "secret_exfiltration", 45),
    (r"(?i)<script|javascript:|onerror=|onload=", "script_injection", 30),
    (r"(?i)BEGIN SYSTEM PROMPT|SYSTEM OVERRIDE|developer message", "prompt_boundary_attack", 35),
    (r"(?i)请忽略(之前|以上|所有).*(指令|规则|提示词)", "zh_ignore_instructions", 35),
    (r"(?i)泄露|打印.*(系统提示词|开发者消息|隐藏提示词|密钥|token)", "zh_prompt_leak", 40),
]

UPLOAD_TEXT_PATTERNS = [
    (r"sk-[A-Za-z0-9][A-Za-z0-9_-]{8,}", "secret_key", "上传内容疑似包含 API Key。", 40),
    (r"(?i)(password|passwd|api[_-]?key|secret|token)\s*[:=]\s*['\"]?[\w.\-]{8,}", "secret_assignment", "上传内容疑似包含密钥或密码。", 40),
    (r"(?i)<script|javascript:|onerror=|onload=", "script_payload", "上传内容包含可执行脚本片段。", 35),
    (r"(?i)ignore (all|previous|system|developer) instructions", "prompt_injection", "上传内容包含疑似 Prompt Injection。", 30),
    (r"(?i)base64_decode|powershell|cmd\.exe|/bin/sh|curl\s+http", "malicious_command", "上传内容包含可疑命令片段。", 35),
]


def scan_prompt_injection(text: str, *, block_score: int = 70, enabled: bool = True) -> SecurityScanResult:
    if not enabled:
        return SecurityScanResult()
    result = SecurityScanResult()
    inspected = text[:12000]
    for pattern, code, score in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, inspected):
            result.add(
                SecurityFinding(
                    code=code,
                    message="输入疑似包含 Prompt Injection 或越权指令。",
                    severity="critical" if score >= 40 else "warning",
                    score=score,
                )
            )
    result.blocked = result.score >= block_score
    return result


def scan_upload_content(
    *,
    filename: str,
    content_base64: str,
    settings: AppSettings,
) -> SecurityScanResult:
    result = SecurityScanResult()
    if not settings.upload_content_scan_enabled and not settings.upload_antivirus_enabled:
        return result
    try:
        content = base64.b64decode(content_base64, validate=True)
    except ValueError:
        result.add(SecurityFinding("invalid_base64", "上传内容不是合法 base64。", "critical", 100))
        result.blocked = True
        return result

    if settings.upload_content_scan_enabled:
        result = _scan_upload_bytes(filename, content, result)
    if settings.upload_antivirus_enabled:
        av_finding = _run_antivirus_scan(settings.upload_antivirus_command, content)
        if av_finding:
            result.add(av_finding)
    result.blocked = any(finding.severity == "critical" for finding in result.findings) or result.score >= 80
    return result


def _scan_upload_bytes(filename: str, content: bytes, result: SecurityScanResult) -> SecurityScanResult:
    lower_name = filename.lower()
    if lower_name.endswith((".exe", ".dll", ".sh", ".bat", ".cmd", ".js", ".jar", ".php")):
        result.add(SecurityFinding("blocked_extension", "不允许上传可执行脚本或二进制程序。", "critical", 100))
    if b"\x00" in content[:4096] and not lower_name.endswith(".pdf"):
        result.add(SecurityFinding("binary_payload", "上传内容包含可疑二进制片段。", "critical", 80))
    text = content[:200000].decode("utf-8", errors="ignore")
    for pattern, code, message, score in UPLOAD_TEXT_PATTERNS:
        if re.search(pattern, text):
            result.add(SecurityFinding(code, message, "critical" if score >= 40 else "warning", score))
    return result


def _run_antivirus_scan(command: str, content: bytes) -> SecurityFinding | None:
    args = shlex.split(command)
    if not args:
        return None
    try:
        completed = subprocess.run(
            args,
            input=content,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return SecurityFinding("antivirus_unavailable", f"杀毒扫描不可用：{exc}", "warning", 20)
    if completed.returncode == 0:
        return None
    output = (completed.stdout + completed.stderr).decode("utf-8", errors="ignore")[:500]
    return SecurityFinding("antivirus_detected", f"杀毒扫描发现风险：{output}", "critical", 100)
