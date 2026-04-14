"""End-to-end tests for every bot command.

Simulates: Telegram webhook → Lambda handler → command router → tools → formatters → Telegram response.

External deps mocked: Telegram API, DynamoDB, yfinance, FINRA, Capitol Trades, RSS feeds.
Internal code runs for real: handler, router, commands, tools, math, formatters.
"""

import json
import math
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import date, timedelta

import bot.telegram_client as tg
from bot.handler import lambda_handler


# ── Fixtures ───────────────────────────────────────────────────────────────

CHAT_ID = "8565010087"


@pytest.fixture(autouse=True)
def mock_telegram(monkeypatch):
    """Mock Telegram API — capture all outgoing messages."""
    sent = []

    def fake_post(endpoint, payload, timeout=10):
        sent.append({"endpoint": endpoint, "payload": payload})
        return {"ok": True, "result": {}}

    monkeypatch.setattr(tg, "_post", fake_post)

    import bot.handler
    monkeypatch.setattr(bot.handler, "TELEGRAM_CHAT_ID", CHAT_ID)

    return sent


@pytest.fixture
def mock_portfolio():
    """Mock DynamoDB portfolio with realistic positions.

    Patches get_positions at every module that imports it so the mock works
    no matter which code path calls it.
    """
    positions = [
        {"position_type": "shares", "ticker": "AMZN", "shares": 100, "cost_basis": 250.0,
         "chat_id": CHAT_ID, "position_id": "share#AMZN"},
        {"position_type": "shares", "ticker": "AMD", "shares": 200, "cost_basis": 222.5,
         "chat_id": CHAT_ID, "position_id": "share#AMD"},
        {"position_type": "shares", "ticker": "SPY", "shares": 18, "cost_basis": 445.0,
         "chat_id": CHAT_ID, "position_id": "share#SPY"},
        {"position_type": "shares", "ticker": "QQQ", "shares": 20, "cost_basis": 385.0,
         "chat_id": CHAT_ID, "position_id": "share#QQQ"},
        {"position_type": "option", "ticker": "AMD", "option_type": "call",
         "strategy": "covered_call", "strike": 250.0, "expiry": "2026-05-15",
         "contracts": 2, "cost_basis": 15.23, "status": "open",
         "chat_id": CHAT_ID, "position_id": "opt#AMD#250.0#2026-05-15"},
    ]
    with patch("shared.db.get_positions", return_value=positions), \
         patch("tools.portfolio.get_positions", return_value=positions), \
         patch("bot.commands.get_portfolio", return_value=positions), \
         patch("bot.ai_commands.get_positions", return_value=positions), \
         patch("shared.db.put_position"), \
         patch("tools.portfolio.put_position"), \
         patch("shared.db.delete_position"), \
         patch("tools.portfolio.delete_position"), \
         patch("shared.db.log_trade"), \
         patch("tools.portfolio.log_trade"):
        yield positions


@pytest.fixture
def mock_prices():
    """Mock yfinance price downloads."""
    price_data = {"AMZN": 198.50, "AMD": 165.30, "SPY": 502.10, "QQQ": 421.50}

    def fake_download(tickers, **kwargs):
        if isinstance(tickers, str):
            tickers = [tickers]
        if len(tickers) == 1:
            t = tickers[0]
            return pd.DataFrame({"Close": [price_data.get(t, 100.0)]})
        data = {("Close", t): [price_data.get(t, 100.0)] for t in tickers}
        return pd.DataFrame(data)

    with patch("tools.prices.yf.download", side_effect=fake_download):
        yield price_data


