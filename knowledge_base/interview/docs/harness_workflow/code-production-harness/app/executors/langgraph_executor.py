"""Agent 执行器 - 基于 LangGraph。
直接把你 Workflow Agent 的能力包装成 LangGraph StateGraph：
  Nodes: reason(LLM) → tool_call → tool_result → finalize
  Edges: 条件路由：如果 LLM 提出工具调用 → 走 tool；否则 finalize。
  Checkpointer：生产建议用 MemorySaver 或 Postgres/MongoSaver，方便后续回放。
"""
from __future__ import annotations

import time
from typing import Any, Iterator, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from .llm import call_llm, tool_args_schema
from ..schema import Scenario


# ---------------------------------------------------------------------------
# Graph State（= ReAct 过程状态）
# ---------------------------------------------------------------------------

class ReActState(TypedDict, total=False):
    user_prompt: str
    context: dict[str, Any]
    tools_whitelist: list[str]
    seed: int

    messages: list[dict[str, Any]]       # 会话消息历史
    steps: int                           # 当前步数
    tool_calls: list[dict[str, Any]]     # 暂存待执行的 tool_call
    evidence_refs: list[dict[str, Any]]  # RAG 检索到的知识

    # 用于 Harness 采集：每一步的 turn dict
    turns: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# 节点实现
# ---------------------------------------------------------------------------

def _emit(turns: list, turn: dict, *, ts=None, duration_ms=0.0, token_count=0,
          cost_usd=0.0, status="ok", **kw) -> dict:
    t = {"type": turn.get("type", "llm_reasoning"), "name": turn.get("name", ""),
         "duration_ms": duration_ms, "token_count": token_count,
         "cost_usd": cost_usd, "status": status, **turn, **kw}
    turns.append(t)
    return t


def node_reason(state: ReActState) -> dict:
    t0 = time.time()
    # 调 LLM，要求输出 ReAct 思考 + 可选 tool_calls
    resp = call_llm(
        messages=state["messages"],
        tools_whitelist=state["tools_whitelist"],
        seed=state["seed"],
    )
    turns = state.get("turns", [])
    _emit(turns, {"type": "llm_reasoning",
                  "name": f"react_step_{state['steps']}",
                  "input": {"messages_count": len(state["messages"])},
                  "output_snippet": resp.content[:500] or "",
                  "tool_args": resp.tool_calls or []},
          duration_ms=(time.time() - t0) * 1000,
          token_count=resp.token_count, cost_usd=resp.cost_usd,
          status="ok" if not resp.error else "error",
          error_message=resp.error)

    new_msgs = list(state["messages"])
    new_msgs.append({"role": "assistant", "content": resp.content,
                     "tool_calls": resp.tool_calls or []})
    if resp.evidence_refs:
        state["evidence_refs"].extend(resp.evidence_refs)
    return {
        "messages": new_msgs,
        "tool_calls": resp.tool_calls or [],
        "steps": state["steps"] + 1,
        "turns": turns,
    }


def node_tool_execute(state: ReActState) -> dict:
    turns = state.get("turns", [])
    new_msgs = list(state["messages"])
    for tc in state.get("tool_calls", []):
        t0 = time.time()
        tool_name = tc.get("name", "")
        tool_args = tc.get("args", {})
        # 实际生产：调用你 Workflow Agent 的 MCP Skill 服务
        obs, status, err, token_cost, cost_dollar = _invoke_tool(
            tool_name, tool_args, state["context"])
        _emit(turns, {"type": "tool_call", "name": tool_name,
                      "tool_name": tool_name, "tool_args": tool_args,
                      "output_snippet": str(obs)[:800]},
              duration_ms=(time.time() - t0) * 1000,
              token_count=token_cost, cost_usd=cost_dollar,
              status=status, error_message=err)
        new_msgs.append({"role": "tool", "name": tool_name,
                         "tool_call_id": tc.get("id"), "content": str(obs)[:2000]})
    return {"messages": new_msgs, "tool_calls": [], "turns": turns}


def node_finalize(state: ReActState) -> dict:
    # 最后一步，把最终回答包装成 final_answer turn
    last_assistant = next(
        (m for m in reversed(state["messages"]) if m["role"] == "assistant"), {})
    turns = state.get("turns", [])
    _emit(turns, {"type": "final_answer", "name": "final",
                  "output_snippet": str(last_assistant.get("content", ""))[:2000],
                  "evidence_refs": state.get("evidence_refs", [])},
          duration_ms=1.0)
    return {"turns": turns}


