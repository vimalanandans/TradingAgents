# Point-In-Time Data Engineering & Ingestion Resilience

To support trustworthy historical backtests and resilient real-time executions, TradingAgents implements a decoupled, fallback-capable data ingestion router protected by strict **point-in-time and anti-lookahead guards**.

---

## 🔌 Unified Ingestion Router

Located in `tradingagents/dataflows/interface.py`, the ingestion layer maps high-level abstract tools requested by agents to specialized underlying data providers:

```
                  ┌──────────────────────┐
                  │ Abstract Tool Method │ (e.g. get_balance_sheet)
                  └──────────┬───────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │  route_to_vendor (Router)   │
              └──────────────┬──────────────┘
                             │
       ┌─────────────────────┼─────────────────────┐
       │ (User Configuration: data_vendors="yfinance,sec_edgar,alpha_vantage")
       ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐      ┌─────────────────────────────┐
│  yfinance    │      │  sec_edgar   │      │        alpha_vantage        │
│  (Primary)   │      │  (Fallback)  │      │         (Secondary)         │
└──────┬───────┘      └──────┬───────┘      └──────────────┬──────────────┘
       │                      │                            │
       └──────────────────────┴─────────────┬──────────────┘
                                            │ (If all fail / hit rate-limits)
                                            ▼
                             ┌─────────────────────────────┐
                             │ Graceful Sentinel Fallback  │
                             │ - NO_DATA_AVAILABLE         │
                             │ - DATA_UNAVAILABLE          │
                             └─────────────────────────────┘
```

### 1. Vendor Fallback Chains
*   **Explicit Configuration:** Users configure data provider preferences as a prioritized, comma-separated list (e.g., `data_vendors="yfinance,alpha_vantage"`).
*   **Tool-Level Overrides:** Tool-specific configurations (configured under `tool_vendors` in `config.py`) override category defaults.
*   **Contamination Safety:** The system never silently falls back to providers that are not configured by the user. If the user explicitly selects a set of vendors, only those are chained, eliminating cross-vendor data drift and unexpected api charges.
*   **Default Behavior:** If no configuration is supplied, the router maps all available implementations for that abstract method in a pre-defined native order.

### 2. Graceful Error Degradation & Sentinels
To prevent a complete system crash when facing API throttling or missing tickers, the router classifies errors and returns descriptive text sentinels:

*   **`NO_DATA_AVAILABLE` Sentinel:** If a provider returns a clean "no data" error (`NoMarketDataError`), the router catches it and returns a structured message detailing the failure reason (e.g. stale date, delisted, invalid ticker). This instructs the downstream LLM that the data is unavailable and explicitly commands it **not to fabricate or estimate** values.
*   **`DATA_UNAVAILABLE` Sentinel:** If all configured vendors hit rate-limits (`VendorRateLimitError`) or are unreachable, the router returns a message indicating transient unavailability, preventing the run from aborting and signaling to downstream agents that no conclusions can be drawn about the symbol.
*   **Flavor vs. Core Classification:** 
    *   **Core Categories:** (Prices, Balance Sheets, Income Statements, News) - Failure is loud. If all fallbacks are exhausted, the first real exception is reraised to halt the run.
    *   **Optional Categories:** (Macro indicators, Prediction markets) - Any failure is gracefully caught and degraded to a sentinel, ensuring supplementary event context cannot break the main trading lifecycle.

---

## 🛡️ Anti-Lookahead & Point-in-Time Guards

In financial ML and multi-agent backtesting, **lookahead bias** (where an agent inadvertently makes a decision based on information published *after* the simulated trade date) invalidates historical performance. TradingAgents implements **6 distinct guards** in `tradingagents/dataflows/date_window.py` to isolate the simulation timeline:

### 1. Strict UTC Normalization (`to_utc`)
All timestamps retrieved from news feeds, Reddit, and Stocktwits are immediately cast to UTC-aware datetime instances. Naive datetimes are assumed to be UTC, establishing a unified temporal baseline.

### 2. Time-Window Trimming (`in_window`)
All social posts and news articles are filtered using a half-open window `[start, end + 1 day)`. 
```python
def in_window(pub_dt: datetime | None, start_dt: datetime, end_dt: datetime) -> bool:
    end = to_utc(end_dt)
    if pub_dt is not None:
        return to_utc(start_dt) <= to_utc(pub_dt) < end + timedelta(days=1)
    return end >= datetime.now(timezone.utc) - timedelta(days=1)
```
*   **Undated Post Protection:** If an item is missing a timestamp, it is discarded in historical runs. It is kept **only** when the end-date reaches present-day (a live run), as future leakage cannot be disproven historically.

### 3. Coverage Gap Guard (`coverage_gap`)
Many social feeds (Reddit, Stocktwits) and Yahoo News APIs only serve recent items (e.g., the last 30 days) and ignore historical start-dates. Returning an empty list over an unobserved historical window would cause downstream agents to conclude that "zero social mentions occurred."
*   **Guard:** If the requested end-date is in the future, or if the oldest returned item is later than the requested start-date, `coverage_gap` returns a descriptive placeholder warning the agent that the feed was unobserved, rather than empty.

### 4. LLM Parameter Clamping (`as_of`)
Agents are allowed to dynamically adjust tool date arguments in their prompts. To prevent a model from requesting tomorrow's data, the router runs all LLM-supplied date strings through `as_of`, clamping any date that walks past the run's configured `trade_date`.

### 5. Historical Window Shift (`as_of_window`)
If an agent requests an indicator or OHLCV window that lies wholly in the future of the simulation trade date, `as_of_window` shifts the entire span backwards in time so it terminates exactly on the configured `trade_date`, preserving the requested window span length.

### 6. Company Profile Withholding (`withhold_live_profile`)
Corporate overview endpoints (such as yfinance `Ticker.info` or Alpha Vantage `OVERVIEW`) do not maintain historical vintage records. If queried, they return present-day valuation multiples, current sector classifications, and today's market capitalization—even if the simulation trade date is set in 2021.
*   **Guard:** If the simulation run date is prior to today, company profile queries are **withheld**. The router returns a clear message explaining that serving live multiples would violate lookahead safety, and instructs the agent to read historical statements (Balance Sheet, Cash Flow, Income Statement) instead.