@pytest.fixture
def mock_yf_ticker():
    """Mock yfinance Ticker for options chains and earnings."""
    def make_ticker(symbol):
        tkr = MagicMock()
        tkr.fast_info.last_price = {"AMZN": 198.50, "AMD": 165.30, "SPY": 502.10, "QQQ": 421.50}.get(symbol, 200.0)
        tkr.options = ["2026-05-15", "2026-06-20"]

        # Options chain with some NaN values (the bug we fixed)
        calls_df = pd.DataFrame({
            "strike": [190.0, 200.0, 210.0, 220.0],
            "volume": [500, 12000, 300, float("nan")],
            "openInterest": [1000, 1500, 800, float("nan")],
            "bid": [12.0, 5.0, 1.5, float("nan")],
            "ask": [12.5, 5.5, 2.0, float("nan")],
            "impliedVolatility": [0.35, 0.32, 0.38, float("nan")],
        })
        puts_df = pd.DataFrame({
            "strike": [190.0, 200.0, 210.0, 250.0],
            "volume": [800, float("nan"), 6000, 100],
            "openInterest": [600, float("nan"), 500, 200],
            "bid": [2.0, float("nan"), 8.0, 45.0],
            "ask": [2.5, float("nan"), 8.5, 46.0],
            "impliedVolatility": [0.30, float("nan"), 0.33, 0.40],
        })
        chain = MagicMock()
        chain.calls = calls_df
        chain.puts = puts_df
        tkr.option_chain.return_value = chain

        # Earnings
        future_date = date.today() + timedelta(days=18)
        earnings_df = pd.DataFrame(
            {"Surprise(%)": [8.0]},
            index=pd.DatetimeIndex([future_date])
        )
        tkr.get_earnings_dates.return_value = earnings_df
        tkr.calendar = {"Earnings Date": [future_date]}
        tkr.history.return_value = pd.DataFrame({"Close": [200.0]})

        return tkr

    with patch("tools.options.yf.Ticker", side_effect=make_ticker), \
         patch("tools.options_flow.yf.Ticker", side_effect=make_ticker), \
         patch("tools.earnings.yf.Ticker", side_effect=make_ticker):
        yield


@pytest.fixture
def mock_news():
    """Mock Yahoo Finance RSS feed."""
    def fake_parse(url):
        feed = MagicMock()
        feed.entries = [
            MagicMock(title="Amazon announces new AI chip partnership",
                      summary="AWS expands custom silicon lineup.",
                      published="2026-04-14T08:00:00", link="https://example.com/1"),
            MagicMock(title="AMZN beats Q1 revenue estimates",
                      summary="Revenue up 12%.", published="2026-04-13T16:00:00",
                      link="https://example.com/2"),
        ]
        # Make .get() work on mock entries
        for e in feed.entries:
            e.get = lambda key, default="", _e=e: getattr(_e, key, default)
        return feed

    with patch("tools.news.feedparser.parse", side_effect=fake_parse):
        yield


@pytest.fixture
def mock_congress_db():
    """Mock congressional trade data in DynamoDB."""
    trades = [
        {"member": "Nancy Pelosi", "party": "D", "chamber": "House", "state": "CA",
         "ticker": "NVDA", "tx_type": "Purchase", "amount": "$1,000,001 - $5,000,000",
         "trade_date": "2026-04-01", "filing_date": "2026-04-08",
         "committees": ["Financial Services"], "signals": ["whale_trade"]},
        {"member": "Tommy Tuberville", "party": "R", "chamber": "Senate", "state": "AL",
         "ticker": "NVDA", "tx_type": "Purchase", "amount": "$250,001 - $500,000",
         "trade_date": "2026-04-03", "filing_date": "2026-04-09",
         "committees": ["Armed Services"], "signals": []},
        {"member": "Dan Crenshaw", "party": "R", "chamber": "House", "state": "TX",
         "ticker": "AMZN", "tx_type": "Purchase", "amount": "$100,001 - $250,000",
         "trade_date": "2026-04-05", "filing_date": "2026-04-10",
         "committees": ["Intelligence"], "signals": ["intelligence_committee"]},
    ]
    with patch("shared.db.query_congress_by_ticker", return_value=trades), \
         patch("shared.db.query_congress_recent", return_value=trades), \
         patch("tools.congress.query_congress_by_ticker", return_value=trades), \
         patch("tools.congress.query_congress_recent", return_value=trades):
        yield trades


