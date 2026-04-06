"""
OTLP HTTP trace export with TLS verification disabled (common behind Zscaler / corporate TLS inspection).

Endpoint and headers follow the same OTEL_* env vars as opentelemetry.exporter.otlp.proto.http.trace_exporter.
"""
import logging
import os
from typing import Any, Dict, Optional, Sequence

logger = logging.getLogger(__name__)

DEFAULT_TRACES_ENDPOINT = "http://localhost:4318/v1/traces"


def get_otlp_endpoint() -> str:
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if endpoint:
        return endpoint
    base = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip().rstrip("/")
    if not base:
        return DEFAULT_TRACES_ENDPOINT
    return base if base.endswith("v1/traces") else f"{base}/v1/traces"


def get_otlp_headers() -> Dict[str, str]:
    from opentelemetry.util.re import parse_env_headers

    s = os.environ.get(
        "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
        os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", ""),
    )
    return parse_env_headers(s, liberal=True) if s else {}


def create_otlp_exporter_no_ssl(endpoint: str, headers: Optional[Dict[str, str]]) -> Any:
    """OTLPSpanExporter with verify=False on HTTP posts (SDK init ignores explicit False for certificate_file)."""
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers or None)
    exporter._certificate_file = False
    return exporter


def wrap_exporter_with_logging(delegate: Any):
    """Wrap an OTLP span exporter so callers can read last export result after shutdown (BatchSpanProcessor is async)."""
    from opentelemetry.sdk.trace import ReadableSpan
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

    class LoggingSpanExporter(SpanExporter):
        def __init__(self, inner: Any):
            self._inner = inner
            self.last_result: Optional[SpanExportResult] = None
            self.last_error: Optional[Exception] = None

        def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
            self.last_error = None
            try:
                self.last_result = self._inner.export(spans)
                if self.last_result is not SpanExportResult.SUCCESS:
                    logger.warning(
                        "OTLP span export returned failure: result=%s span_count=%s",
                        self.last_result,
                        len(spans) if spans else 0,
                    )
                return self.last_result
            except Exception as e:
                self.last_error = e
                logger.exception("OTLP span export raised: %s", e)
                raise

        def shutdown(self) -> None:
            self._inner.shutdown()

        def force_flush(self, timeout_millis: int = 30000) -> bool:
            return self._inner.force_flush(timeout_millis)

    return LoggingSpanExporter(delegate)
