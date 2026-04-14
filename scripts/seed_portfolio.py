"""Seed DynamoDB portfolio table with your current positions.

Run this once after first deploy:
  python scripts/seed_portfolio.py
"""

import os
import sys
import boto3
from decimal import Decimal

# Your current portfolio from data/portfolio.json
POSITIONS = [
    {"position_type": "shares", "ticker": "AMZN", "shares": 100, "cost_basis": 250.0},
    {"position_type": "shares", "ticker": "AMD", "shares": 200, "cost_basis": 222.5},
    {"position_type": "shares", "ticker": "SPY", "shares": 18, "cost_basis": 445.0},
    {"position_type": "shares", "ticker": "QQQ", "shares": 20, "cost_basis": 385.0},
    {
        "position_type": "option", "ticker": "AMD", "option_type": "call",
        "strategy": "covered_call", "strike": 250.0, "expiry": "2026-05-15",
        "contracts": 2, "cost_basis": 15.23, "status": "open",
    },
]

CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TABLE_NAME = os.environ.get("DYNAMODB_TABLE_PORTFOLIO", "stock-intel-portfolio")
REGION = os.environ.get("AWS_REGION", "us-east-1")


def position_id(pos):
    if pos.get("position_type") == "option":
        return f"opt#{pos['ticker']}#{pos['strike']}#{pos['expiry']}"
    return f"share#{pos['ticker']}"


def to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_decimal(i) for i in obj]
    return obj


def main():
    if not CHAT_ID:
        print("Set TELEGRAM_CHAT_ID environment variable first.")
        sys.exit(1)

    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(TABLE_NAME)

    print(f"Seeding {len(POSITIONS)} positions to {TABLE_NAME} for chat_id={CHAT_ID}")
    for pos in POSITIONS:
        item = to_decimal({
            "chat_id": CHAT_ID,
            "position_id": position_id(pos),
            **pos,
        })
        table.put_item(Item=item)
        print(f"  Added: {pos['ticker']} ({pos['position_type']})")

    print("Done!")


if __name__ == "__main__":
    main()
