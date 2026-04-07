# LangGraph agents: Confident AI API vs OpenTelemetry

Small **LangGraph** demos: one **agent** node (chat) and one **tools** node (`get_weather`). No real LLM is required by default (synthetic tool call). Optional local OpenAI-compatible server via `OPENAI_*` env vars.

Requires **Python 3.11+**. Run examples **from this directory** (`python`) so imports resolve (`workflow`, `otel`, `confidentai`).

---

## Setup

```powershell
cd python
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## `agent_confident.py` — DeepEval / `@observe`

Traces go to **Confident AI Observatory** via `deepeval.tracing.observe`. After the run, the script prompts for **Enter** and sends feedback with `deepeval.annotation.send_annotation` using the SDK **`trace_uuid`** (not `threadId`).

| Variable | Required | Description |
|----------|----------|-------------|
| `CONFIDENT_API_KEY` | Yes | Project API key. |
| `CONFIDENT_TRACE_FLUSH` | No | Set to `YES` so traces flush before exit (good for one-shot scripts). |

```powershell
$env:CONFIDENT_API_KEY = "your_key"
$env:CONFIDENT_TRACE_FLUSH = "YES"
python agent_confident.py
```

Optional LLM: set `OPENAI_BASE_URL` (e.g. Ollama), `OPENAI_API_KEY`, `OPENAI_MODEL`.

---

## `agent_otel.py` — OpenTelemetry (OTLP HTTP)

Flow: export spans → print ids → **Enter** → `POST /v1/annotations` with **`threadId`** and **`FIVE_STAR_RATING`**.

- **W3C `trace_id`** (printed) is what OpenTelemetry uses on the wire. Confident Observatory’s **trace UUID** is often a different internal id; do not assume it equals the printed `trace_id`.
- **`confident.trace.thread_id`** is set on the root span (`langgraph.run_one`). The printed **thread id** should match the thread in the UI; annotations use that value as **`threadId`**. See [OpenTelemetry on Confident AI](https://www.confident-ai.com/docs/integrations/opentelemetry) (threads / `confident.trace.thread_id`).
- Optional **`CONFIDENT_OTEL_THREAD_ID`**: if set, reused as thread id; if unset, a new UUID per run.

**OTLP HTTP** in this repo uses **`create_otlp_exporter_no_ssl`** (`verify=False` on the exporter). HTTPS to Confident (`https://otel.confident-ai.com/...`) may log **`InsecureRequestWarning`** from urllib3; that is expected unless you switch to verified TLS.

**Mode** (see `confidentai.otlp.resolve_otlp_traces_export`): if **`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`** and **`OTEL_EXPORTER_OTLP_TRACES_HEADERS`** are both **empty** (after strip), OTLP URL is derived from **`CONFIDENT_BASE_URL`** and headers include **`x-confident-api-key`**. If **either** traces env var is non-empty, endpoint and headers come from **`otel/export.py`** (`get_otlp_endpoint` / `get_otlp_headers`).

**REST** `/v1/annotations` uses header **`CONFIDENT-API-KEY`** (same project key as OTLP when using Confident defaults).

---

### Confident AI (default OTLP + REST)

Use when both `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` and `OTEL_EXPORTER_OTLP_TRACES_HEADERS` are empty. **`CONFIDENT_BASE_URL` host** must be exactly `api.confident-ai.com`, `eu.api.confident-ai.com`, or `au.api.confident-ai.com` so OTLP can map to `otel.confident-ai.com` / `eu.otel…` / `au.otel…`. Other hosts require the custom OTLP env vars below.

| Variable | Required | Description |
|----------|----------|-------------|
| `CONFIDENT_API_KEY` | Yes | OTLP header `x-confident-api-key` and REST `CONFIDENT-API-KEY`. |
| `CONFIDENT_BASE_URL` | Yes | REST origin (e.g. `https://api.confident-ai.com`); also used to derive OTLP traces URL in default mode. |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | No | Must be **empty** for default Confident OTLP (non-empty selects custom path). |
| `OTEL_EXPORTER_OTLP_TRACES_HEADERS` | No | Must be **empty** for default Confident OTLP. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | Not read in default mode (only when custom OTLP path is selected). |
| `OTEL_EXPORTER_OTLP_HEADERS` | No | Not read in default mode. |
| `TRACELOOP_TRACE_CONTENT` | No | Set to `false` to reduce LangChain span payload logging. |
| `CONFIDENT_OTEL_THREAD_ID` | No | Stable `confident.trace.thread_id` + `threadId` for annotations. |
| `CONFIDENT_ANNOTATION_DEBUG` | No | **Default on** if unset (`getenv(..., "1")`). Set to `0`, `false`, `no`, `off`, or **`""`** to disable stdout dump of annotation request/response. Any other value (e.g. `1`, `true`) keeps it on. |

```powershell
$env:CONFIDENT_API_KEY = "your_key"
$env:CONFIDENT_BASE_URL = "https://api.confident-ai.com"
python agent_otel.py
```

---

### Custom OTLP endpoint (collector or non-Confident OTLP)

Use when **either** `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` **or** `OTEL_EXPORTER_OTLP_TRACES_HEADERS` is non-empty. Resolution matches **`otel/export.py`**: traces endpoint wins, then `OTEL_EXPORTER_OTLP_ENDPOINT` + `/v1/traces`, else `http://localhost:4318/v1/traces`. Headers: `OTEL_EXPORTER_OTLP_TRACES_HEADERS` then `OTEL_EXPORTER_OTLP_HEADERS`.

`CONFIDENT_API_KEY` and `CONFIDENT_BASE_URL` remain **required** for `/v1/annotations` (REST only in this path).

| Variable | Required | Description |
|----------|----------|-------------|
| `CONFIDENT_API_KEY` | Yes | REST `/v1/annotations` only. |
| `CONFIDENT_BASE_URL` | Yes | REST origin for `/v1/annotations`. |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | No | Full OTLP HTTP traces URL. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | OTLP base; `/v1/traces` appended if needed. |
| `OTEL_EXPORTER_OTLP_TRACES_HEADERS` | No | Comma-separated `key=value` (traces exporter). |
| `OTEL_EXPORTER_OTLP_HEADERS` | No | Fallback if traces headers unset/empty. |
| `TRACELOOP_TRACE_CONTENT` | No | Same as above. |
| `CONFIDENT_OTEL_THREAD_ID` | No | Same as default mode. |
| `CONFIDENT_ANNOTATION_DEBUG` | No | Same as default mode. |

```powershell
$env:CONFIDENT_API_KEY = "your_key"
$env:CONFIDENT_BASE_URL = "https://api.confident-ai.com"
$env:OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = "http://localhost:4318/v1/traces"
$env:OTEL_EXPORTER_OTLP_TRACES_HEADERS = "authorization=Basic ..."
python agent_otel.py
```

---

## Layout

| Path | Role |
|------|------|
| `workflow.py` | Shared graph and nodes. |
| `agent_confident.py` | DeepEval `@observe`; annotation via SDK `trace_uuid`. |
| `agent_otel.py` | OTLP + LangChain instrumentor; annotation via `threadId` + `confidentai.post_thread_annotation_five_star`. |
| `otel/` | OTLP exporter helpers (`export.py`); TLS verify off for corporate proxies. |
| `confidentai/` | `otlp.py` (resolve export + Confident OTLP URL), `api.py` (`/v1/annotations` trace vs thread). |
