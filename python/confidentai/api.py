"""
Confident AI REST API helpers (Evals API).
"""
import json
import logging
import os
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


def _annotation_debug_enabled() -> bool:
    v = os.environ.get("CONFIDENT_ANNOTATION_DEBUG", "1").strip().lower()
    return v not in ("0", "false", "no", "off", "")


def _print_annotation_debug(
    *,
    url: str,
    body: Dict[str, Any],
    resp: requests.Response,
    parsed: Optional[Any],
) -> None:
    if not _annotation_debug_enabled():
        return
    redacted_headers = {"Content-Type": "application/json", "CONFIDENT-API-KEY": "<redacted>"}
    print("[confident annotations] POST", url)
    print("[confident annotations] headers:", json.dumps(redacted_headers))
    print("[confident annotations] request JSON:\n" + json.dumps(body, indent=2))
    print(f"[confident annotations] response HTTP {resp.status_code} {resp.reason or ''}")
    if parsed is not None:
        try:
            print("[confident annotations] response JSON:\n" + json.dumps(parsed, indent=2))
        except (TypeError, ValueError):
            print("[confident annotations] response body (raw):\n", resp.text[:8000])
    else:
        txt = (resp.text or "")[:8000]
        print("[confident annotations] response body (raw):\n" + txt)
        if len(resp.text or "") > 8000:
            print("[confident annotations] ... truncated ...")


def get_rest_base_url() -> str:
    """REST API origin from ``CONFIDENT_BASE_URL`` (required)."""
    base = os.environ.get("CONFIDENT_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise ValueError("CONFIDENT_BASE_URL is required.")
    return base


def normalize_trace_uuid_for_annotation(trace_id: str) -> str:
    """Format W3C 128-bit trace id (32 hex) as hyphenated UUID; otherwise return stripped input."""
    raw = trace_id.strip()
    compact = raw.lower().replace("-", "")
    if len(compact) == 32 and all(c in "0123456789abcdef" for c in compact):
        return f"{compact[:8]}-{compact[8:12]}-{compact[12:16]}-{compact[16:20]}-{compact[20:]}"
    return raw


def _post_annotations(
    body: Dict[str, Any],
    api_key: str,
    *,
    timeout: float,
    log_label: str,
) -> None:
    url = f"{get_rest_base_url()}/v1/annotations"
    headers = {
        "Content-Type": "application/json",
        "CONFIDENT-API-KEY": api_key.strip(),
    }
    logger.info("POST %s %s body keys=%s", url, log_label, list(body.keys()))
    resp = requests.post(url, json=body, headers=headers, timeout=timeout)
    parsed: Optional[Any] = None
    try:
        parsed = resp.json()
    except ValueError:
        parsed = None
    _print_annotation_debug(url=url, body=body, resp=resp, parsed=parsed)
    if resp.ok:
        if isinstance(parsed, dict) and parsed.get("success") is False:
            err = parsed.get("error") or "Confident API returned success=false"
            logger.error("Annotation API success=false: %s body=%s", err, parsed)
            raise RuntimeError(err)
        return
    detail = (resp.text or "").strip()
    logger.error(
        "Annotation failed %s: %s",
        log_label,
        detail[:2000] if detail else "(empty body)",
    )
    raise RuntimeError(
        f"HTTP {resp.status_code} for {resp.url} — {detail or '(empty body)'}"
    )


def post_trace_annotation_five_star(
    trace_uuid: str,
    rating: int,
    api_key: str,
    *,
    timeout: float = 60,
) -> None:
    """POST /v1/annotations with ``traceUuid`` (Confident dashboard id, not always equal to OTEL trace_id)."""
    trace_uuid_for_api = normalize_trace_uuid_for_annotation(trace_uuid)
    _post_annotations(
        {
            "traceUuid": trace_uuid_for_api,
            "rating": int(rating),
            "type": "FIVE_STAR_RATING",
        },
        api_key,
        timeout=timeout,
        log_label=f"traceUuid={trace_uuid_for_api} rating={rating}",
    )


def post_thread_annotation_five_star(
    thread_id: str,
    rating: int,
    api_key: str,
    *,
    timeout: float = 60,
) -> None:
    """POST /v1/annotations with ``threadId`` (use with ``confident.trace.thread_id`` on OTLP spans)."""
    tid = thread_id.strip()
    _post_annotations(
        {
            "threadId": tid,
            "rating": int(rating),
            "type": "FIVE_STAR_RATING",
        },
        api_key,
        timeout=timeout,
        log_label=f"threadId={tid} rating={rating}",
    )
