"""Tests for tools/options.py and tools/options_flow.py — NaN handling, Greeks, flow detection."""

import math
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock


class TestOptionsNaNHandling:
    """The critical bug: yfinance returns NaN for volume/OI on some contracts."""

    def test_safe_int_nan(self):
        """int(float('nan')) raises ValueError — our code must handle it."""
        val = float("nan")
        # This is what caused the production crash:
        with pytest.raises(ValueError):
            int(val)
        # Our fix:
        result = 0 if (val is None or (isinstance(val, float) and math.isnan(val))) else int(val)
        assert result == 0

    def test_safe_int_none(self):
        val = None
        result = 0 if (val is None or (isinstance(val, float) and math.isnan(val))) else int(val)
        assert result == 0

    def test_safe_int_normal(self):
        val = 5000.0
        result = 0 if (val is None or (isinstance(val, float) and math.isnan(val))) else int(val)
        assert result == 5000

    def test_safe_float_nan(self):
        val = float("nan")
        result = 0.0 if (val is None or (isinstance(val, float) and math.isnan(val))) else float(val)
        assert result == 0.0


class TestOptionsFlowNaN:
    """Test that scan_options_flow handles NaN in real yfinance data."""

    @patch("tools.options_flow.yf.Ticker")
    def test_nan_volume_doesnt_crash(self, mock_ticker):
        from tools.options_flow import scan_options_flow

        # Mock a chain with NaN values
        mock_tkr = MagicMock()
        mock_tkr.options = ["2026-05-15"]

        calls_df = pd.DataFrame({
            "strike": [200.0, 210.0, 220.0],
            "volume": [1000, float("nan"), 500],
            "openInterest": [200, float("nan"), 100],
            "bid": [5.0, float("nan"), 2.0],
            "ask": [5.5, float("nan"), 2.5],
        })
        puts_df = pd.DataFrame({
            "strike": [200.0, 210.0],
            "volume": [float("nan"), 800],
            "openInterest": [float("nan"), 150],
            "bid": [float("nan"), 3.0],
            "ask": [float("nan"), 3.5],
        })

        chain = MagicMock()
        chain.calls = calls_df
        chain.puts = puts_df
        mock_tkr.option_chain.return_value = chain
        mock_ticker.return_value = mock_tkr

        # This should NOT raise ValueError
        result = scan_options_flow("TEST")
        assert "error" not in result
        assert isinstance(result["put_call_ratio"], float)

    @patch("tools.options_flow.yf.Ticker")
    def test_all_nan_chain(self, mock_ticker):
        from tools.options_flow import scan_options_flow

        mock_tkr = MagicMock()
        mock_tkr.options = ["2026-05-15"]

        # Everything is NaN
        df = pd.DataFrame({
            "strike": [200.0],
            "volume": [float("nan")],
            "openInterest": [float("nan")],
            "bid": [float("nan")],
            "ask": [float("nan")],
        })
        chain = MagicMock()
        chain.calls = df
        chain.puts = df
        mock_tkr.option_chain.return_value = chain
        mock_ticker.return_value = mock_tkr

        result = scan_options_flow("TEST")
        assert result["total_call_volume"] == 0
        assert result["total_put_volume"] == 0

    @patch("tools.options_flow.yf.Ticker")
    def test_no_options_available(self, mock_ticker):
        from tools.options_flow import scan_options_flow

        mock_tkr = MagicMock()
        mock_tkr.options = []
        mock_ticker.return_value = mock_tkr

        result = scan_options_flow("TEST")
        assert result["alerts"] == []


class TestAnalyzeOption:
    @patch("tools.options.yf.Ticker")
    def test_nan_fields_handled(self, mock_ticker):
        from tools.options import analyze_option

        mock_tkr = MagicMock()
        mock_tkr.fast_info.last_price = 200.0
        mock_tkr.options = ["2026-05-15"]

        df = pd.DataFrame({
            "strike": [210.0],
            "bid": [float("nan")],
            "ask": [float("nan")],
            "impliedVolatility": [float("nan")],
            "volume": [float("nan")],
            "openInterest": [float("nan")],
        })
        chain = MagicMock()
        chain.puts = df
        mock_tkr.option_chain.return_value = chain
        mock_ticker.return_value = mock_tkr

        result = analyze_option("TEST", 210.0, "2026-05-15", "put")
        assert "error" not in result
        assert result["bid"] == 0.0
        assert result["volume"] == 0
        assert result["open_interest"] == 0


class TestAnalyzeAllOptions:
    @patch("tools.options.analyze_option")
    def test_skips_closed_options(self, mock_analyze):
        from tools.options import analyze_all_options

        positions = [
            {"position_type": "option", "ticker": "AMD", "strike": 250, "expiry": "2026-05-15",
             "option_type": "call", "status": "closed"},
        ]
        result = analyze_all_options(positions)
        assert result == []
        mock_analyze.assert_not_called()

    @patch("tools.options.analyze_option")
    def test_skips_shares(self, mock_analyze):
        from tools.options import analyze_all_options

        positions = [{"position_type": "shares", "ticker": "AMZN", "shares": 100, "cost_basis": 250}]
        result = analyze_all_options(positions)
        assert result == []