def _route_after_reason(state: ReActState) -> str:
    if state.get("tool_calls"):
        return "tools"
    return "finalize"


def _route_max_steps(state: ReActState) -> str:
    if state["steps"] >= 20:  # 上限防死循环
        return "finalize"
    return "reason"


# ---------------------------------------------------------------------------
# 构建 Graph
# ---------------------------------------------------------------------------

def build_graph():
    g = StateGraph(ReActState)
    g.add_node("reason", node_reason)
    g.add_node("tools", node_tool_execute)
    g.add_node("finalize", node_finalize)

    g.add_edge(START, "reason")
    g.add_conditional_edges("reason", _route_after_reason,
                            {"tools": "tools", "finalize": "finalize"})
    g.add_conditional_edges("tools", _route_max_steps,
                            {"reason": "reason", "finalize": "finalize"})
    g.add_edge("finalize", END)
    return g.compile(checkpointer=MemorySaver())


# ---------------------------------------------------------------------------
# AgentExecutor 协议实现（与 demos/harness runner 一致）
# ---------------------------------------------------------------------------

class LangGraphAgentExecutor:
    def __init__(self, graph=None):
        self.graph = graph or build_graph()

    def run_stream(self, user_prompt: str, context: dict,
                   tools_whitelist: list[str], seed: int) -> Iterator[dict]:
        initial: ReActState = {
            "user_prompt": user_prompt,
            "context": context,
            "tools_whitelist": tools_whitelist or [],
            "seed": seed,
            "messages": [
                {"role": "system",
                 "content": "你是 Workflow Agent ReAct 执行器。优先使用工具获取事实依据，最后输出最终答案。"},
                {"role": "user", "content": user_prompt},
            ],
            "steps": 0,
            "tool_calls": [],
            "evidence_refs": [],
            "turns": [],
        }
        config = {"configurable": {"thread_id": f"t_{seed}_{int(time.time())}"}}

        last_turns_len = 0
        for _ in self.graph.stream(initial, config, stream_mode="values"):
            state = _
            current_turns = state.get("turns", [])
            # 只 yield 新增的 turn（流式输出给 Harness Runner 边跑边采 span）
            for i in range(last_turns_len, len(current_turns)):
                yield current_turns[i]
            last_turns_len = len(current_turns)


# ---------------------------------------------------------------------------
# Tool 调用占位（接入你 Workflow Agent 的 MCP Skill）
# ---------------------------------------------------------------------------

def _invoke_tool(tool_name: str, tool_args: dict, context: dict
                 ) -> tuple[str, str, Optional[str], int, float]:
    """返回 (observation, status, err_msg, token, cost)。
    真实生产：用 MCP SDK 调用 Workflow Agent 的工具；这里做示例映射。
    """
    # 你现有 MCP Skill 服务：knowledge_retrieval / get_trace_detail / sandbox_check_...
    # 这里做快速 demo 映射。
    import json
    obs = ""
    status = "ok"
    err = None
    try:
        if tool_name == "get_trace_detail":
            obs = json.dumps({
                "trace_id": tool_args.get("trace_id"),
                "failed_span": {"tool": "code_edit", "error": "sandbox_toml_parse_failed"},
            }, ensure_ascii=False)
        elif tool_name == "sandbox_check_config_integrity":
            obs = json.dumps({
                "sha256_mismatch": True, "residual_keys": ["tool_version"],
                "recommended_action": "rollback_then_atomic_replace_with_sha256",
            }, ensure_ascii=False)
        elif tool_name == "knowledge_retrieval":
            obs = ("开播失败的常见原因：1) 推流鉴权配置错误（检查 AK/SK 有效期、权限）"
                   "；2) 主播端到 CDN 推流网络不通（检查防火墙、RTMP 端口）"
                   "；3) 音视频编码参数不兼容（分辨率、码率、H.264 profile）。")
        else:
            obs = f"tool {tool_name} args={tool_args} -> ok"
    except Exception as e:
        status, err = "error", repr(e)
    return obs, status, err, 0, 0.0
