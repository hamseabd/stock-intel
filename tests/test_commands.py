"""Tests for bot/commands.py — command routing and all command handlers."""

import pytest
from unittest.mock import patch, MagicMock

from bot.commands import route_command, DIRECT_COMMANDS, AI_COMMANDS


class TestCommandRouting:
    def test_all_direct_commands_registered(self):
        expected = [
            "/pnl", "/portfolio", "/options", "/put", "/update", "/history",
            "/news", "/flow", "/technicals", "/darkpool", "/congress", "/earnings",
            "/movers", "/sector", "/scan", "/compare",
            "/watch", "/unwatch", "/watchlist", "/alerts", "/threshold",
            "/help", "/start",
        ]
        for cmd in expected:
            assert cmd in DIRECT_COMMANDS, f"{cmd} not registered"

    def test_all_ai_commands_registered(self):
        expected = ["/brief", "/catalyst", "/risk", "/analyze", "/ask"]
        for cmd in expected:
            assert cmd in AI_COMMANDS, f"{cmd} not registered"

    @patch("bot.commands.DIRECT_COMMANDS")
    def test_routes_to_help(self, mock_cmds):
        mock_fn = MagicMock(return_value="help text")
        mock_cmds.__contains__ = lambda self, key: key == "/help"
        mock_cmds.__getitem__ = lambda self, key: mock_fn
        result = route_command("123", "/help")
        mock_fn.assert_called_once_with("123", "")

    def test_routes_help_returns_content(self):
        result = route_command("123", "/help")
        assert "PORTFOLIO" in result

    def test_routes_help_specific_command(self):
        result = route_command("123", "/help brief")
        assert "Morning Intelligence Brief" in result

    @patch("bot.commands.handle_ask")
    def test_freeform_text_goes_to_ai(self, mock_ask):
        mock_ask.return_value = "answer"
        result = route_command("123", "What should I do with AMD?")
        mock_ask.assert_called_once()

    def test_unknown_command(self):
        result = route_command("123", "/foobar")
        assert "Unknown command" in result

    def test_empty_input(self):
        result = route_command("123", "")
        assert "/help" in result


class TestCmdHelp:
    def test_main_help(self):
        from bot.commands import cmd_help
        result = cmd_help("123", "")
        assert "PORTFOLIO" in result
        assert "RESEARCH" in result
        assert "AI-POWERED" in result

    def test_specific_command_help(self):
        from bot.commands import cmd_help
        result = cmd_help("123", "brief")
        assert "Morning Intelligence Brief" in result

    def test_unknown_command_help(self):
        from bot.commands import cmd_help
        result = cmd_help("123", "nonexistent")
        assert "Unknown command" in result


class TestCmdPnl:
    @patch("bot.commands.get_portfolio")
    def test_no_positions(self, mock_get):
        from bot.commands import cmd_pnl
        mock_get.return_value = []
        result = cmd_pnl("123", "")
        assert "No positions" in result

    @patch("bot.commands.fetch_prices")
    @patch("bot.commands.calculate_portfolio_pnl")
    @patch("bot.commands.get_portfolio")
    def test_with_positions(self, mock_get, mock_pnl, mock_prices):
        from bot.commands import cmd_pnl
        mock_get.return_value = [
            {"position_type": "shares", "ticker": "AMZN", "shares": 100, "cost_basis": 250}
        ]
        mock_prices.return_value = {"AMZN": 200.0}
        mock_pnl.return_value = {
            "positions": [{"ticker": "AMZN", "shares": 100, "cost_basis": 250, "current_price": 200,
                           "market_value": 20000, "dollar_pnl": -5000, "pct_pnl": -20.0}],
            "totals": {"total_cost": 25000, "total_value": 20000, "total_dollar_pnl": -5000, "total_pct_pnl": -20.0},
        }
        result = cmd_pnl("123", "")
        assert "AMZN" in result

    @patch("bot.commands.fetch_prices")
    @patch("bot.commands.calculate_portfolio_pnl")
    @patch("bot.commands.get_portfolio")
    def test_single_ticker(self, mock_get, mock_pnl, mock_prices):
        from bot.commands import cmd_pnl
        mock_get.return_value = [
            {"position_type": "shares", "ticker": "AMZN", "shares": 100, "cost_basis": 250}
        ]
        mock_prices.return_value = {"AMZN": 200.0}
        mock_pnl.return_value = {
            "positions": [{"ticker": "AMZN", "shares": 100, "cost_basis": 250, "current_price": 200,
                           "market_value": 20000, "dollar_pnl": -5000, "pct_pnl": -20.0}],
            "totals": {"total_cost": 25000, "total_value": 20000, "total_dollar_pnl": -5000, "total_pct_pnl": -20.0},
        }
        result = cmd_pnl("123", "AMZN")
        assert "AMZN" in result


