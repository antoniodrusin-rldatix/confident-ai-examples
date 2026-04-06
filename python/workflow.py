"""Shared LangGraph pieces for agent_otel.py and agent_confident.py.

- TypedDict state and fixed demo constants (synthetic get_weather call).
- agent_node / tools_node: no observability imports here.

Default path is synthetic (no LLM). Optional OpenAI-compatible server via OPENAI_BASE_URL.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional, TypedDict

DEFAULT_MODEL = "gpt-4o"
TOOL_NAME = "get_weather"
TOOL_CALL_ID = "call_synthetic_xyz"
TOOL_ARGS = {"location": "Paris"}
TOOL_RESULT = {"temp": 18, "unit": "celsius"}
USER_QUERY = "What's the weather in Paris?"


class State(TypedDict, total=False):
    user_query: str
    agent_output: dict
    tool_result: dict


def _call_local_llm_if_configured(query: str) -> Optional[dict[str, Any]]:
    """
    If OPENAI_BASE_URL is set, call that API. Returns None to fall back to synthetic output.
    """
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    if not base_url:
        print("[workflow] Local LLM not configured (OPENAI_BASE_URL unset), using synthetic response")
        return None
    query_snippet = (query[:80] + "...") if len(query) > 80 else query
    print(f"[workflow] Calling local LLM (OPENAI_BASE_URL={base_url}) for query: {query_snippet}")
    try:
        from openai import OpenAI

        client = OpenAI(base_url=base_url, api_key=os.environ.get("OPENAI_API_KEY", "lm-studio"))
        model = os.environ.get("OPENAI_MODEL", "local")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": query}],
        )
        content = resp.choices[0].message.content or ""
        tool_calls = getattr(resp.choices[0].message, "tool_calls", None) or []
        content_preview = (content[:200] + "...") if len(content) > 200 else content
        print(
            f"[workflow] Local LLM response: model={resp.model or model}, "
            f"content_length={len(content)}, tool_calls={len(tool_calls)}, "
            f"content_preview={content_preview!r}"
        )
        if not tool_calls:
            normalized_calls = [
                {"id": TOOL_CALL_ID, "name": TOOL_NAME, "arguments": TOOL_ARGS}
            ]
        else:
            normalized_calls = [
                {
                    "id": tc.id,
                    "name": getattr(tc.function, "name", TOOL_NAME),
                    "arguments": json.loads(getattr(tc.function, "arguments", "{}") or "{}"),
                }
                for tc in tool_calls
            ]
        return {
            "content": content,
            "tool_calls": normalized_calls,
            "model": resp.model or DEFAULT_MODEL,
        }
    except Exception as e:
        print(f"[workflow] Local LLM call failed: {e}")
        return None


def agent_node(state: State) -> dict[str, Any]:
    """Produce assistant output: real LLM if configured, else synthetic tool_calls for get_weather."""
    query = state.get("user_query") or USER_QUERY
    query_snippet = (query[:80] + "...") if len(query) > 80 else query
    print(f"[workflow] agent_node called, user_query={query_snippet!r}")
    out = _call_local_llm_if_configured(query)
    if out is None:
        return {
            "agent_output": {
                "content": "",
                "tool_calls": [{"id": TOOL_CALL_ID, "name": TOOL_NAME, "arguments": TOOL_ARGS}],
                "model": DEFAULT_MODEL,
            }
        }
    return {"agent_output": out}


def tools_node(state: State) -> dict[str, Any]:
    """Resolve get_weather arguments from agent_output; return fixed synthetic weather dict."""
    agent_out = state.get("agent_output") or {}
    tool_calls = agent_out.get("tool_calls") or [{"name": TOOL_NAME, "arguments": TOOL_ARGS}]
    args = TOOL_ARGS
    for tc in tool_calls:
        if tc.get("name") == TOOL_NAME:
            args = tc.get("arguments") or TOOL_ARGS
            break
    print(f"[workflow] tools_node called, tool={TOOL_NAME}, arguments={args}")
    result = {**TOOL_RESULT, "location": args.get("location", "Paris")}
    return {"tool_result": result}