@pytest.fixture
def mock_darkpool():
    """Mock FINRA dark pool data."""
    def fake_fetch(ticker, days=14):
        return [
            {"ticker": ticker, "date": "2026-04-11", "dark_volume": 45000000,
             "total_volume": 100000000, "dark_pct": 45.0, "short_volume": 52000000, "short_pct": 52.0},
            {"ticker": ticker, "date": "2026-04-10", "dark_volume": 42000000,
             "total_volume": 95000000, "dark_pct": 44.2, "short_volume": 48000000, "short_pct": 50.5},
            {"ticker": ticker, "date": "2026-04-09", "dark_volume": 33000000,
             "total_volume": 100000000, "dark_pct": 33.0, "short_volume": 35000000, "short_pct": 35.0},
            {"ticker": ticker, "date": "2026-04-08", "dark_volume": 32000000,
             "total_volume": 98000000, "dark_pct": 32.7, "short_volume": 34000000, "short_pct": 34.7},
        ]

    with patch("tools.darkpool.fetch_darkpool", side_effect=fake_fetch), \
         patch("bot.commands.fetch_darkpool", side_effect=fake_fetch), \
         patch("bot.ai_commands.fetch_darkpool", side_effect=fake_fetch), \
         patch("bot.commands.analyze_darkpool_trend", return_value="rising"), \
         patch("bot.ai_commands.analyze_darkpool_trend", return_value="rising"), \
         patch("bot.commands.get_darkpool_flags", return_value=[
             {"ticker": "AMD", "dark_pct": 45.0, "short_pct": 52.0, "trend": "rising", "date": "2026-04-11"}
         ]), \
         patch("bot.ai_commands.get_darkpool_flags", return_value=[
             {"ticker": "AMD", "dark_pct": 45.0, "short_pct": 52.0, "trend": "rising", "date": "2026-04-11"}
         ]):
        yield


@pytest.fixture
def mock_technicals():
    """Mock price history for technicals."""
    np.random.seed(42)
    n = 130
    prices = 200.0 * np.cumprod(1 + np.random.normal(0.001, 0.02, n))

    def fake_history(ticker, period="6mo"):
        return {
            "closes": prices.tolist(),
            "volumes": (np.random.uniform(30e6, 80e6, n)).tolist(),
            "highs": (prices * 1.01).tolist(),
            "lows": (prices * 0.99).tolist(),
        }

    with patch("tools.technicals.fetch_price_history", side_effect=fake_history):
        yield


@pytest.fixture
def mock_watchlist():
    with patch("shared.db.get_watchlist", return_value=["NVDA", "TSLA"]), \
         patch("bot.commands.get_watchlist", return_value=["NVDA", "TSLA"]), \
         patch("bot.ai_commands.get_watchlist", return_value=["NVDA", "TSLA"]), \
         patch("shared.db.add_to_watchlist"), \
         patch("bot.commands.add_to_watchlist"), \
         patch("shared.db.remove_from_watchlist"), \
         patch("bot.commands.remove_from_watchlist"):
        yield


@pytest.fixture
def mock_alerts_db():
    config = {"chat_id": CHAT_ID, "enabled": True, "congress": True, "flow": True,
              "darkpool": True, "technicals": True, "earnings": True, "price": True}
    with patch("shared.db.get_alert_config", return_value=config), \
         patch("bot.commands.get_alert_config", return_value=config), \
         patch("shared.db.put_alert_config"), \
         patch("bot.commands.put_alert_config"), \
         patch("shared.db.get_price_alerts", return_value=[]), \
         patch("bot.commands.get_price_alerts", return_value=[]), \
         patch("shared.db.put_price_alert"), \
         patch("bot.commands.put_price_alert"), \
         patch("shared.db.delete_price_alerts"), \
         patch("bot.commands.delete_price_alerts"):
        yield config


@pytest.fixture
def mock_trade_history():
    trades = [
        {"timestamp": "2026-04-10T10:15:00", "action": "sell", "ticker": "AMZN",
         "shares": 50, "price": 195.0, "realized_pnl": -2750.0},
        {"timestamp": "2026-04-09T14:30:00", "action": "buy", "ticker": "AMD",
         "shares": 100, "price": 170.0},
    ]
    with patch("shared.db.get_trade_history", return_value=trades), \
         patch("bot.commands.get_trade_history", return_value=trades):
        yield


# ── Helpers ────────────────────────────────────────────────────────────────

def send(text: str) -> dict:
    """Simulate sending a Telegram message and return the event."""
    return {"body": json.dumps({"message": {"chat": {"id": int(CHAT_ID)}, "text": text}})}


def get_response(sent: list) -> str:
    """Extract the bot's response text from captured Telegram calls."""
    for msg in reversed(sent):
        if msg["endpoint"] == "sendMessage":
            return msg["payload"]["text"]
    return ""


