# Context Observability and Offline Analysis

This folder contains additive instrumentation and an offline trace analyzer.
It does not change the TradingAgents graph, prompts, reducers, model choices,
or context-management behavior.

## What is the context ledger?

The context ledger is a local JSON Lines (`.jsonl`) measurement file. Each line
is one callback event from a live analysis run. It records:

- graph/chain start and end lineage;
- state-field names, character sizes, estimated tokens, and hashes;
- message count, role, size, estimated tokens, and hashes at each LLM call;
- tool input/output sizes and hashes;
- provider usage metadata when the model callback provides it.

Raw prompts and tool contents are deliberately not copied into the ledger.
Langfuse remains the place to inspect raw trace payloads. Hashes let the
analyzer detect repeated or changed content without duplicating sensitive data.

The ledger is generated automatically during the CLI run. You do not create it
manually and you do not need to send it before starting the CLI.

## Enable ledger capture

Put this in `.env` before starting the CLI:

```dotenv
TRADINGAGENTS_CONTEXT_TRACE_PATH=results/context-ledger.jsonl
```

Then run the normal analysis command. If the variable is unset, ledger capture
is disabled. Enabling it does not change the analysis result; it only adds a
measurement callback.

The path may be absolute or relative to the repository. A single file can hold
multiple runs; every event includes a `run_id`, ticker, trade date, model
metadata, and timestamp.

## Configuration namespaces

Keep these groups separate in `.env`:

| Prefix | Purpose | Changes live analysis model? |
|---|---|---|
| `TRADINGAGENTS_*` | Live CLI provider, models, run settings, and ledger path | Yes, for live settings |
| `LANGFUSE_*` | Langfuse collection and destination | No |
| `CONTEXT_ANALYZER_*` | Offline LLM review of downloaded traces | No |

Example:

```dotenv
# Live analysis settings
TRADINGAGENTS_LLM_PROVIDER=google
TRADINGAGENTS_QUICK_THINK_LLM=gemini-3.8-flash
TRADINGAGENTS_DEEP_THINK_LLM=gemini-3.1-pro-preview
TRADINGAGENTS_CONTEXT_TRACE_PATH=results/context-ledger.jsonl

# Offline reviewer settings; independent from the live analysis model
CONTEXT_ANALYZER_PROVIDER=google
CONTEXT_ANALYZER_MODEL=gemini-2.5-flash
CONTEXT_ANALYZER_OUT_DIR=context_observability/reports
CONTEXT_ANALYZER_LEDGER_PATH=results/context-ledger.jsonl
```

The analyzer uses the same provider API key convention as the clients:
`GOOGLE_API_KEY` for Google or `OPENAI_API_KEY` for OpenAI.

## Analyze a downloaded Langfuse trace

After exporting a trace from Langfuse, run:

```bash
./.venv/bin/python -m context_observability.analyze_trace \
  /path/to/trace.json
```

The provider, model, output directory, and ledger path come from the
`CONTEXT_ANALYZER_*` variables. Command-line flags override `.env` values:

```bash
./.venv/bin/python -m context_observability.analyze_trace \
  /path/to/trace.json \
  --provider google \
  --model gemini-2.5-flash \
  --ledger results/context-ledger.jsonl
```

The analyzer writes a report such as:

```text
context_observability/reports/trace_context_analysis.md
```

Each report contains deterministic measurements followed by an LLM review with
proven findings, context-loss indicators, temporal/data risks, performance
findings, evidence gaps, and recommended experiments. Trace contents are
treated as untrusted evidence, not instructions to the reviewer model.

## Recommended workflow

1. Configure Langfuse and `TRADINGAGENTS_CONTEXT_TRACE_PATH` in `.env`.
2. Run the normal CLI analysis.
3. Export the corresponding Langfuse trace JSON.
4. Run the offline analyzer with `CONTEXT_ANALYZER_LEDGER_PATH` pointing to the
   ledger produced by that run.
5. Compare multiple reports before changing context-management logic.

This produces evidence about context growth, clearing, repetition, tool
payloads, temporal risks, latency, and token usage. It does not by itself prove
that a larger context caused a wrong investment decision; add evaluation scores
or controlled repeated runs for that conclusion.
