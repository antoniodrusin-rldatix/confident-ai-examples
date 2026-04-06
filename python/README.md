# LangGraph agents: Confident AI API vs OpenTelemetry

Small **LangGraph** demos: one **agent** node (chat) and one **tools** node (`get_weather`). No real LLM is required by default (synthetic tool call). You can optionally point at a local OpenAI-compatible server.

Requires **Python 3.11+**. The **`.python-version`** file is **3.12** for [pyenv](https://github.com/pyenv/pyenv) and similar tools; use any installed 3.11+ otherwise.

---

## Virtual environment and dependencies

Create a venv in this folder, activate it, then install packages. Run all examples **from this directory** (`python`) so imports resolve.

If `python` / `python3` on your PATH is still 3.10 or older, use an explicit interpreter (for example **`py -3`** on Windows to pick the newest Python 3.x registered with the [launcher](https://docs.python.org/3/using/windows.html#python-launcher-for-windows)).

**PowerShell**

```powershell
cd python
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

After activation, use `python agent_confident.py` or `python agent_otel.py` as below.

---

## See traces in Confident AI (DeepEval API)

This path uses the **Confident AI / DeepEval** tracing integration (`deepeval.tracing.observe`). Traces show up in the **Confident AI Observatory** for your project.

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CONFIDENT_API_KEY` | Yes | API key from your Confident AI account (same key you use with DeepEval / the platform). |
| `CONFIDENT_TRACE_FLUSH` | No | Set to `YES` so traces flush before a short-lived process exits (recommended for one-shot scripts and CI). |

### Run locally

```powershell
$env:CONFIDENT_API_KEY = "your_key_here"
$env:CONFIDENT_TRACE_FLUSH = "YES"
python agent_confident.py
```

The script runs one graph invocation (parent span) with child spans for **agent** and **tools**, then optionally prompts for Enter to send sample feedback via the annotation API.

Open the Confident AI **Observatory** in the browser and look for the new trace (filter by recent activity if needed).

### Optional: real local LLM

If `OPENAI_BASE_URL` is set, the agent node calls that API instead of the synthetic reply:

| Variable | Description |
|----------|-------------|
| `OPENAI_BASE_URL` | Base URL (e.g. `http://localhost:11434/v1` for Ollama). |
| `OPENAI_API_KEY` | Optional; many local servers accept any placeholder value. |
| `OPENAI_MODEL` | Model id on the server (default `local`). |

---

## OpenTelemetry (OTLP) instead

Use **`agent_otel.py`** when you want **OpenTelemetry** spans exported over **OTLP HTTP** (e.g. local collector, or Confident’s OTLP endpoint).

### Common environment variables

| Variable | Description |
|----------|-------------|
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | Full traces URL (overrides base below). |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Base OTLP URL; `/v1/traces` is appended if the traces endpoint is not set. |
| `OTEL_EXPORTER_OTLP_TRACES_HEADERS` | Comma-separated headers: `key1=value1,key2=value2`. |
| `OTEL_EXPORTER_OTLP_HEADERS` | Fallback if traces-specific headers are not set. |
| `TRACELOOP_TRACE_CONTENT` | Set to `false` to avoid logging prompt/completion text on spans (LangChain instrumentor). |

**Local collector (default)** — if nothing is set, traces go to `http://localhost:4318/v1/traces`.

```powershell
python agent_otel.py
```

**Confident AI via OTLP**

```powershell
$env:OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = "https://otel.confident-ai.com/v1/traces"
$env:OTEL_EXPORTER_OTLP_TRACES_HEADERS = "x-confident-api-key=YOUR_CONFIDENT_API_KEY"
python agent_otel.py
```

---

## Layout

| File | Purpose |
|------|--------|
| `workflow.py` | Shared graph and nodes; no observability. |
| `agent_confident.py` | Confident AI tracing via `deepeval` `@observe`. |
| `agent_otel.py` | OpenTelemetry + OTLP HTTP (`opentelemetry-instrumentation-langchain`). |
| `otel/` | Package: OTLP HTTP exporter helpers (`export.py`) used by `agent_otel.py`. |
