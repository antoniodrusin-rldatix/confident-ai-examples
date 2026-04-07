"""
Map Confident REST base URL to OTLP traces URL (standard Confident hosts only).
"""
import os
from typing import Dict, Tuple
from urllib.parse import urlparse, urlunparse

_REST_HOST_TO_OTEL_HOST: dict[str, str] = {
    "api.confident-ai.com": "otel.confident-ai.com",
    "eu.api.confident-ai.com": "eu.otel.confident-ai.com",
    "au.api.confident-ai.com": "au.otel.confident-ai.com",
}


def require_confident_project_env() -> Tuple[str, str]:
    """Return (CONFIDENT_API_KEY, CONFIDENT_BASE_URL); both must be set."""
    key = os.environ.get("CONFIDENT_API_KEY", "").strip()
    base = os.environ.get("CONFIDENT_BASE_URL", "").strip().rstrip("/")
    if not key:
        raise ValueError("CONFIDENT_API_KEY is required.")
    if not base:
        raise ValueError(
            "CONFIDENT_BASE_URL is required (e.g. https://api.confident-ai.com, "
            "https://eu.api.confident-ai.com, https://au.api.confident-ai.com)."
        )
    return key, base


def otlp_traces_endpoint_from_rest_base(rest_base: str) -> str:
    """https://api.confident-ai.com -> https://otel.confident-ai.com/v1/traces (EU/AU similarly)."""
    p = urlparse(rest_base.strip().rstrip("/"))
    if not p.netloc:
        raise ValueError(f"Invalid CONFIDENT_BASE_URL: {rest_base!r}")
    host = p.netloc.lower()
    otel_host = _REST_HOST_TO_OTEL_HOST.get(host)
    if not otel_host:
        raise ValueError(
            f"Cannot derive OTLP URL from CONFIDENT_BASE_URL host {host!r}. "
            "Use a standard Confident API host or set OTEL_EXPORTER_OTLP_TRACES_ENDPOINT "
            "and OTEL_EXPORTER_OTLP_TRACES_HEADERS."
        )
    scheme = p.scheme or "https"
    return urlunparse((scheme, otel_host, "/v1/traces", "", "", ""))


def resolve_otlp_traces_export() -> Tuple[str, Dict[str, str], str]:
    """Resolve OTLP endpoint and headers, plus API key for REST calls.

    If ``OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`` and ``OTEL_EXPORTER_OTLP_TRACES_HEADERS`` are
    both unset (empty), uses ``CONFIDENT_BASE_URL`` and ``CONFIDENT_API_KEY`` for Confident OTLP.

    Otherwise uses ``otel.export`` (``OTEL_EXPORTER_OTLP_*``) for endpoint/headers.

    ``CONFIDENT_API_KEY`` and ``CONFIDENT_BASE_URL`` are always required.
    """
    api_key, rest_base = require_confident_project_env()
    ep_set = bool(os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip())
    hdr_set = bool(os.environ.get("OTEL_EXPORTER_OTLP_TRACES_HEADERS", "").strip())
    if not ep_set and not hdr_set:
        endpoint = otlp_traces_endpoint_from_rest_base(rest_base)
        return endpoint, {"x-confident-api-key": api_key}, api_key
    from otel.export import get_otlp_endpoint, get_otlp_headers

    return get_otlp_endpoint(), get_otlp_headers(), api_key
