# Langfuse Observability

TradingAgents supports optional Langfuse tracing without changing the agent
workflow. Tracing is disabled by default and is fail-open: missing credentials
or a telemetry outage must not stop an analysis.

## Configuration

Copy `.env.example` to `.env`, then set:

```dotenv
LANGFUSE_TRACING_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

For the US Langfuse Cloud region, use `https://us.cloud.langfuse.com`. For a
self-hosted deployment, set `LANGFUSE_BASE_URL` to the URL reachable by the
TradingAgents process, commonly `http://localhost:3000`.

The callback receives the run metadata for ticker, trade date, asset type,
provider, selected models, and selected analysts. LangChain/LangGraph callbacks
then capture nested graph, LLM, and tool activity, including inputs/outputs
where supported by the installed integrations, latency, errors, and provider
usage metadata.

## Local Docker or Podman

Run Langfuse using the official self-hosting Compose configuration. Docker
Compose and Podman Compose are both suitable; keep the Langfuse services and
their database volumes outside the TradingAgents process. Configure the
TradingAgents `.env` file with the reachable Langfuse URL after the services
start.

```bash
# From the Langfuse self-hosting checkout
docker compose up -d
# or
podman compose up -d
```

Use `LANGFUSE_BASE_URL=http://localhost:3000` when both applications run on the
same host. If TradingAgents runs in another container, use the Compose service
name or host gateway address instead of `localhost`.

## Trace identity and experiment metadata

Each CLI analysis is named `tradingagents.analysis` and tagged with
`tradingagents`, `analysis`, and the asset type. Low-cardinality metadata
identifies the ticker, analysis date, provider, models, and analyst set. Do not
put API keys, portfolio secrets, or unrestricted account data in metadata.

Use Langfuse tags and metadata to compare controlled experiments, for example:

```text
baseline-market-only
all-analysts
all-analysts-with-memory
deep-debate
```

The existing `StatsCallbackHandler` remains active for the CLI display. It
continues to provide local aggregate counters while Langfuse provides the
durable nested trace.

## Context ledger and offline review

For context-loss measurement, set this in `.env` before starting the normal
CLI:

```dotenv
TRADINGAGENTS_CONTEXT_TRACE_PATH=results/context-ledger.jsonl
```

This creates a local JSONL ledger automatically during the run. It records
lineage, state/message sizes, hashes, tool sizes, and callback usage metadata;
it does not modify prompts or store raw prompt contents. See
[`context_observability/README.md`](../context_observability/README.md) for the
complete workflow and the separate `CONTEXT_ANALYZER_*` settings used to review
an exported trace with Gemini or OpenAI. Those analyzer settings do not change
the provider or model used by the live TradingAgents analysis.

## What this first integration does not claim

Tracing records what the framework sends and receives; it does not yet enforce
context or spend budgets. Before adding context compression, compare traces for
message count, prompt size, report repetition, debate growth, tool latency,
provider usage, and final decision quality. Budget enforcement should be added
as a separate callback after baseline evidence is collected.

If Langfuse usage metadata is unavailable from a provider, token and cost fields
may be incomplete. Treat provider-reported usage as authoritative and use local
character/token estimates only as diagnostics.