def get_all_responses(sent: list) -> list[str]:
    """Get all sendMessage texts (for long messages split into chunks)."""
    return [m["payload"]["text"] for m in sent if m["endpoint"] == "sendMessage"]


# ── PORTFOLIO COMMANDS ─────────────────────────────────────────────────────

class TestE2E_Help:
    def test_help_shows_all_categories(self, mock_telegram):
        lambda_handler(send("/help"), None)
        resp = get_response(mock_telegram)
        assert "PORTFOLIO" in resp
        assert "RESEARCH" in resp
        assert "INTELLIGENCE" in resp
        assert "AI-POWERED" in resp
        assert "WATCHLIST" in resp
        assert "/pnl" in resp
        assert "/brief" in resp
        assert "/congress" in resp

    def test_help_specific_command(self, mock_telegram):
        lambda_handler(send("/help flow"), None)
        resp = get_response(mock_telegram)
        assert "Unusual Options Activity" in resp
        assert "Volume" in resp
        assert "$0" in resp

    def test_help_unknown_command(self, mock_telegram):
        lambda_handler(send("/help foobar"), None)
        resp = get_response(mock_telegram)
        assert "Unknown command" in resp

    def test_start_shows_help(self, mock_telegram):
        lambda_handler(send("/start"), None)
        resp = get_response(mock_telegram)
        assert "PORTFOLIO" in resp


class TestE2E_Pnl:
    def test_pnl_all_positions(self, mock_telegram, mock_portfolio, mock_prices):
        lambda_handler(send("/pnl"), None)
        resp = get_response(mock_telegram)
        assert "AMZN" in resp
        assert "AMD" in resp
        assert "SPY" in resp
        assert "QQQ" in resp
        assert "TOTAL" in resp

    def test_pnl_single_ticker(self, mock_telegram, mock_portfolio, mock_prices):
        lambda_handler(send("/pnl AMZN"), None)
        resp = get_response(mock_telegram)
        assert "AMZN" in resp
        assert "TOTAL" in resp

    def test_pnl_no_positions(self, mock_telegram):
        with patch("shared.db.get_positions", return_value=[]), \
             patch("tools.portfolio.get_positions", return_value=[]), \
             patch("bot.commands.get_portfolio", return_value=[]):
            lambda_handler(send("/pnl"), None)
            resp = get_response(mock_telegram)
            assert "No positions" in resp

    def test_pnl_nonexistent_ticker(self, mock_telegram, mock_portfolio, mock_prices):
        lambda_handler(send("/pnl XYZ"), None)
        resp = get_response(mock_telegram)
        assert "No share position" in resp


class TestE2E_Portfolio:
    def test_portfolio_shows_all(self, mock_telegram, mock_portfolio):
        lambda_handler(send("/portfolio"), None)
        resp = get_response(mock_telegram)
        assert "AMZN" in resp
        assert "100" in resp
        assert "Shares" in resp or "shares" in resp
        assert "AMD" in resp
        assert "Options" in resp or "call" in resp
        assert "$250" in resp  # strike

    def test_portfolio_empty(self, mock_telegram):
        with patch("bot.commands.get_portfolio", return_value=[]):
            lambda_handler(send("/portfolio"), None)
            resp = get_response(mock_telegram)
            assert "No positions" in resp


class TestE2E_Options:
    def test_options_analyzes_open(self, mock_telegram, mock_portfolio, mock_yf_ticker):
        lambda_handler(send("/options"), None)
        resp = get_response(mock_telegram)
        assert "AMD" in resp
        assert "call" in resp

    def test_options_no_positions(self, mock_telegram):
        with patch("bot.commands.get_portfolio", return_value=[]):
            lambda_handler(send("/options"), None)
            resp = get_response(mock_telegram)
            assert "No open options" in resp

    def test_put_command(self, mock_telegram, mock_portfolio, mock_yf_ticker):
        lambda_handler(send("/put"), None)
        resp = get_response(mock_telegram)
        # No puts in our portfolio, only calls
        assert "No open put" in resp