class TestCmdUpdate:
    def test_no_args(self):
        from bot.commands import cmd_update
        result = cmd_update("123", "")
        assert "Usage" in result

    @patch("bot.commands.update_portfolio")
    def test_valid_trade(self, mock_update):
        from bot.commands import cmd_update
        mock_update.return_value = "Sold 50 AMZN at $195.00."
        result = cmd_update("123", "sold 50 AMZN at 195")
        assert "Sold" in result

    def test_unparseable(self):
        from bot.commands import cmd_update
        result = cmd_update("123", "do something weird")
        assert "Couldn't parse" in result


class TestCmdWatch:
    @patch("bot.commands.add_to_watchlist")
    def test_single(self, mock_add):
        from bot.commands import cmd_watch
        result = cmd_watch("123", "NVDA")
        assert "NVDA" in result
        mock_add.assert_called_once()

    @patch("bot.commands.add_to_watchlist")
    def test_multiple(self, mock_add):
        from bot.commands import cmd_watch
        result = cmd_watch("123", "NVDA TSLA PLTR")
        assert "NVDA" in result
        assert mock_add.call_count == 3

    def test_no_args(self):
        from bot.commands import cmd_watch
        result = cmd_watch("123", "")
        assert "Usage" in result


class TestCmdAlerts:
    @patch("bot.commands.get_price_alerts")
    @patch("bot.commands.get_alert_config")
    def test_show_config(self, mock_config, mock_prices):
        from bot.commands import cmd_alerts
        mock_config.return_value = {"enabled": True, "congress": True}
        mock_prices.return_value = []
        result = cmd_alerts("123", "")
        assert "ON" in result

    @patch("bot.commands.put_alert_config")
    @patch("bot.commands.get_alert_config")
    def test_enable(self, mock_get, mock_put):
        from bot.commands import cmd_alerts
        mock_get.return_value = {"enabled": False}
        result = cmd_alerts("123", "on")
        assert "enabled" in result

    @patch("bot.commands.put_alert_config")
    @patch("bot.commands.get_alert_config")
    def test_disable(self, mock_get, mock_put):
        from bot.commands import cmd_alerts
        mock_get.return_value = {"enabled": True}
        result = cmd_alerts("123", "off")
        assert "disabled" in result

    @patch("bot.commands.put_alert_config")
    @patch("bot.commands.get_alert_config")
    def test_mute(self, mock_get, mock_put):
        from bot.commands import cmd_alerts
        mock_get.return_value = {"enabled": True}
        result = cmd_alerts("123", "mute 2h")
        assert "muted" in result.lower()

    @patch("bot.commands.put_alert_config")
    @patch("bot.commands.get_alert_config")
    def test_toggle_type(self, mock_get, mock_put):
        from bot.commands import cmd_alerts
        mock_get.return_value = {"enabled": True, "congress": True}
        result = cmd_alerts("123", "congress off")
        assert "congress" in result.lower()


class TestCmdThreshold:
    def test_no_args(self):
        from bot.commands import cmd_threshold
        result = cmd_threshold("123", "")
        assert "Usage" in result

    @patch("bot.commands.put_price_alert")
    def test_set_above(self, mock_put):
        from bot.commands import cmd_threshold
        result = cmd_threshold("123", "AMZN above 200")
        assert "AMZN" in result
        assert "above" in result
        mock_put.assert_called_once()

    @patch("bot.commands.put_price_alert")
    def test_set_below(self, mock_put):
        from bot.commands import cmd_threshold
        result = cmd_threshold("123", "AMD below 155")
        assert "AMD" in result
        mock_put.assert_called_once()

    @patch("bot.commands.delete_price_alerts")
    def test_clear(self, mock_del):
        from bot.commands import cmd_threshold
        result = cmd_threshold("123", "clear AMZN")
        assert "Cleared" in result
        mock_del.assert_called_once()

    def test_invalid_direction(self):
        from bot.commands import cmd_threshold
        result = cmd_threshold("123", "AMZN sideways 200")
        assert "above" in result or "below" in result

    def test_invalid_price(self):
        from bot.commands import cmd_threshold
        result = cmd_threshold("123", "AMZN above notanumber")
        assert "Invalid" in result
