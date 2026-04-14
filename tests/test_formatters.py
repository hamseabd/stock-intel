"""Tests for shared/formatters.py — string formatting, no I/O."""

import pytest

from shared.formatters import (
    format_pnl_table,
    format_options_table,
    format_risk_flags,
    format_news,
    format_flow,
    format_technicals,
    format_congress_trades,
    format_darkpool,
    format_earnings,
    format_movers,
    format_watchlist,
    format_alert_config,
    format_alert_price,
    format_alert_flow,
    format_alert_congress,
    format_alert_congress_cluster,
    format_alert_earnings,
    format_alert_options_expiry,
    format_alert_darkpool,
    format_alert_technical,
    html_escape,
)


class TestFormatPnlTable:
    def test_basic(self):
        positions = [
            {"ticker": "AMZN", "shares": 100, "cost_basis": 250.0, "current_price": 198.50,
             "market_value": 19850.0, "dollar_pnl": -5150.0, "pct_pnl": -20.6},
        ]
        totals = {"total_cost": 25000, "total_value": 19850, "total_dollar_pnl": -5150, "total_pct_pnl": -20.6}
        result = format_pnl_table(positions, totals)
        assert "AMZN" in result
        assert "PORTFOLIO" in result
        assert "TOTAL" in result

    def test_flags_drawdown(self):
        positions = [
            {"ticker": "AMD", "shares": 200, "cost_basis": 222.5, "current_price": 165.30,
             "market_value": 33060.0, "dollar_pnl": -11440.0, "pct_pnl": -25.7},
        ]
        totals = {"total_cost": 44500, "total_value": 33060, "total_dollar_pnl": -11440, "total_pct_pnl": -25.7}
        result = format_pnl_table(positions, totals)
        assert "!!" in result  # drawdown flag

    def test_empty_positions(self):
        result = format_pnl_table([], {"total_cost": 0, "total_value": 0, "total_dollar_pnl": 0, "total_pct_pnl": 0})
        assert "TOTAL" in result


class TestFormatOptionsTable:
    def test_basic(self):
        options = [
            {"ticker": "AMD", "option_type": "call", "strike": 250, "expiry": "2026-05-15",
             "dte": 35, "delta": 0.12, "recommendation": "hold"},
        ]
        result = format_options_table(options)
        assert "AMD" in result
        assert "call" in result

    def test_empty(self):
        result = format_options_table([])
        assert "No open options" in result


class TestFormatRiskFlags:
    def test_with_flags(self):
        flags = [
            {"severity": "HIGH", "message": "AMD down 25%"},
            {"severity": "MEDIUM", "message": "Earnings in 7 days"},
        ]
        result = format_risk_flags(flags)
        assert "AMD down 25%" in result
        assert "!!" in result

    def test_no_flags(self):
        result = format_risk_flags([])
        assert "No urgent" in result


class TestFormatNews:
    def test_with_headlines(self, sample_headlines):
        result = format_news("AMZN", sample_headlines)
        assert "AMZN" in result
        assert "AI chip" in result

    def test_empty_headlines(self):
        result = format_news("XYZ", [])
        assert "No recent headlines" in result


class TestFormatFlow:
    def test_with_alerts(self):
        alerts = [
            {"option_type": "call", "strike": 200, "expiry": "2026-05-15",
             "volume": 15000, "volume_oi_ratio": 8.3, "premium": 1800000, "direction": "bullish"},
        ]
        result = format_flow("AMZN", alerts, 0.8, {"bullish": 1800000, "bearish": 200000})
        assert "AMZN" in result
        assert "bullish" in result
        assert "15,000" in result

    def test_no_alerts(self):
        result = format_flow("XYZ", [], 1.0, {"bullish": 0, "bearish": 0})
        assert "No unusual" in result


class TestFormatTechnicals:
    def test_basic(self):
        t = {
            "price": 165.30, "rsi_14": 29.5, "macd_line": -1.2, "macd_signal": -0.8,
            "macd_histogram": -0.4, "sma_50": 180.0, "sma_200": 195.0,
            "bb_upper": 190.0, "bb_middle": 175.0, "bb_lower": 160.0,
            "support": 155.0, "resistance": 180.0, "avg_volume": 50000000,
            "current_volume": 62000000, "overall_signal": "bearish",
        }
        result = format_technicals("AMD", t)
        assert "AMD" in result
        assert "BEARISH" in result
        assert "oversold" in result


