"""Tests for bot/handler.py — webhook handling, routing, error handling.

We mock bot.telegram_client._post which is the single mockable point
for all Telegram API calls. handler.py imports the module (not functions),
so patching _post on the module works reliably.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from bot.handler import lambda_handler
import bot.telegram_client as tg


@pytest.fixture(autouse=True)
def mock_telegram(monkeypatch):
    """Replace _post on the telegram_client module for every test."""
    mock = MagicMock(return_value={"ok": True, "result": {}})
    monkeypatch.setattr(tg, "_post", mock)
    # Allow our test chat_id through
    import bot.handler
    monkeypatch.setattr(bot.handler, "TELEGRAM_CHAT_ID", "8565010087")
    return mock


class TestMessageHandling:
    def test_help_command_responds(self, mock_telegram):
        result = lambda_handler(_event("/help"), None)
        assert result["statusCode"] == 200
        mock_telegram.assert_called()
        endpoint, payload = _last_send(mock_telegram)
        assert endpoint == "sendMessage"
        assert payload["chat_id"] == "8565010087"
        assert "PORTFOLIO" in payload["text"]

    def test_help_specific_command(self, mock_telegram):
        lambda_handler(_event("/help brief"), None)
        _, payload = _last_send(mock_telegram)
        assert "Morning Intelligence Brief" in payload["text"]

    def test_start_command_shows_help(self, mock_telegram):
        lambda_handler(_event("/start"), None)
        _, payload = _last_send(mock_telegram)
        assert "PORTFOLIO" in payload["text"]

    def test_unknown_command_returns_error(self, mock_telegram):
        lambda_handler(_event("/foobar"), None)
        _, payload = _last_send(mock_telegram)
        assert "Unknown command" in payload["text"]

    @patch("bot.commands.get_portfolio")
    def test_portfolio_command(self, mock_get, mock_telegram):
        mock_get.return_value = [
            {"position_type": "shares", "ticker": "AMZN", "shares": 100, "cost_basis": 250.0}
        ]
        lambda_handler(_event("/portfolio"), None)
        _, payload = _last_send(mock_telegram)
        assert "AMZN" in payload["text"]

    @patch("bot.commands.add_to_watchlist")
    def test_watch_command(self, mock_add, mock_telegram):
        lambda_handler(_event("/watch NVDA"), None)
        mock_add.assert_called_once_with("8565010087", "NVDA")
        _, payload = _last_send(mock_telegram)
        assert "NVDA" in payload["text"]

    def test_update_no_args(self, mock_telegram):
        lambda_handler(_event("/update"), None)
        _, payload = _last_send(mock_telegram)
        assert "Usage" in payload["text"]

    def test_update_unparseable(self, mock_telegram):
        lambda_handler(_event("/update random text here"), None)
        _, payload = _last_send(mock_telegram)
        assert "Couldn't parse" in payload["text"]


class TestCallbackQueries:
    def test_callback_processes_command(self, mock_telegram):
        event = {
            "body": json.dumps({
                "callback_query": {
                    "id": "abc123",
                    "message": {"chat": {"id": 8565010087}},
                    "data": "/help",
                }
            })
        }
        result = lambda_handler(event, None)
        assert result["statusCode"] == 200
        endpoints = [c[0][0] for c in mock_telegram.call_args_list]
        assert "answerCallbackQuery" in endpoints
        assert "sendMessage" in endpoints


class TestEdgeCases:
    def test_empty_text(self, mock_telegram):
        result = lambda_handler(_event(""), None)
        assert result["statusCode"] == 200
        mock_telegram.assert_not_called()

    def test_no_text_field(self, mock_telegram):
        event = {"body": json.dumps({"message": {"chat": {"id": 123}}})}
        result = lambda_handler(event, None)
        assert result["statusCode"] == 200
        mock_telegram.assert_not_called()

    def test_no_message(self, mock_telegram):
        result = lambda_handler({"body": json.dumps({})}, None)
        assert result["statusCode"] == 200

    def test_invalid_json(self, mock_telegram):
        result = lambda_handler({"body": "not json"}, None)
        assert result["statusCode"] == 200

    def test_no_body(self, mock_telegram):
        result = lambda_handler({}, None)
        assert result["statusCode"] == 200

    def test_whitespace_text(self, mock_telegram):
        result = lambda_handler(_event("   "), None)
        assert result["statusCode"] == 200
        mock_telegram.assert_not_called()


class TestAccessControl:
    def test_wrong_chat_id_ignored(self, mock_telegram):
        with patch("bot.handler.TELEGRAM_CHAT_ID", "123"):
            lambda_handler(_event("/help", chat_id=999), None)
            mock_telegram.assert_not_called()

    def test_empty_chat_id_allows_all(self, mock_telegram):
        with patch("bot.handler.TELEGRAM_CHAT_ID", ""):
            lambda_handler(_event("/help", chat_id=999), None)
            mock_telegram.assert_called()


class TestErrorHandling:
    def test_route_error_sends_error_message(self, mock_telegram):
        with patch("bot.handler.route_command", side_effect=Exception("kaboom")):
            result = lambda_handler(_event("/pnl"), None)
            assert result["statusCode"] == 200
            mock_telegram.assert_called()
            _, payload = _last_send(mock_telegram)
            assert "Something went wrong" in payload["text"]

    def test_telegram_failure_doesnt_crash(self, mock_telegram):
        mock_telegram.side_effect = Exception("Telegram down")
        with patch("bot.commands.route_command", side_effect=Exception("boom")):
            result = lambda_handler(_event("/pnl"), None)
            assert result["statusCode"] == 200


# ── Helpers ────────────────────────────────────────────────────────────────

def _event(text: str, chat_id: int = 8565010087) -> dict:
    return {"body": json.dumps({"message": {"chat": {"id": chat_id}, "text": text}})}


def _last_send(mock_post) -> tuple[str, dict]:
    for c in reversed(mock_post.call_args_list):
        if c[0][0] == "sendMessage":
            return c[0][0], c[0][1]
    raise AssertionError(f"No sendMessage call found. Calls: {mock_post.call_args_list}")
