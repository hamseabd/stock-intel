"""Tests for tools/portfolio.py — trade parsing and portfolio updates."""

import pytest
from unittest.mock import patch, MagicMock

from tools.portfolio import parse_trade_text, update_portfolio


class TestParseTradeText:
    def test_sold_at(self):
        result = parse_trade_text("sold 50 AMZN at 195")
        assert result == {"action": "sell", "ticker": "AMZN", "shares": 50.0, "price": 195.0}

    def test_bought_at(self):
        result = parse_trade_text("bought 100 AMD at 165.50")
        assert result == {"action": "buy", "ticker": "AMD", "shares": 100.0, "price": 165.50}

    def test_buy_at_sign(self):
        result = parse_trade_text("buy 20 QQQ @ 420")
        assert result == {"action": "buy", "ticker": "QQQ", "shares": 20.0, "price": 420.0}

    def test_sell_with_dollar(self):
        result = parse_trade_text("sell 10 SPY at $502")
        assert result == {"action": "sell", "ticker": "SPY", "shares": 10.0, "price": 502.0}

    def test_buy_no_at(self):
        result = parse_trade_text("buy 50 NVDA 800")
        assert result == {"action": "buy", "ticker": "NVDA", "shares": 50.0, "price": 800.0}

    def test_case_insensitive(self):
        result = parse_trade_text("BOUGHT 10 amzn AT 200")
        assert result["action"] == "buy"
        assert result["ticker"] == "AMZN"

    def test_fractional_shares(self):
        result = parse_trade_text("bought 0.5 BTC at 50000")
        assert result["shares"] == 0.5

    def test_unparseable(self):
        assert parse_trade_text("what is my portfolio?") is None

    def test_empty(self):
        assert parse_trade_text("") is None

    def test_missing_price(self):
        assert parse_trade_text("sold 50 AMZN") is None

    def test_just_ticker(self):
        assert parse_trade_text("AMZN") is None


class TestUpdatePortfolio:
    @patch("tools.portfolio.get_positions")
    @patch("tools.portfolio.put_position")
    @patch("tools.portfolio.log_trade")
    def test_buy_new_position(self, mock_log, mock_put, mock_get):
        mock_get.return_value = []
        result = update_portfolio("123", "buy", "NVDA", shares=10, price=800.0)
        assert "New position" in result
        assert "NVDA" in result
        mock_put.assert_called_once()
        mock_log.assert_called_once()

    @patch("tools.portfolio.get_positions")
    @patch("tools.portfolio.put_position")
    @patch("tools.portfolio.log_trade")
    def test_buy_add_to_existing(self, mock_log, mock_put, mock_get):
        mock_get.return_value = [
            {"position_type": "shares", "ticker": "AMZN", "shares": 100, "cost_basis": 250.0}
        ]
        result = update_portfolio("123", "buy", "AMZN", shares=50, price=200.0)
        assert "150" in result  # 100 + 50
        assert "Bought" in result

    @patch("tools.portfolio.get_positions")
    @patch("tools.portfolio.put_position")
    @patch("tools.portfolio.log_trade")
    def test_sell_partial(self, mock_log, mock_put, mock_get):
        mock_get.return_value = [
            {"position_type": "shares", "ticker": "AMZN", "shares": 100, "cost_basis": 250.0}
        ]
        result = update_portfolio("123", "sell", "AMZN", shares=50, price=200.0)
        assert "Sold" in result
        assert "P&L" in result

    @patch("tools.portfolio.get_positions")
    @patch("tools.portfolio.put_position")
    @patch("tools.portfolio.delete_position")
    @patch("tools.portfolio.log_trade")
    def test_sell_full_close(self, mock_log, mock_del, mock_put, mock_get):
        mock_get.return_value = [
            {"position_type": "shares", "ticker": "AMZN", "shares": 100, "cost_basis": 250.0}
        ]
        result = update_portfolio("123", "sell", "AMZN", shares=100, price=200.0)
        assert "closed" in result.lower()
        mock_del.assert_called_once()

    @patch("tools.portfolio.get_positions")
    def test_sell_no_position(self, mock_get):
        mock_get.return_value = []
        result = update_portfolio("123", "sell", "XYZ", shares=10, price=100.0)
        assert "No share position" in result

    @patch("tools.portfolio.get_positions")
    def test_sell_too_many(self, mock_get):
        mock_get.return_value = [
            {"position_type": "shares", "ticker": "AMZN", "shares": 10, "cost_basis": 250.0}
        ]
        result = update_portfolio("123", "sell", "AMZN", shares=50, price=200.0)
        assert "Can't sell" in result

    @patch("tools.portfolio.get_positions")
    @patch("tools.portfolio.put_position")
    @patch("tools.portfolio.log_trade")
    def test_add_option(self, mock_log, mock_put, mock_get):
        mock_get.return_value = []
        result = update_portfolio("123", "add_option", "AMD",
                                  option_type="put", strike=230.0, expiry="2026-05-15", contracts=1, price=5.0)
        assert "Added" in result
        assert "AMD" in result

    @patch("tools.portfolio.get_positions")
    @patch("tools.portfolio.delete_position")
    @patch("tools.portfolio.log_trade")
    def test_close_option(self, mock_log, mock_del, mock_get):
        mock_get.return_value = [
            {"position_type": "option", "ticker": "AMD", "option_type": "put",
             "strike": 230.0, "expiry": "2026-05-15", "status": "open"}
        ]
        result = update_portfolio("123", "close_option", "AMD", strike=230.0, expiry="2026-05-15")
        assert "Closed" in result

    @patch("tools.portfolio.get_positions")
    def test_unknown_action(self, mock_get):
        mock_get.return_value = []
        result = update_portfolio("123", "yolo", "AMZN")
        assert "Unknown action" in result
