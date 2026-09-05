"""LLM 调用封装：LiteLLM 统一入口，多模型 fallback + 成本统计 + 超时。
真实生产推荐在 LLM 之前挂一个 LiteLLM Proxy（自带速率限制、重试、用量看板）。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import structlog

from ..config import get_settings

log = structlog.get_logger()


@dataclass
class LLMResp:
    content: str
    tool_calls: list[dict[str, Any]] | None
    token_count: int
    cost_usd: float
    error: Optional[str]
    evidence_refs: list[dict[str, Any]] | None = None


def call_llm(messages: list[dict[str, Any]],
             tools_whitelist: Optional[list[str]] = None,
             seed: Optional[int] = None) -> LLMResp:
    """真实生产：用 litellm.completion + 多模型重试。
    为避免本 demo 依赖外部 API，这里实现一个"离线 dummy 模式"：
    当环境变量 LLM_API_KEY 未设置时，输出一个可预测的回答 + 工具调用序列，
    这样 CI、本地、Test 环境都能跑。
    """
    s = get_settings()
    api_key = s.LLM_API_KEY.get_secret_value() if s.LLM_API_KEY else None
    if not api_key:
        return _dummy_reason(messages, tools_whitelist)

    try:
        import litellm  # lazy import，没装也不阻塞本地开发
    except Exception as e:
        return LLMResp("", None, 0, 0.0, f"litellm_not_installed: {e}")

    models = [s.LLM_DEFAULT_MODEL] + list(s.LLM_FALLBACK_MODELS or [])
    last_err = None
    for model in models:
        t0 = time.time()
        try:
            tools = ([{"type": "function",
                       "function": tool_args_schema(name)}
                      for name in (tools_whitelist or [])]) or None
            resp = litellm.completion(
                model=model,
                messages=messages,
                tools=tools,
                temperature=s.LLM_TEMPERATURE,
                seed=seed or s.LLM_SEED,
                timeout=s.LLM_TIMEOUT,
                api_base=s.LLM_PROXY_BASE_URL,
                api_key=api_key,
            )
            msg = resp.choices[0].message
            usage = resp.usage or {}
            # litellm 自带 cost 计算
            cost = float(getattr(resp, "_hidden_params", {}).get(
                "response_cost") or litellm.cost_per_token(
                    model, usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                )[0])
            tool_calls = None
            if getattr(msg, "tool_calls", None):
                tool_calls = [
                    {"id": tc.id, "name": tc.function.name,
                     "args": _safe_json(tc.function.arguments)}
                    for tc in msg.tool_calls
                ]
            return LLMResp(
                content=str(msg.content or ""),
                tool_calls=tool_calls,
                token_count=usage.get("total_tokens", 0),
                cost_usd=cost,
                error=None,
            )
        except Exception as e:  # pragma: no cover
            last_err = f"{model} -> {e!r}"
            log.warning("llm_call_failed", err=last_err,
                        took_ms=int((time.time()-t0)*1000))
            continue
    return LLMResp("", None, 0, 0.0, f"all_models_failed: {last_err}")


def tool_args_schema(tool_name: str) -> dict:
    """示例：实际场景请接入你的 MCP Skill Schema。"""
    return {
        "name": tool_name,
        "description": f"工具 {tool_name}",
        "parameters": {"type": "object", "properties": {
            "trace_id": {"type": "string"},
            "domain": {"type": "string"},
        }},
    }


def _safe_json(raw: str) -> dict:
    import json as _json
    try:
        return _json.loads(raw or "{}")
    except Exception:
        return {"_raw": raw}


# ---------------------------------------------------------------------------
# Dummy：无 LLM Key 也能跑通的"逻辑推理器"，规则化输出工具调用
# ---------------------------------------------------------------------------

def _dummy_reason(messages, tools_whitelist) -> LLMResp:
    last_user = next((m["content"] for m in reversed(messages)
                      if m["role"] == "user"), "")
    whitelist = set(tools_whitelist or [])

    # 规则 1：如果是诊断类问题且看到 traceId，先调 get_trace_detail
    if "traceId" in last_user or "trace_id" in last_user or "排查根因" in last_user:
        if "get_trace_detail" in whitelist or not whitelist:
            return LLMResp(
                content="我先查 trace 详情，再检查 Sandbox 配置完整性。",
                tool_calls=[{"id": "1", "name": "get_trace_detail",
                             "args": {"trace_id": _extract(last_user, "trace_id|traceId", "tr_abc123")}}],
                token_count=1200, cost_usd=0.001, error=None,
            )
    # 规则 2：如果上一轮 tool 返回包含 tom_parse_failed，调 sandbox_check
    for m in reversed(messages):
        if m["role"] == "tool" and "toml_parse_failed" in str(m.get("content", "")):
            return LLMResp(
                content="trace 显示 Sandbox TOML 解析失败，需要检查配置完整性。",
                tool_calls=[{"id": "2", "name": "sandbox_check_config_integrity",
                             "args": {}}],
                token_count=900, cost_usd=0.001, error=None,
            )
    # 规则 3：业务问题走知识库
    if any(k in last_user for k in ["开播", "推流", "直播"]):
        return LLMResp(
            content="我先从业务知识库检索开播失败排查流程。",
            tool_calls=[{"id": "3", "name": "knowledge_retrieval",
                         "args": {"domain": "live_streaming", "scope": "operation"}}],
            token_count=700, cost_usd=0.001, error=None,
        )
    # 默认：根据 tool 返回构造最终回答
    latest_tool = next(
        (m["content"] for m in reversed(messages) if m["role"] == "tool"), "")
    if "sha256_mismatch" in latest_tool:
        return LLMResp(
            content=("【根因】Sandbox 配置残留导致新一轮加载的 TOML 损坏，哈希校验不一致。\n"
                     "【修复建议】① 对配置变更引入 SHA-256 摘要校验；"
                     "② 配置写入采用原子替换（写临时文件 + rename）；"
                     "③ 失败自动回滚到上一版本配置；"
                     "④ 增加阶段账本对账，检测配置脏状态提前告警。"),
            tool_calls=None, token_count=1500, cost_usd=0.002, error=None,
        )
    if "鉴权" in latest_tool and "编码" in latest_tool:
        return LLMResp(
            content=("开播推流失败一般分三大类排查：\n"
                     "1. 鉴权：核对 AK/SK 有效性、过期时间；"
                     "2. 网络：主播端 telnet RTMP 端口、抓包看丢包；"
                     "3. 编码：检查 H.264 profile、码率、分辨率是否在 CDN 允许范围内。"),
            tool_calls=None, token_count=1100, cost_usd=0.002, error=None,
        )
    return LLMResp(content=f"收到：{last_user[:100]}。请提供更多信息。",
                   tool_calls=None, token_count=500, cost_usd=0.0005, error=None)


def _extract(text: str, pattern: str, default: str) -> str:
    import re
    m = re.search(rf"({pattern})[=:\s]*([\w\-]+)", text)
    return m.group(2) if m else default
