# Systemic Architecture & Core Design Patterns

This document covers the high-level system boundaries, core technology stack, and structural design patterns of the **TradingAgents** framework.

---

## 🏗️ Architectural Overview

TradingAgents employs a layered, decoupled architecture designed to bridge real-time/historical financial data feeds, stateful multi-agent pipelines, and a high-fidelity interactive user interface.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        User Interface Layer                            │
│           Typer CLI  |  Rich Terminal Dashboard  |  Stdout Stream      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     Multi-Agent Orchestration Layer                    │
│      TradingAgentsGraph | LangGraph Engine | State-Machines (sqlite)   │
└───────────┬───────────────────────────────┬────────────────────────────┘
            │                               │
            ▼                               ▼
┌───────────────────────┐       ┌────────────────────────────────────────┐
│  LLM Provider Layer   │       │          Data Ingestion Layer          │
│                       │       │ Interface Router | Point-In-Time Guard │
│  - Anthropic Client   │       ├────────────────────────────────────────┤
│  - Google Client      │       │ - yfinance      | - sec_edgar          │
│  - OpenAI/Azure       │       │ - FRED          | - Polymarket         │
│  - Bedrock / OpenRouter│      │ - Reddit        | - Stocktwits         │
└───────────────────────┘       └────────────────────────────────────────┘
```

---

## 💻 Core Technology Stack

1.  **LangGraph (v0.4.8+)**:
    *   Provides the acyclic/cyclic graph definition mechanism (`StateGraph`).
    *   Manages execution steps, checkpointing, and thread-level state storage.
    *   Executes asynchronous and synchronous agent streams.
2.  **Pydantic (v2)**:
    *   Enforces static, structured outputs from decision-making LLM nodes (Research Manager, Trader, Portfolio Manager, Sentiment Analyst).
    *   Safeguards the pipeline from API payload drift and missing/null values via robust type-coercion helpers (`_coerce_optional_float`).
3.  **SQLite**:
    *   Provides transactionally-isolated, contention-free local checkpoint storage.
    *   Maintains historical steps to allow zero-data-loss execution resume if an API is interrupted or throttled.
4.  **Typer & Rich**:
    *   Powers the interactive CLI entrypoint and commands.
    *   Enforces an immersive, multi-pane terminal user interface (TUI) mapping running execution logs, token budgets, ongoing agent debates, and live results.

---

## 🧩 Architectural Design Patterns

### 1. Sequential-to-Competitive Pipeline Pattern
To prevent LLM "groupthink" and confirmation bias, the framework separates **objective data extraction** from **subjective thesis synthesis**.
*   **Sequential Analysts (Objective):** Analysts sequentially execute search-and-retrieval tool loops to isolate factual market statistics, sentiment trends, news, and financial filing entries.
*   **Competitive Debaters (Subjective):** Once the factual "reports" are recorded in the state, the framework enters a structured debate loop. The **Bull Researcher** and **Bear Researcher** argue under a strict turn-based protocol, refereed by the **Research Manager**. A second loop (the **Risk Debate**) pits **Aggressive**, **Conservative**, and **Neutral** perspectives against one another under the refereeing of the **Portfolio Manager**.

### 2. Conversational Context Wipe & Anchor (Clean-Slate) Pattern
A common problem in multi-agent LangGraph pipelines is the ballooning cost and attention-drift caused by carrying a single, long `MessagesState` across many different agents.
*   **Wipe:** When transitioning between sequential analysts, the `create_msg_delete` step returns `RemoveMessage` operations to erase the previous analyst's conversational history.
*   **Anchor:** To ensure the subsequent analyst is not left contextless, the wipe node injects a custom `HumanMessage` anchored to the deterministic, resolved ticker identity and trade date. This avoids LLM confusion while reducing context window usage by up to **80%**.

### 3. Decoupled Provider-Agnostic Client Factory Pattern
To keep the framework highly adaptable to multiple foundation models, all LLM clients inherit from a lightweight `BaseClient`.
*   **Lazy Loading:** Provider-specific SDKs (like `google-generativeai` or `boto3`) are loaded lazily within their respective factory methods. If a user only configures OpenAI, the framework does not attempt to import other heavyweight packages or crash on missing environment variables.
*   **Declarative Capabilities Registry:** Features like native structured output configurations, tool calling limits, and thinking effort levels are declared inside a central `capabilities.py` file, shielding agent prompt definitions from API variations.

### 4. Deterministic Identity Resolution (The Single-Source of Truth)
Before any agent tool is executed, the framework runs a deterministic symbol normalization pass using `resolve_instrument_identity`. This resolves crypto vs. stock types, matches exchange suffixes, and caches the security context in `instrument_context` within the graph's shared state. Downstream tools read this validated identity rather than performing lookup requests inside agent loops, which eliminates duplicate network requests and inconsistent symbol references.
