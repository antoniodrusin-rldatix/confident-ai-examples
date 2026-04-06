"""
LangGraph agent with Confident AI tracing via deepeval @observe.
Same workflow as workflow.py: agent -> tools. One trace per run: parent span (run_one) with two
child spans (agent_node, tools_node). Observe at invocation layer so agent/tools nest under the run.
Env: CONFIDENT_API_KEY; optional CONFIDENT_TRACE_FLUSH=YES for short-lived scripts.
"""
import os
import random
import sys
from typing import Any

from deepeval.annotation import send_annotation
from deepeval.annotation.api import AnnotationType
from deepeval.tracing import observe
from deepeval.tracing.context import current_trace_context
from langgraph.graph import END, START, StateGraph

from workflow import State, USER_QUERY, agent_node as raw_agent_node, tools_node as raw_tools_node


def _setup_tracing():
    """Check Confident API key is set for tracing."""
    if not os.environ.get("CONFIDENT_API_KEY", "").strip():
        raise ValueError("Set CONFIDENT_API_KEY for Confident AI tracing.")


@observe()
def agent_node(state: State) -> dict[str, Any]:
    """Confident span around shared workflow.agent_node (LLM or synthetic tool_calls)."""
    print("[agent_confident] agent_node entered")
    return raw_agent_node(state)


@observe()
def tools_node(state: State) -> dict[str, Any]:
    """Confident span around shared workflow.tools_node (get_weather result)."""
    print("[agent_confident] tools_node entered")
    return raw_tools_node(state)


def _build_graph():
    """Build agent→tools StateGraph and return compiled graph."""
    builder = StateGraph(State)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tools_node)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", "tools")
    builder.add_edge("tools", END)
    return builder.compile()


def _answer_from_final_state(state: State) -> str:
    """Human-readable answer: assistant text if present, else summary from tool_result."""
    agent_out = state.get("agent_output") or {}
    content = (agent_out.get("content") or "").strip()
    if content:
        return content
    tr = state.get("tool_result") or {}
    if tr:
        loc = tr.get("location", "")
        temp = tr.get("temp")
        unit = tr.get("unit", "celsius")
        if temp is not None:
            return f"The weather in {loc or 'the location'} is {temp}° {unit}."
    return ""


@observe()
def run_one(query: str | None = None) -> tuple[str, str]:
    """Run one invocation. Parent span here; agent + tools spans are children.

    Returns (answer, trace_uuid). trace_uuid is for send_annotation (Observatory URL).
    """
    q = query or USER_QUERY
    trace = current_trace_context.get()
    if trace is None:
        raise RuntimeError("No active Confident trace (current_trace_context is empty).")
    trace_uuid = trace.uuid
    graph = _build_graph()
    final = graph.invoke({"user_query": q})
    answer = _answer_from_final_state(final)
    return answer, trace_uuid


def main() -> None:
    try:
        _setup_tracing()
        answer, trace_uuid = run_one("This is an example query")
        print("Confident AI trace (agent + tools spans) sent. Check the Observatory.")
        print(f"  Answer: {answer}")
        print(f"  trace_uuid (Observatory / annotations): {trace_uuid}")
        input("Press Enter to send feedback on this trace (or Ctrl+C to skip)... ")
        send_annotation(
            trace_uuid=trace_uuid,
            type=AnnotationType.FIVE_STAR_RATING,
            rating=random.randint(1, 5),
        )
        print("Feedback sent.")
    except ValueError as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
