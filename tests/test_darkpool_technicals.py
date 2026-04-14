"""Tests for tools/darkpool.py and tools/technicals.py."""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from tools.darkpool import analyze_darkpool_trend, get_darkpool_flags
from tools.technicals import get_technical_flags


class TestDarkpoolTrend:
    def test_rising(self):
        # Recent avg ~45, older avg ~32 — difference > 5 → rising
        data = [
            {"dark_pct": 46.0}, {"dark_pct": 45.0}, {"dark_pct": 44.0},
            {"dark_pct": 33.0}, {"dark_pct": 32.0}, {"dark_pct": 31.0},
        ]
        trend = analyze_darkpool_trend(data)
        assert trend == "rising"

    def test_falling(self):
        data = [
            {"dark_pct": 30.0}, {"dark_pct": 31.0}, {"dark_pct": 29.0},  # recent: avg ~30
            {"dark_pct": 45.0}, {"dark_pct": 44.0}, {"dark_pct": 46.0},  # older: avg ~45
        ]
        trend = analyze_darkpool_trend(data)
        assert trend == "falling"

    def test_stable(self):
        data = [
            {"dark_pct": 35.0}, {"dark_pct": 36.0}, {"dark_pct": 34.0},
            {"dark_pct": 35.0}, {"dark_pct": 36.0}, {"dark_pct": 34.0},
        ]
        trend = analyze_darkpool_trend(data)
        assert trend == "stable"

    def test_insufficient_data(self):
        data = [{"dark_pct": 40.0}]
        trend = analyze_darkpool_trend(data)
        assert trend == "insufficient data"

    def test_empty(self):
        trend = analyze_darkpool_trend([])
        assert trend == "insufficient data"


class TestDarkpoolFlags:
    @patch("tools.darkpool.fetch_darkpool")
    def test_flags_high_dark_pct(self, mock_fetch):
        mock_fetch.return_value = [
            {"dark_pct": 48.0, "short_pct": 42.0, "date": "2026-04-10", "total_volume": 100000},
            {"dark_pct": 45.0, "short_pct": 40.0, "date": "2026-04-09", "total_volume": 95000},
            {"dark_pct": 35.0, "short_pct": 38.0, "date": "2026-04-08", "total_volume": 90000},
        ]
        flags = get_darkpool_flags(["AMD"], threshold=40.0)
        assert len(flags) == 1
        assert flags[0]["ticker"] == "AMD"
        assert flags[0]["dark_pct"] == 48.0

    @patch("tools.darkpool.fetch_darkpool")
    def test_flags_high_short_pct(self, mock_fetch):
        mock_fetch.return_value = [
            {"dark_pct": 35.0, "short_pct": 55.0, "date": "2026-04-10", "total_volume": 100000},
            {"dark_pct": 34.0, "short_pct": 52.0, "date": "2026-04-09", "total_volume": 95000},
            {"dark_pct": 33.0, "short_pct": 50.0, "date": "2026-04-08", "total_volume": 90000},
        ]
        flags = get_darkpool_flags(["AMD"], threshold=40.0)
        assert len(flags) == 1  # short_pct > 50 triggers

    @patch("tools.darkpool.fetch_darkpool")
    def test_no_flags_normal(self, mock_fetch):
        mock_fetch.return_value = [
            {"dark_pct": 32.0, "short_pct": 38.0, "date": "2026-04-10", "total_volume": 100000},
            {"dark_pct": 31.0, "short_pct": 37.0, "date": "2026-04-09", "total_volume": 95000},
            {"dark_pct": 33.0, "short_pct": 39.0, "date": "2026-04-08", "total_volume": 90000},
        ]
        flags = get_darkpool_flags(["AMD"])
        assert flags == []

    @patch("tools.darkpool.fetch_darkpool")
    def test_empty_data(self, mock_fetch):
        mock_fetch.return_value = []
        flags = get_darkpool_flags(["AMD"])
        assert flags == []


class TestTechnicalFlags:
    @patch("tools.technicals.analyze_technicals")
    def test_oversold_flagged(self, mock_analyze):
        mock_analyze.return_value = {
            "ticker": "AMD", "price": 165, "rsi_14": 25.0,
            "macd_line": -1.0, "macd_signal": -0.5, "macd_histogram": -0.5,
            "sma_50": 180, "sma_200": 195, "overall_signal": "bearish",
        }
        flags = get_technical_flags(["AMD"])
        assert len(flags) == 1
        assert any("oversold" in r for r in flags[0]["reasons"])

    @patch("tools.technicals.analyze_technicals")
    def test_overbought_flagged(self, mock_analyze):
        mock_analyze.return_value = {
            "ticker": "AMZN", "price": 250, "rsi_14": 78.0,
            "macd_line": 2.0, "macd_signal": 1.5, "macd_histogram": 0.5,
            "sma_50": 230, "sma_200": 210, "overall_signal": "bullish",
        }
        flags = get_technical_flags(["AMZN"])
        assert any("overbought" in r for r in flags[0]["reasons"])

    @patch("tools.technicals.analyze_technicals")
    def test_no_flags_neutral(self, mock_analyze):
        # RSI normal (50), MACD flat (line == signal), price == SMAs
        mock_analyze.return_value = {
            "ticker": "SPY", "price": 500, "rsi_14": 50.0,
            "macd_line": 0.0, "macd_signal": 0.0, "macd_histogram": 0.0,
            "sma_50": 500, "sma_200": 500, "overall_signal": "neutral",
        }
        flags = get_technical_flags(["SPY"])
        assert flags == []

    @patch("tools.technicals.analyze_technicals")
    def test_error_ticker_skipped(self, mock_analyze):
        mock_analyze.return_value = {"error": "Insufficient data."}
        flags = get_technical_flags(["XYZ"])
        assert flags == []