class TestE2E_Update:
    def test_buy_shares(self, mock_telegram, mock_portfolio):
        lambda_handler(send("/update bought 50 NVDA at 800"), None)
        resp = get_response(mock_telegram)
        assert "NVDA" in resp
        assert "New position" in resp or "Bought" in resp

    def test_sell_shares(self, mock_telegram, mock_portfolio):
        lambda_handler(send("/update sold 50 AMZN at 195"), None)
        resp = get_response(mock_telegram)
        assert "Sold" in resp
        assert "AMZN" in resp
        assert "P&L" in resp

    def test_sell_more_than_held(self, mock_telegram, mock_portfolio):
        lambda_handler(send("/update sold 500 AMZN at 195"), None)
        resp = get_response(mock_telegram)
        assert "Can't sell" in resp

    def test_update_unparseable(self, mock_telegram):
        lambda_handler(send("/update do something random"), None)
        resp = get_response(mock_telegram)
        assert "Couldn't parse" in resp

    def test_update_no_args(self, mock_telegram):
        lambda_handler(send("/update"), None)
        resp = get_response(mock_telegram)
        assert "Usage" in resp


class TestE2E_History:
    def test_trade_history(self, mock_telegram, mock_trade_history):
        lambda_handler(send("/history"), None)
        resp = get_response(mock_telegram)
        assert "sell" in resp
        assert "AMZN" in resp
        assert "buy" in resp
        assert "AMD" in resp

    def test_empty_history(self, mock_telegram):
        with patch("shared.db.get_trade_history", return_value=[]), \
             patch("bot.commands.get_trade_history", return_value=[]):
            lambda_handler(send("/history"), None)
            resp = get_response(mock_telegram)
            assert "No trade history" in resp


# ── RESEARCH COMMANDS ──────────────────────────────────────────────────────

class TestE2E_News:
    def test_news_single_ticker(self, mock_telegram, mock_news):
        lambda_handler(send("/news AMZN"), None)
        resp = get_response(mock_telegram)
        assert "AMZN" in resp
        assert "AI chip" in resp or "NEWS" in resp

    def test_news_all_tickers(self, mock_telegram, mock_portfolio, mock_news):
        lambda_handler(send("/news"), None)
        resp = get_response(mock_telegram)
        assert "NEWS" in resp or "AMZN" in resp

    def test_news_no_positions(self, mock_telegram, mock_news):
        with patch("bot.commands.get_portfolio", return_value=[]), \
             patch("bot.commands.get_all_tickers", return_value=[]):
            lambda_handler(send("/news"), None)
            resp = get_response(mock_telegram)
            assert "No positions" in resp or "TICKER" in resp


class TestE2E_Flow:
    def test_flow_single_ticker(self, mock_telegram, mock_yf_ticker):
        lambda_handler(send("/flow AMZN"), None)
        resp = get_response(mock_telegram)
        assert "AMZN" in resp
        assert "Put/Call" in resp

    def test_flow_detects_unusual(self, mock_telegram, mock_yf_ticker):
        """The mock chain has 12000 vol on $200 calls vs 1500 OI = 8x ratio → unusual."""
        lambda_handler(send("/flow AMZN"), None)
        resp = get_response(mock_telegram)
        assert "200" in resp or "Unusual" in resp or "bullish" in resp

    def test_flow_handles_nan(self, mock_telegram, mock_yf_ticker):
        """NaN values in the chain should NOT crash."""
        lambda_handler(send("/flow AMZN"), None)
        resp = get_response(mock_telegram)
        assert "Error" not in resp

    def test_flow_all_tickers(self, mock_telegram, mock_portfolio, mock_watchlist, mock_yf_ticker):
        lambda_handler(send("/flow"), None)
        resp = get_response(mock_telegram)
        # Should scan portfolio + watchlist tickers
        assert "FLOW" in resp or "unusual" in resp.lower() or "No unusual" in resp


class TestE2E_Technicals:
    def test_technicals_ticker(self, mock_telegram, mock_technicals):
        lambda_handler(send("/technicals AMD"), None)
        resp = get_response(mock_telegram)
        assert "AMD" in resp
        assert "RSI" in resp
        assert "MACD" in resp
        assert "SMA" in resp
        assert "Bollinger" in resp or "bb" in resp.lower() or "$" in resp

    def test_technicals_no_ticker(self, mock_telegram):
        lambda_handler(send("/technicals"), None)
        resp = get_response(mock_telegram)
        assert "Usage" in resp


