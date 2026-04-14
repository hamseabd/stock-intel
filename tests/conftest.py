"""Test fixtures and mocks for the entire test suite."""

import sys
import os
import json
import math
from unittest.mock import MagicMock, patch
from decimal import Decimal

import pytest
import numpy as np

# Add src to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Set test environment variables before any imports
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("DYNAMODB_TABLE_PORTFOLIO", "test-portfolio")
os.environ.setdefault("DYNAMODB_TABLE_WATCHLIST", "test-watchlist")
os.environ.setdefault("DYNAMODB_TABLE_ALERTS", "test-alerts")
os.environ.setdefault("DYNAMODB_TABLE_CONGRESS", "test-congress")
os.environ.setdefault("DYNAMODB_TABLE_TRADES", "test-trades")
os.environ.setdefault("S3_BUCKET_DATA", "test-data")
os.environ.setdefault("S3_BUCKET_DASHBOARD", "test-dashboard")
os.environ.setdefault("SQS_ALERT_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/test-alerts")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "123456789")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")


# ── Sample Data ────────────────────────────────────────────────────────────

@pytest.fixture
def sample_share_positions():
    return [
        {"position_type": "shares", "ticker": "AMZN", "shares": 100, "cost_basis": 250.0},
        {"position_type": "shares", "ticker": "AMD", "shares": 200, "cost_basis": 222.5},
        {"position_type": "shares", "ticker": "SPY", "shares": 18, "cost_basis": 445.0},
        {"position_type": "shares", "ticker": "QQQ", "shares": 20, "cost_basis": 385.0},
    ]


@pytest.fixture
def sample_option_positions():
    return [
        {
            "position_type": "option", "ticker": "AMD", "option_type": "call",
            "strategy": "covered_call", "strike": 250.0, "expiry": "2026-05-15",
            "contracts": 2, "cost_basis": 15.23, "status": "open",
        },
        {
            "position_type": "option", "ticker": "AMZN", "option_type": "put",
            "strategy": "cash_secured_put", "strike": 180.0, "expiry": "2026-04-25",
            "contracts": 1, "cost_basis": 3.50, "status": "open",
        },
    ]


@pytest.fixture
def sample_all_positions(sample_share_positions, sample_option_positions):
    return sample_share_positions + sample_option_positions


@pytest.fixture
def sample_prices():
    return {
        "AMZN": 198.50,
        "AMD": 165.30,
        "SPY": 502.10,
        "QQQ": 421.50,
    }


@pytest.fixture
def sample_congress_trades():
    return [
        {
            "member": "Nancy Pelosi", "party": "D", "chamber": "House",
            "state": "CA", "ticker": "NVDA", "tx_type": "Purchase",
            "amount": "$1,000,001 - $5,000,000", "trade_date": "2026-04-01",
            "filing_date": "2026-04-08", "committees": ["Financial Services"],
            "owner": "Spouse", "signals": ["whale_trade"],
        },
        {
            "member": "Tommy Tuberville", "party": "R", "chamber": "Senate",
            "state": "AL", "ticker": "NVDA", "tx_type": "Purchase",
            "amount": "$250,001 - $500,000", "trade_date": "2026-04-03",
            "filing_date": "2026-04-09", "committees": ["Armed Services"],
            "owner": "Self", "signals": [],
        },
        {
            "member": "Jon Ossoff", "party": "D", "chamber": "Senate",
            "state": "GA", "ticker": "MSFT", "tx_type": "Purchase",
            "amount": "$50,001 - $100,000", "trade_date": "2026-04-05",
            "filing_date": "2026-04-10", "committees": [],
            "owner": "Self", "signals": [],
        },
        {
            "member": "Dan Crenshaw", "party": "R", "chamber": "House",
            "state": "TX", "ticker": "NVDA", "tx_type": "Purchase",
            "amount": "$100,001 - $250,000", "trade_date": "2026-04-06",
            "filing_date": "2026-04-10", "committees": ["Intelligence"],
            "owner": "Self", "signals": ["intelligence_committee"],
        },
    ]


@pytest.fixture
def sample_price_history():
    """6 months of fake closing prices trending up with noise."""
    np.random.seed(42)
    n = 130  # ~6 months of trading days
    base = 200.0
    returns = np.random.normal(0.001, 0.02, n)
    prices = base * np.cumprod(1 + returns)
    return prices


@pytest.fixture
def sample_headlines():
    return [
        {"title": "Amazon announces new AI chip", "summary": "AWS expands custom silicon.", "published": "2026-04-10T08:00:00", "link": "https://example.com/1"},
        {"title": "AMZN beats Q1 estimates", "summary": "Revenue up 12%.", "published": "2026-04-09T16:00:00", "link": "https://example.com/2"},
        {"title": "Amazon Web Services growth slows", "summary": "Cloud revenue misses.", "published": "2026-04-08T12:00:00", "link": "https://example.com/3"},
    ]


@pytest.fixture
def sample_darkpool_data():
    return [
        {"ticker": "AMD", "date": "2026-04-10", "dark_volume": 45000000, "total_volume": 100000000, "dark_pct": 45.0, "short_volume": 52000000, "short_pct": 52.0},
        {"ticker": "AMD", "date": "2026-04-09", "dark_volume": 42000000, "total_volume": 95000000, "dark_pct": 44.2, "short_volume": 48000000, "short_pct": 50.5},
        {"ticker": "AMD", "date": "2026-04-08", "dark_volume": 38000000, "total_volume": 105000000, "dark_pct": 36.2, "short_volume": 45000000, "short_pct": 42.9},
        {"ticker": "AMD", "date": "2026-04-07", "dark_volume": 35000000, "total_volume": 98000000, "dark_pct": 35.7, "short_volume": 40000000, "short_pct": 40.8},
    ]


# ── Mock helpers ───────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Mock all DynamoDB calls."""
    with patch("shared.db._dynamodb") as mock:
        yield mock


@pytest.fixture
def mock_telegram():
    """Mock Telegram API calls."""
    with patch("bot.telegram_client.requests.post") as mock_post:
        mock_post.return_value = MagicMock(json=lambda: {"ok": True, "result": {}})
        yield mock_post
