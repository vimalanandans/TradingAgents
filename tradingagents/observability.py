"""Optional Langfuse observability for TradingAgents.

Tracing is deliberately opt-in and fail-open. The application must continue to
run when Langfuse is not configured or temporarily unavailable.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    value = os.getenv("LANGFUSE_TRACING_ENABLED", "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def create_langfuse_handler() -> Any | None:
    """Create the current Langfuse LangChain callback handler when configured.

    The Langfuse SDK reads ``LANGFUSE_PUBLIC_KEY``, ``LANGFUSE_SECRET_KEY`` and
    ``LANGFUSE_BASE_URL`` itself. The base URL supports both Langfuse Cloud and
    a local/self-hosted deployment. Returning ``None`` keeps tracing optional.
    """
    if not _enabled():
        return None

    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        logger.warning(
            "LANGFUSE_TRACING_ENABLED is true but Langfuse keys are missing; "
            "continuing without Langfuse tracing"
        )
        return None

    try:
        from langfuse.langchain import CallbackHandler

        return CallbackHandler()
    except Exception as exc:  # noqa: BLE001 - observability must not break runs
        logger.warning("Could not initialize Langfuse tracing: %s", exc)
        return None


def add_langfuse_callback(callbacks: list[Any]) -> list[Any]:
    """Return callbacks with one optional Langfuse handler appended."""
    handler = create_langfuse_handler()
    if handler is not None:
        callbacks.append(handler)
    return callbacks


def flush_langfuse() -> None:
    """Flush buffered Langfuse events at the end of a CLI/process run."""
    if not _enabled():
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception as exc:  # noqa: BLE001 - flushing must not break runs
        logger.warning("Could not flush Langfuse tracing: %s", exc)


def langfuse_run_metadata(selections: dict[str, Any]) -> dict[str, Any]:
    """Build low-cardinality metadata attached to every graph trace."""
    return {
        "ticker": selections.get("ticker"),
        "trade_date": selections.get("analysis_date"),
        "asset_type": selections.get("asset_type"),
        "llm_provider": selections.get("llm_provider"),
        "quick_model": selections.get("quick_think_llm"),
        "deep_model": selections.get("deep_think_llm"),
        "analysts": ",".join(
            getattr(analyst, "value", str(analyst))
            for analyst in selections.get("analysts", [])
        ),
    }
