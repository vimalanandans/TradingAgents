"""Optional Langfuse observability for TradingAgents.

Tracing is deliberately opt-in and fail-open. The application must continue to
run when Langfuse is not configured or temporarily unavailable.
"""

from __future__ import annotations

import logging
import os
import hashlib
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

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


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except Exception:  # noqa: BLE001 - telemetry must never fail the run
        return str(value)


def _digest(value: Any) -> str:
    return hashlib.sha256(_text(value).encode("utf-8")).hexdigest()


def _message_summary(message: Any, index: int) -> dict[str, Any]:
    if isinstance(message, dict):
        role = message.get("role") or message.get("type") or "unknown"
        content = message.get("content", "")
    else:
        role = getattr(message, "type", None) or type(message).__name__
        content = getattr(message, "content", str(message))
    content_text = _text(content)
    return {
        "index": index,
        "role": role,
        "chars": len(content_text),
        "estimated_tokens": max(1, len(content_text) // 4) if content_text else 0,
        "sha256": _digest(content_text),
    }


def _state_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"type": type(value).__name__, "chars": len(_text(value))}
    summary: dict[str, Any] = {}
    for key, item in value.items():
        if key == "messages" and isinstance(item, (list, tuple)):
            summary[key] = {
                "count": len(item),
                "chars": len(_text(item)),
                "estimated_tokens": max(1, len(_text(item)) // 4) if item else 0,
                "items": [_message_summary(m, i) for i, m in enumerate(item)],
            }
        elif isinstance(item, str):
            summary[key] = {
                "chars": len(item),
                "estimated_tokens": max(1, len(item) // 4) if item else 0,
                "sha256": _digest(item),
                "present": bool(item),
            }
        elif isinstance(item, dict):
            summary[key] = {
                "chars": len(_text(item)),
                "sha256": _digest(item),
                "keys": sorted(str(k) for k in item),
            }
        else:
            summary[key] = {"type": type(item).__name__, "chars": len(_text(item))}
    return summary


class ContextTraceCallback(BaseCallbackHandler):
    """Measurement-only JSONL ledger for context and trajectory analysis.

    It records sizes, hashes, lineage, timing, and provider usage rather than
    changing prompts or graph state. Raw prompt content is intentionally not
    copied into this ledger; Langfuse remains the opt-in source for payloads.
    """

    def __init__(self, path: str | Path, run_metadata: dict[str, Any] | None = None):
        super().__init__()
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = str(uuid.uuid4())
        self.run_metadata = run_metadata or {}
        self._lock = threading.Lock()

    def _write(self, event: str, **payload: Any) -> None:
        record = {
            "run_id": self.run_id,
            "event": event,
            "timestamp": time.time(),
            **self.run_metadata,
            **payload,
        }
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, default=str) + "\n")

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
        serialized_id = serialized.get("id")
        fallback_name = (
            serialized_id[-1]
            if isinstance(serialized_id, list) and serialized_id
            else serialized_id or "chain"
        )
        name = kwargs.get("name") or serialized.get("name") or fallback_name
        self._write(
            "chain_start",
            span_id=str(run_id),
            parent_span_id=str(parent_run_id) if parent_run_id else None,
            name=name,
            state=_state_summary(inputs),
        )

    def on_chain_end(self, outputs, *, run_id, parent_run_id=None, **kwargs):
        self._write(
            "chain_end",
            span_id=str(run_id),
            parent_span_id=str(parent_run_id) if parent_run_id else None,
            output_state=_state_summary(outputs),
        )

    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs):
        flattened = messages[0] if messages and isinstance(messages[0], list) else messages
        self._write(
            "llm_start",
            span_id=str(run_id),
            parent_span_id=str(parent_run_id) if parent_run_id else None,
            model=kwargs.get("invocation_params", {}).get("model"),
            messages={
                "count": len(flattened),
                "chars": len(_text(flattened)),
                "estimated_tokens": max(1, len(_text(flattened)) // 4) if flattened else 0,
                "items": [_message_summary(m, i) for i, m in enumerate(flattened)],
            },
        )

    def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
        usage = {}
        try:
            generation = response.generations[0][0]
            usage = getattr(generation.message, "usage_metadata", None) or {}
        except (AttributeError, IndexError, TypeError):
            pass
        self._write(
            "llm_end",
            span_id=str(run_id),
            parent_span_id=str(parent_run_id) if parent_run_id else None,
            usage=usage,
        )

    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, **kwargs):
        self._write(
            "tool_start",
            span_id=str(run_id),
            parent_span_id=str(parent_run_id) if parent_run_id else None,
            name=kwargs.get("name") or serialized.get("name"),
            input_chars=len(_text(input_str)),
            input_sha256=_digest(input_str),
        )

    def on_tool_end(self, output, *, run_id, parent_run_id=None, **kwargs):
        self._write(
            "tool_end",
            span_id=str(run_id),
            parent_span_id=str(parent_run_id) if parent_run_id else None,
            output_chars=len(_text(output)),
            output_sha256=_digest(output),
        )