class TestE2E_Darkpool:
    def test_darkpool_single_ticker(self, mock_telegram, mock_darkpool):
        lambda_handler(send("/darkpool AMD"), None)
        resp = get_response(mock_telegram)
        assert "AMD" in resp
        assert "45.0%" in resp
        assert "HIGH" in resp

    def test_darkpool_all_tickers(self, mock_telegram, mock_portfolio, mock_watchlist, mock_darkpool):
        lambda_handler(send("/darkpool"), None)
        resp = get_response(mock_telegram)
        assert "DARK POOL" in resp or "off-exchange" in resp


class TestE2E_Congress:
    def test_congress_single_ticker(self, mock_telegram, mock_congress_db):
        lambda_handler(send("/congress AMZN"), None)
        resp = get_response(mock_telegram)
        assert "CONGRESSIONAL" in resp or "Congress" in resp

    def test_congress_all(self, mock_telegram, mock_congress_db):
        lambda_handler(send("/congress"), None)
        resp = get_response(mock_telegram)
        assert "CONGRESSIONAL" in resp or "CLUSTER" in resp or "Pelosi" in resp


class TestE2E_Earnings:
    def test_earnings_single(self, mock_telegram, mock_yf_ticker):
        lambda_handler(send("/earnings AMZN"), None)
        resp = get_response(mock_telegram)
        assert "AMZN" in resp
        assert "EARNINGS" in resp

    def test_earnings_all(self, mock_telegram, mock_portfolio, mock_yf_ticker):
        lambda_handler(send("/earnings"), None)
        resp = get_response(mock_telegram)
        assert "EARNINGS" in resp


# ── INTELLIGENCE COMMANDS ──────────────────────────────────────────────────

class TestE2E_Movers:
    def test_movers(self, mock_telegram, mock_portfolio):
        with patch("tools.prices.yf.download") as mock_dl:
            # Return 2 days of data for movers calculation
            mock_dl.return_value = pd.DataFrame({"Close": [160.0, 170.0]})
            lambda_handler(send("/movers"), None)
            resp = get_response(mock_telegram)
            assert "MOVERS" in resp or "%" in resp


class TestE2E_Sector:
    def test_sector(self, mock_telegram, mock_congress_db):
        lambda_handler(send("/sector"), None)
        resp = get_response(mock_telegram)
        assert "SECTOR" in resp or "Congress" in resp.lower() or "%" in resp


class TestE2E_Scan:
    def test_scan_ticker(self, mock_telegram, mock_yf_ticker, mock_technicals,
                         mock_darkpool, mock_congress_db, mock_news):
        with patch("tools.prices.fetch_prices", return_value={"NVDA": 850.0}):
            lambda_handler(send("/scan NVDA"), None)
            resp = get_response(mock_telegram)
            assert "NVDA" in resp or "SCAN" in resp

    def test_scan_no_ticker(self, mock_telegram):
        lambda_handler(send("/scan"), None)
        resp = get_response(mock_telegram)
        assert "Usage" in resp


class TestE2E_Compare:
    def test_compare_two_tickers(self, mock_telegram, mock_technicals):
        lambda_handler(send("/compare AMD NVDA"), None)
        resp = get_response(mock_telegram)
        assert "COMPARE" in resp
        assert "AMD" in resp
        assert "NVDA" in resp
        assert "RSI" in resp
        assert "Price" in resp

    def test_compare_one_ticker(self, mock_telegram):
        lambda_handler(send("/compare AMD"), None)
        resp = get_response(mock_telegram)
        assert "Usage" in resp


# ── WATCHLIST & ALERTS ─────────────────────────────────────────────────────

class TestE2E_Watch:
    def test_watch_single(self, mock_telegram, mock_watchlist):
        lambda_handler(send("/watch NVDA"), None)
        resp = get_response(mock_telegram)
        assert "NVDA" in resp
        assert "Added" in resp or "watchlist" in resp.lower()

    def test_watch_multiple(self, mock_telegram, mock_watchlist):
        lambda_handler(send("/watch NVDA TSLA PLTR"), None)
        resp = get_response(mock_telegram)
        assert "NVDA" in resp
        assert "TSLA" in resp
        assert "PLTR" in resp

    def test_watch_no_args(self, mock_telegram):
        lambda_handler(send("/watch"), None)
        resp = get_response(mock_telegram)
        assert "Usage" in resp


