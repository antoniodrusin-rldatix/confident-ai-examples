"""
LangGraph agent with OpenTelemetry + OTLP HTTP to Confident (or override via OTEL_*).
Exports spans, prints ids, waits for Enter (like agent_confident.py), then POSTs a 5-star annotation.

Confident Observatory often shows a trace UUID that is not the W3C trace_id from OpenTelemetry.
We set ``confident.trace.thread_id`` on the root span and send annotations with ``threadId`` so feedback
matches the trace in the dashboard. See https://www.confident-ai.com/docs/integrations/opentelemetry
"""
import logging
import os
import random
import sys
import uuid

from opentelemetry import trace
from opentelemetry.trace import format_trace_id
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExportResult,
)

from langgraph.graph import END, START, StateGraph

from confidentai import post_thread_annotation_five_star, resolve_otlp_traces_export
from otel import create_otlp_exporter_no_ssl, wrap_exporter_with_logging
from opentelemetry.instrumentation.langchain import LangchainInstrumentor

from workflow import State, USER_QUERY, agent_node as raw_agent_node, tools_node as raw_tools_node

_OTLP_FLUSH_TIMEOUT_MS = 30_000
_CONFIDENT_THREAD_ATTR = "confident.trace.thread_id"


def _setup_tracing(endpoint: str, headers: dict | None):
    resource = Resource.create({"service.name": "langgraph-agent-otel"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(out=sys.stdout)))
    exporter = create_otlp_exporter_no_ssl(endpoint, headers or None)
    exporter = wrap_exporter_with_logging(exporter)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return provider, trace.get_tracer("langgraph.agent_otel", "1.0.0"), exporter


def _build_graph():
    builder = StateGraph(State)
    builder.add_node("agent", raw_agent_node)
    builder.add_node("tools", raw_tools_node)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", "tools")
    builder.add_edge("tools", END)
    return builder.compile()


def run_one(query: str | None = None, thread_id: str | None = None):
    graph = _build_graph()
    initial: State = {"user_query": query or USER_QUERY}
    tracer = trace.get_tracer(__name__)
    tid = (thread_id or "").strip() or str(uuid.uuid4())
    with tracer.start_as_current_span("langgraph.run_one") as span:
        span.set_attribute(_CONFIDENT_THREAD_ATTR, tid)
        final = graph.invoke(initial)
        trace_id_hex = format_trace_id(span.get_span_context().trace_id)
    return final, trace_id_hex, tid


def main() -> None:
    try:
        create_otlp_exporter_no_ssl("http://dummy", None)
    except ImportError as e:
        print(
            "OTLP HTTP trace exporter not found. "
            "pip install opentelemetry-exporter-otlp-proto-http"
        )
        print(e)
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(name)s: %(message)s")
    try:
        endpoint, headers, api_key = resolve_otlp_traces_export()
    except ValueError as e:
        print(e)
        sys.exit(1)

    provider, _, exporter = _setup_tracing(endpoint, headers)
    LangchainInstrumentor().instrument()
    try:
        thread_id = os.environ.get("CONFIDENT_OTEL_THREAD_ID", "").strip()
        _, trace_id_hex, thread_id = run_one(thread_id=thread_id or None)
        provider.force_flush(_OTLP_FLUSH_TIMEOUT_MS)
        if getattr(exporter, "last_result", None) != SpanExportResult.SUCCESS:
            print(f"OTLP export failed. Endpoint: {endpoint}")
            if getattr(exporter, "last_error", None) is not None:
                print(exporter.last_error)
            sys.exit(1)
        provider.shutdown()
        print(f"Exported spans to {endpoint}.")
        print("OpenTelemetry trace sent. Check the Confident AI Observatory.")
        print(f"  W3C trace_id (OTEL / export): {trace_id_hex}")
        print(f"  thread id ({_CONFIDENT_THREAD_ATTR} / annotations): {thread_id}")
        input("Press Enter to send feedback on this trace (or Ctrl+C to skip)... ")
        post_thread_annotation_five_star(thread_id, random.randint(1, 5), api_key)
        print("Feedback sent.")
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
