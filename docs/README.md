# TradingAgents: Architecture & Orchestration Documentation

Welcome to the technical documentation suite for **TradingAgents**, a multi-agent LLM financial trading framework built on **LangGraph**. This suite details the architectural blueprints, multi-agent state machines, point-in-time data engineering, and state persistence of the platform.

---

## 🗺️ Documentation Map

To navigate the inner workings of TradingAgents, refer to the following specialized guides:

### 1. [Systemic Architecture & Design Patterns](architecture.md)
*   **Overview:** High-level system overview, technology stack, and systemic design patterns.
*   **Key Patterns:** Sequential Analysts, Round-Robin Debates, Lazy-Import Factories, and the Separation of Concerns.

### 2. [Multi-Agent Orchestration & State Machine](multi_agent_orchestration.md)
*   **Overview:** Comprehensive breakdown of the 12-agent graph topology, state schemas, and conditional transitions.
*   **Key Concepts:** `AgentState`, nested state TypedDicts, token-saving context-window wipes (`create_msg_delete`), and transition logic.

### 3. [Data Ingestion, Point-In-Time Guards & Resilience](data_ingestion_and_guards.md)
*   **Overview:** The resilient data-ingestion layer, vendor fallback chains, and strict anti-lookahead financial guards.
*   **Key Concepts:** Point-in-time date-clamping, live-profile withholding, coverage gap placeholders, and vendor-failure sentinels.

### 4. [LLM Client Factory & Model Capabilities](llm_clients.md)
*   **Overview:** The provider factory, lazy-loading imports, and declarative client registry.
*   **Key Concepts:** Model capabilities registry, provider thinking configurations, and custom client wrappers.

### 5. [CLI Interface, State Persistence & Lifecycle](cli_and_lifecycle.md)
*   **Overview:** The state checkpointing mechanics and the Rich-based terminal user interface.
*   **Key Concepts:** Per-ticker SQLite databases, signature-hashed thread IDs, state resumes, and multi-panel TUI.

### 6. [Context Management & Evaluation](context_management.md)
*   **Overview:** A comprehensive review of the framework's state-retention, token budgets, and lookahead guards.

### 7. [Langfuse Observability](langfuse_observability.md)
*   **Overview:** Optional cloud or self-hosted Langfuse tracing for graph runs, agents, LLM calls, tools, metadata, latency, and provider usage.
*   **Key Concepts:** The Clean-Slate pattern, nested state-machine isolation, atomic file swapping, and retrospective memory limits.

---

## 🚀 High-Level System Architecture

TradingAgents coordinates multiple specialized agents to analyze, debate, structure, and execute trade decisions. The data flow travels from raw external data feeds, through sequential domain-expert analysts, into competitive research and risk-mitigation debate rooms, and finally to the portfolio manager for execution sizing.

```
       [ CLI / Run Start ]
                │
                ▼
   [ Instrument Identity & Ticker ]
                │
                ▼
    [ Sequential Analyst Phase ] ◄────► [ Market Data Ingestion ]
      - Market Analyst                    - yfinance
      - Sentiment Analyst                 - sec_edgar
      - News Analyst                      - fred / polymarket
      - Fundamentals Analyst              - reddit / stocktwits
                │
                ▼
     [ Research Debate Loop ]
       - Bull Researcher
       - Bear Researcher
       - Research Manager (Judge)
                │
                ▼
     [ Trading Proposal Phase ]
       - Trader
                │
                ▼
      [ Risk Debate Loop ]
       - Aggressive Analyst
       - Conservative Analyst
       - Neutral Analyst
       - Portfolio Manager (Judge) ───► [ Persistent Markdown Report ]
                                  ───► [ SQLite Checkpoint Save ]
```