class TestE2E_Unwatch:
    def test_unwatch(self, mock_telegram, mock_watchlist):
        lambda_handler(send("/unwatch TSLA"), None)
        resp = get_response(mock_telegram)
        assert "TSLA" in resp
        assert "Removed" in resp or "remove" in resp.lower()

    def test_unwatch_no_args(self, mock_telegram):
        lambda_handler(send("/unwatch"), None)
        resp = get_response(mock_telegram)
        assert "Usage" in resp


class TestE2E_Watchlist:
    def test_watchlist_with_tickers(self, mock_telegram, mock_watchlist):
        lambda_handler(send("/watchlist"), None)
        resp = get_response(mock_telegram)
        assert "NVDA" in resp
        assert "TSLA" in resp

    def test_watchlist_empty(self, mock_telegram):
        with patch("shared.db.get_watchlist", return_value=[]), \
             patch("bot.commands.get_watchlist", return_value=[]):
            lambda_handler(send("/watchlist"), None)
            resp = get_response(mock_telegram)
            assert "Empty" in resp


class TestE2E_Alerts:
    def test_alerts_show_config(self, mock_telegram, mock_alerts_db):
        lambda_handler(send("/alerts"), None)
        resp = get_response(mock_telegram)
        assert "ALERT CONFIG" in resp
        assert "ON" in resp

    def test_alerts_enable(self, mock_telegram, mock_alerts_db):
        lambda_handler(send("/alerts on"), None)
        resp = get_response(mock_telegram)
        assert "enabled" in resp

    def test_alerts_disable(self, mock_telegram, mock_alerts_db):
        lambda_handler(send("/alerts off"), None)
        resp = get_response(mock_telegram)
        assert "disabled" in resp

    def test_alerts_mute(self, mock_telegram, mock_alerts_db):
        lambda_handler(send("/alerts mute 2h"), None)
        resp = get_response(mock_telegram)
        assert "muted" in resp.lower() or "2 hours" in resp

    def test_alerts_toggle_type(self, mock_telegram, mock_alerts_db):
        lambda_handler(send("/alerts congress off"), None)
        resp = get_response(mock_telegram)
        assert "congress" in resp.lower()
        assert "OFF" in resp

    def test_alerts_invalid(self, mock_telegram, mock_alerts_db):
        lambda_handler(send("/alerts foobar"), None)
        resp = get_response(mock_telegram)
        assert "Usage" in resp or "on" in resp


class TestE2E_Threshold:
    def test_set_above(self, mock_telegram, mock_alerts_db):
        lambda_handler(send("/threshold AMZN above 200"), None)
        resp = get_response(mock_telegram)
        assert "AMZN" in resp
        assert "above" in resp
        assert "$200" in resp

    def test_set_below(self, mock_telegram, mock_alerts_db):
        lambda_handler(send("/threshold AMD below 155"), None)
        resp = get_response(mock_telegram)
        assert "AMD" in resp
        assert "below" in resp

    def test_clear(self, mock_telegram, mock_alerts_db):
        lambda_handler(send("/threshold clear AMZN"), None)
        resp = get_response(mock_telegram)
        assert "Cleared" in resp

    def test_no_args(self, mock_telegram):
        lambda_handler(send("/threshold"), None)
        resp = get_response(mock_telegram)
        assert "Usage" in resp

    def test_invalid_direction(self, mock_telegram, mock_alerts_db):
        lambda_handler(send("/threshold AMZN sideways 200"), None)
        resp = get_response(mock_telegram)
        assert "above" in resp or "below" in resp

    def test_invalid_price(self, mock_telegram, mock_alerts_db):
        lambda_handler(send("/threshold AMZN above abc"), None)
        resp = get_response(mock_telegram)
        assert "Invalid" in resp


# ── AI COMMANDS ────────────────────────────────────────────────────────────

