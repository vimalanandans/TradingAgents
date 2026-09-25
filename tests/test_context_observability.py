import json

from context_observability.analyze_trace import summarize
from tradingagents.observability import ContextTraceCallback


def test_context_callback_writes_measurement_only_ledger(tmp_path):
    path = tmp_path / "context.jsonl"
    callback = ContextTraceCallback(path, {"ticker": "TEST"})

    callback.on_chain_start(
        {"id": ["tests", "chain"]},
        {"messages": [{"role": "user", "content": "hello"}]},
        run_id="chain-1",
    )
    callback.on_chat_model_start(
        {},
        [[{"role": "user", "content": "hello"}]],
        run_id="llm-1",
        parent_run_id="chain-1",
        invocation_params={"model": "test-model"},
    )

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["event"] for row in rows] == ["chain_start", "llm_start"]
    assert rows[1]["messages"]["count"] == 1
    assert "content" not in rows[1]["messages"]["items"][0]


def test_trace_summary_extracts_temporal_evidence():
    summary = summarize(
        {
            "observations": [
                {
                    "type": "AGENT",
                    "traceName": "test",
                    "traceId": "trace-1",
                    "metadata": {"trade_date": "2026-09-22"},
                },
                {
                    "type": "TOOL",
                    "name": "tool",
                    "output": '{"as_of": "2026-09-23"}',
                },
            ]
        }
    )
    assert summary["future_dates_relative_to_trade_date"] == ["2026-09-23"]
