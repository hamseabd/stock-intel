"""Environment configuration for all Lambda functions."""

import os

# AWS
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
DYNAMODB_TABLE_PORTFOLIO = os.environ.get("DYNAMODB_TABLE_PORTFOLIO", "stock_portfolio")
DYNAMODB_TABLE_WATCHLIST = os.environ.get("DYNAMODB_TABLE_WATCHLIST", "stock_watchlist")
DYNAMODB_TABLE_ALERTS = os.environ.get("DYNAMODB_TABLE_ALERTS", "stock_alerts")
DYNAMODB_TABLE_CONGRESS = os.environ.get("DYNAMODB_TABLE_CONGRESS", "stock_congress_trades")
DYNAMODB_TABLE_TRADES = os.environ.get("DYNAMODB_TABLE_TRADES", "stock_trades")
S3_BUCKET_DATA = os.environ.get("S3_BUCKET_DATA", "stock-intel-data")
S3_BUCKET_DASHBOARD = os.environ.get("S3_BUCKET_DASHBOARD", "stock-intel-dashboard")
SQS_ALERT_QUEUE_URL = os.environ.get("SQS_ALERT_QUEUE_URL", "")

# Telegram
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Claude API
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL_SMART = "claude-sonnet-4-6"
CLAUDE_MODEL_FAST = "claude-haiku-4-5-20251001"

# Market hours (ET)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MIN = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MIN = 0

# Thresholds
UNUSUAL_FLOW_VOLUME_RATIO = 5.0  # volume / OI
LARGE_FLOW_PREMIUM = 500_000  # $500K single-strike
DARKPOOL_HIGH_PCT = 40.0  # >40% off-exchange
SHORT_VOLUME_HIGH_PCT = 50.0  # >50% short
DRAWDOWN_ALERT_PCT = -10.0  # flag positions down >10%
OPTIONS_EXPIRY_WARN_DAYS = 14
EARNINGS_WARN_DAYS = 30
CONGRESS_CLUSTER_MIN_MEMBERS = 2
CONGRESS_CLUSTER_WINDOW_DAYS = 14
CONGRESS_MIN_AMOUNT = "$50,001"
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
