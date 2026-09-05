"""LLM-as-Judge：temperature=0 + seed 固定，尽可能减少 flakiness。
建议用小模型（gpt-4o-mini / qwen2.5-7b），TRACE 论文验证过精度够用。
"""

from __future__ import annotations

import json
from typing import Any

from ..schema import Trajectory, Assertion

# 默认 judge prompt（可按场景定制）
JUDGE_PROMPT = """
你是一个严谨的 trajectory 评审员，仅根据提供的【Agent 执行轨迹】和【判定标准】回答。

【判定标准】：{criteria}
【Agent 最终回答】：{final_answer}
【工具调用和观察摘要】：
{tool_trace}
【Evidence Bank 引用】：
{evidence}

请严格按 JSON 格式输出：
{{
  "score": true/false,          // 是否满足标准
  "reasoning": "简要说明（1-2 句）"
}}
不要输出 JSON 以外的任何内容。
"""


class LLMJudge:
    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.0,
                 seed: int = 42, api_key: str | None = None):
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover
            raise ImportError("请 pip install openai") from e
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.seed = seed

    def _extract_final(self, traj: Trajectory) -> str:
        for s in reversed(traj.spans):
            if s.type.value == "final_answer":
                return s.output_snippet[:4000]
        return ""

    def _tool_trace(self, traj: Trajectory) -> str:
        lines = []
        for s in traj.spans:
            if s.type.value == "tool_call":
                lines.append(f"- [{s.status.value}] {s.tool_name} args={json.dumps(s.tool_args, ensure_ascii=False)}")
            elif s.type.value == "tool_result":
                lines.append(f"  -> obs: {s.output_snippet[:400]}")
        return "\n".join(lines) or "无工具调用"

    def _evidence(self, traj: Trajectory) -> str:
        if not traj.evidence_bank_refs:
            return "无"
        return "\n".join(f"- {r.doc_id} chunk={r.chunk_index} score={r.relevance_score}"
                         for r in traj.evidence_bank_refs)

    def judge(self, assertion: Assertion, traj: Trajectory) -> dict:
        user = JUDGE_PROMPT.format(
            criteria=assertion.criteria or "回答是否合理准确？",
            final_answer=self._extract_final(traj),
            tool_trace=self._tool_trace(traj),
            evidence=self._evidence(traj),
        )
        resp = self.client.chat.completions.create(
            model=assertion.model or self.model,
            temperature=self.temperature,
            seed=self.seed,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": user}],
        )
        content = resp.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return {"score": False, "reasoning": f"judge_output_not_json: {content[:200]}"}
        return {"score": bool(data.get("score", False)),
                "reasoning": data.get("reasoning", "")[:400]}


def evaluate_llm_assertions(assertions: list[Assertion], traj: Trajectory,
                            judge: LLMJudge | None = None) -> list[dict]:
    """对断言中 type=llm_judge 的项执行评审，返回每项的结果。"""
    results: list[dict] = []
    j = judge or LLMJudge()
    for a in assertions:
        if a.type.value != "llm_judge":
            continue
        try:
            r = j.judge(a, traj)
        except Exception as e:  # pragma: no cover
            r = {"score": False, "reasoning": f"judge_error: {e}"}
        results.append({"type": "llm_judge", "passed": r["score"],
                        "detail": r["reasoning"], "criteria": a.criteria})
    return results
