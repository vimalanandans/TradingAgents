# CLI Interface, State Persistence & Lifecycle

This document describes the state persistence layers, SQLite checkpointing mechanisms, and the real-time, interactive terminal dashboard that drives the TradingAgents user experience.

---

## 💾 Resumable State Checkpointing

To secure executions against network interruptions, LLM rate-limiting, and credentials errors, TradingAgents implements a highly resilient checkpointing architecture (located in `tradingagents/graph/checkpointer.py`).

### 1. Isolated Per-Ticker Databases
Traditional SQLite implementations often suffer from `database is locked` errors when multiple concurrent processes write to a single file.
*   **Resolution:** TradingAgents assigns each ticker its own isolated database file located at `<data_dir>/checkpoints/<TICKER>.db`.
*   **Safety:** Ticker values are passed through `safe_ticker_component` before directory resolution, preventing path-traversal vulnerabilities from unvalidated user inputs.
*   **Write-Ahead Logging (WAL):** During database deletion/clearance, the checkpointer unlinks the core `.db` file alongside its auxiliary `-wal` (Write-Ahead Log) and `-shm` (Shared Memory) sidecar files to prevent stale state reconstruction.

### 2. Signature-Hashed Thread IDs
A primary concern when resuming a previous checkpoint in LangGraph is ensuring the graph's topology has not shifted. Loading a checkpoint generated under a 4-analyst graph into a 2-analyst run would crash the state machine.
*   **Resolution:** Thread IDs are computed deterministically via a SHA-256 hash of the ticker, trade date, and a **graph setup choices signature**:
    ```python
    def thread_id(ticker: str, date: str, signature: str = "") -> str:
        base = f"{ticker.upper()}:{date}"
        if signature:
            base = f"{base}:{signature}"
        return hashlib.sha256(base.encode()).hexdigest()[:16]
    ```
*   **Effect:** Changing model providers, adding or removing analysts, or adjusting debate round parameters alters the `signature` hash. The system then automatically bypasses the old checkpoint and starts a clean run, guaranteeing state compatibility.

### 3. Fault Tolerance & Zero-Loss Resumes
*   **Lookup:** On initialization, `TradingAgentsGraph` checks for existing checkpoints (`has_checkpoint`).
*   **Resume:** If a valid checkpoint is present, LangGraph starts execution from the last successfully committed node, rather than repeating previous analyst tool loops. This saves significant API cost and time.
*   **Cleanup:** Successful decisions can be cleared or overridden by removing checkpoint records via `clear_checkpoint` or `clear_all_checkpoints`.

---

## 🖥️ Interactive Terminal TUI Dashboard

The primary user entry point is driven by a `Typer` application coupled with a real-time `Rich` terminal layout (located in `cli/main.py`).

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TRADINGAGENTS CLI DASHBOARD                     │
│  Ticker: AAPL  |  Date: 2026-09-19  |  LLM Provider: Anthropic (Sonnet)│
├────────────────────────────────────┬───────────────────────────────────┤
│                                    │                                   │
│      ACTIVE AGENT WORKBOARD        │       RUNNING EXECUTION LOGS      │
│                                    │                                   │
│  [Market Analyst]                  │  [14:10:05] Starting Graph Run... │
│  - Active: Tool Ingestion Loop     │  [14:10:12] Market Analyst active │
│  - Calling: get_indicators         │  [14:10:18] Cleared conversation  │
│  - Status: Fetching indicators...  │  [14:10:20] Sentiment Analyst...  │
│                                    │                                   │
├────────────────────────────────────┴───────────────────────────────────┤
│                                                                        │
│                          LIVE DECISION PREVIEW                         │
│                                                                        │
│   **Recommendation**: Buy                                              │
│   **Rationale**: Robust technical bounce off Bollinger Support...      │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│  Progress: [██████████████████████████████░░░░░░░░░░░] 75%  Cost: $0.14 │
└────────────────────────────────────────────────────────────────────────┘
```

### 1. Multi-Panel Rich Layout
The terminal screen is partitioned into several independent widgets that refresh concurrently using a `rich.live.Live` rendering context:
*   **Header Panel:** Displays global run configurations, active tickers, simulation date, and selected LLM model details.
*   **Agent Workboard Panel:** Shows which agent node is currently running, its active status (e.g., executing tool, formatting findings), and live tracking of token consumption and accumulated running cost (USD).
*   **Execution Logs Panel:** Serves as a scrolling trace log tracking state-machine transitions, database writes, and tool triggers.
*   **Decision Preview Panel:** Renders markdown reports (such as active debates, structured analyst summaries, and the finalized Portfolio Decision) as soon as they are written to the shared state.

### 2. Live Event Stream Consumption
The CLI reads the LangGraph execution as a real-time event generator:
```python
async for event in graph.astream_events(config, version="v2"):
    kind = event["event"]
    if kind == "on_chat_model_stream":
        # Stream raw tokens directly to the Active Agent Workboard
        ...
    elif kind == "on_tool_start":
        # Print active tool parameters to the Tool Panel
        ...
    elif kind == "on_node_end":
        # Log node completion and refresh state panels
        ...
```
This continuous feedback loop provides granular transparency into the multi-agent decision chain, letting users monitor the precise catalyst for every trade recommendation.