class TestFormatCongressTrades:
    def test_with_trades_and_clusters(self, sample_congress_trades):
        clusters = [{"ticker": "NVDA", "members": ["Pelosi", "Tuberville", "Crenshaw"], "direction": "buying"}]
        result = format_congress_trades(sample_congress_trades, clusters)
        assert "NVDA" in result
        assert "CLUSTER" in result

    def test_empty(self):
        result = format_congress_trades([])
        assert "No recent" in result


class TestFormatDarkpool:
    def test_with_data(self, sample_darkpool_data):
        result = format_darkpool("AMD", sample_darkpool_data, "rising")
        assert "AMD" in result
        assert "45.0%" in result
        assert "HIGH" in result

    def test_empty(self):
        result = format_darkpool("XYZ", [], "stable")
        assert "No dark pool" in result


class TestFormatEarnings:
    def test_basic(self):
        tickers = [
            {"ticker": "AMD", "next_earnings_date": "2026-04-28", "days_away": 14},
            {"ticker": "AMZN", "next_earnings_date": "2026-05-01", "days_away": 21},
        ]
        result = format_earnings(tickers)
        assert "AMD" in result
        assert "SOON" in result

    def test_this_week(self):
        tickers = [{"ticker": "TSLA", "next_earnings_date": "2026-04-17", "days_away": 3}]
        result = format_earnings(tickers)
        assert "THIS WEEK" in result

    def test_empty(self):
        result = format_earnings([])
        assert "No earnings" in result


class TestFormatMovers:
    def test_basic(self):
        movers = [
            {"ticker": "AMD", "price": 170.0, "change_pct": 4.2},
            {"ticker": "AMZN", "price": 195.0, "change_pct": -1.8},
        ]
        result = format_movers(movers)
        assert "AMD" in result
        assert "+4.2%" in result
        assert "-1.8%" in result


class TestFormatWatchlist:
    def test_with_tickers(self):
        result = format_watchlist(["NVDA", "TSLA"])
        assert "NVDA" in result
        assert "TSLA" in result

    def test_empty(self):
        result = format_watchlist([])
        assert "Empty" in result


class TestFormatAlertConfig:
    def test_basic(self):
        config = {"enabled": True, "congress": True, "flow": False}
        result = format_alert_config(config, [])
        assert "ON" in result

    def test_with_price_alerts(self):
        config = {"enabled": True}
        price_alerts = [{"ticker": "AMZN", "direction": "above", "target_price": 200.0}]
        result = format_alert_config(config, price_alerts)
        assert "AMZN" in result
        assert "above" in result


# ── Alert Formatters ───────────────────────────────────────────────────────

class TestAlertFormatters:
    def test_price_alert(self):
        result = format_alert_price("AMD", 155.0, -5.2, "Big drop")
        assert "AMD" in result
        assert "DOWN" in result

    def test_flow_alert(self):
        result = format_alert_flow("AMZN", 200, "2026-05-15", "call", 15000, 1800, 1800000, "bullish")
        assert "AMZN" in result
        assert "8.3x" in result

    def test_congress_alert(self):
        trade = {"member": "Pelosi", "party": "D", "tx_type": "Purchase", "ticker": "NVDA",
                 "amount": "$1M-5M", "filing_date": "2026-04-08"}
        result = format_alert_congress(trade)
        assert "Pelosi" in result
        assert "NVDA" in result

    def test_congress_cluster(self):
        result = format_alert_congress_cluster("NVDA", ["Pelosi", "Tuberville", "Crenshaw"], "buying")
        assert "3 members" in result

    def test_earnings_alert(self):
        result = format_alert_earnings("AMD", 3)
        assert "3 days" in result

    def test_options_expiry_alert(self):
        result = format_alert_options_expiry("AMD", "call", 250, 3, 0.12, "let_expire")
        assert "AMD" in result
        assert "EXPIRING" in result

    def test_darkpool_alert(self):
        result = format_alert_darkpool("AMD", 45.0, 52.0)
        assert "45.0%" in result

    def test_technical_alert(self):
        result = format_alert_technical("AMD", "bearish", "RSI 29 (oversold)")
        assert "AMD" in result


class TestHtmlEscape:
    def test_ampersand(self):
        assert html_escape("A&B") == "A&amp;B"

    def test_angle_brackets(self):
        assert html_escape("<script>") == "&lt;script&gt;"

    def test_clean_text(self):
        assert html_escape("Hello World") == "Hello World"