class TestE2E_AiCommands:
    """AI commands gather data with code then call Claude. We mock Claude."""

    @patch("bot.ai_commands._ask_claude", return_value="Buy AMD, sell AMZN, hold SPY.")
    def test_brief(self, mock_claude, mock_telegram, mock_portfolio, mock_prices,
                   mock_yf_ticker, mock_news, mock_congress_db, mock_darkpool, mock_technicals,
                   mock_watchlist):
        lambda_handler(send("/brief"), None)
        responses = get_all_responses(mock_telegram)
        full_resp = " ".join(responses)
        assert "MORNING BRIEF" in full_resp or "PORTFOLIO" in full_resp
        # Claude was called for recommendations
        mock_claude.assert_called()

    @patch("bot.ai_commands._ask_claude", return_value="AMD is oversold, consider buying at $155 support.")
    def test_catalyst(self, mock_claude, mock_telegram, mock_yf_ticker, mock_news,
                      mock_congress_db, mock_darkpool, mock_technicals):
        lambda_handler(send("/catalyst AMD"), None)
        resp = get_response(mock_telegram)
        assert "CATALYSTS" in resp or "AMD" in resp
        mock_claude.assert_called()

    def test_catalyst_no_ticker(self, mock_telegram):
        lambda_handler(send("/catalyst"), None)
        resp = get_response(mock_telegram)
        assert "Usage" in resp

    @patch("bot.ai_commands._ask_claude", return_value="Biggest risk is AMD concentration at 38%.")
    def test_risk(self, mock_claude, mock_telegram, mock_portfolio, mock_prices,
                  mock_yf_ticker, mock_darkpool, mock_technicals):
        lambda_handler(send("/risk"), None)
        resp = get_response(mock_telegram)
        assert "RISK" in resp
        mock_claude.assert_called()

    @patch("bot.ai_commands._ask_claude", return_value="AMZN thesis: bearish short-term, neutral long-term.")
    def test_analyze(self, mock_claude, mock_telegram, mock_yf_ticker, mock_news,
                     mock_congress_db, mock_darkpool, mock_technicals):
        lambda_handler(send("/analyze AMZN"), None)
        resp = get_response(mock_telegram)
        assert "ANALYSIS" in resp or "AMZN" in resp
        mock_claude.assert_called()

    def test_analyze_no_ticker(self, mock_telegram):
        lambda_handler(send("/analyze"), None)
        resp = get_response(mock_telegram)
        assert "Usage" in resp

    @patch("bot.ai_commands._ask_claude", return_value="Yes, roll the call out 30 days for more premium.")
    def test_ask_freeform(self, mock_claude, mock_telegram, mock_portfolio):
        lambda_handler(send("/ask Should I roll my AMD call?"), None)
        resp = get_response(mock_telegram)
        assert "roll" in resp
        mock_claude.assert_called()

    def test_ask_no_question(self, mock_telegram):
        lambda_handler(send("/ask"), None)
        resp = get_response(mock_telegram)
        assert "Usage" in resp


# ── EDGE CASES & ERROR HANDLING ────────────────────────────────────────────

class TestE2E_EdgeCases:
    def test_unknown_command(self, mock_telegram):
        lambda_handler(send("/foobar"), None)
        resp = get_response(mock_telegram)
        assert "Unknown command" in resp
        assert "/help" in resp

    def test_freeform_goes_to_ai(self, mock_telegram, mock_portfolio):
        with patch("bot.ai_commands._ask_claude", return_value="The market is volatile."):
            lambda_handler(send("What is happening with the market?"), None)
            resp = get_response(mock_telegram)
            assert "volatile" in resp or "market" in resp

    def test_case_insensitive_commands(self, mock_telegram):
        lambda_handler(send("/HELP"), None)
        resp = get_response(mock_telegram)
        assert "PORTFOLIO" in resp

    def test_command_with_extra_whitespace(self, mock_telegram, mock_watchlist):
        lambda_handler(send("/watch   NVDA  "), None)
        resp = get_response(mock_telegram)
        assert "NVDA" in resp

    def test_callback_button_press(self, mock_telegram):
        event = {
            "body": json.dumps({
                "callback_query": {
                    "id": "test123",
                    "message": {"chat": {"id": int(CHAT_ID)}},
                    "data": "/help flow",
                }
            })
        }
        lambda_handler(event, None)
        endpoints = [m["endpoint"] for m in mock_telegram]
        assert "answerCallbackQuery" in endpoints
        assert "sendMessage" in endpoints
        resp = get_response(mock_telegram)
        assert "Unusual Options Activity" in resp

    def test_handler_never_crashes(self, mock_telegram):
        """Handler should return 200 even with garbage input."""
        for payload in [
            {},
            {"body": ""},
            {"body": "null"},
            {"body": "[]"},
            {"body": '{"update_id": 123}'},
        ]:
            result = lambda_handler(payload, None)
            assert result["statusCode"] == 200
