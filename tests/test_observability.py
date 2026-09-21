import unittest
from unittest.mock import patch

from tradingagents.observability import langfuse_run_metadata


class LangfuseObservabilityTests(unittest.TestCase):
    def test_tracing_is_opt_in(self):
        with patch.dict("os.environ", {"LANGFUSE_TRACING_ENABLED": "false"}, clear=False):
            from tradingagents.observability import create_langfuse_handler

            self.assertIsNone(create_langfuse_handler())

    def test_metadata_is_low_cardinality_and_run_specific(self):
        metadata = langfuse_run_metadata(
            {
                "ticker": "NVDA",
                "analysis_date": "2026-09-19",
                "asset_type": "stock",
                "llm_provider": "google",
                "quick_think_llm": "gemini-flash",
                "deep_think_llm": "gemini-pro",
                "analysts": ["market", "news"],
            }
        )
        self.assertEqual(metadata["ticker"], "NVDA")
        self.assertEqual(metadata["trade_date"], "2026-09-19")
        self.assertEqual(metadata["analysts"], "market,news")
        self.assertNotIn("GOOGLE_API_KEY", str(metadata))
