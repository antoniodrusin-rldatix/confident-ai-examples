"""
LangGraph agent with Confident AI tracing via deepeval @observe.
Same workflow as workflow.py: agent -> tools. One trace per run: parent span (run_one) with two
child spans (agent_node, tools_node). Observe at invocation layer so agent/tools nest under the run.
Env: CONFIDENT_API_KEY; optional CONFIDENT_TRACE_FLUSH=YES for short-lived scripts.
"""
import os
import random
import sys
import uuid
from typing import Any

from deepeval.annotation import send_annotation
from deepeval.annotation.api import AnnotationType
from deepeval.tracing import observe
from deepeval.tracing.context import current_trace_context, update_current_trace
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


@observe()
def run_one(query: str | None = None) -> str:
    """Run one invocation. Parent span here; agent + tools spans are children.

    Returns trace_uuid for send_annotation (matches the Observatory URL).
    """
    feedback_thread_id = str(uuid.uuid4())
    q = query or USER_QUERY
    update_current_trace(thread_id=feedback_thread_id, input=q)
    trace = current_trace_context.get()
    if trace is None:
        raise RuntimeError("No active Confident trace (current_trace_context is empty).")
    trace_uuid = trace.uuid
    graph = _build_graph()
    graph.invoke({"user_query": q})
    return trace_uuid


def main() -> None:
    try:
        _setup_tracing()
        trace_uuid = run_one()
        print("Confident AI trace (agent + tools spans) sent. Check the Observatory.")
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
