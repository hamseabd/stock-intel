"""DynamoDB helpers for all tables."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

from shared.config import (
    AWS_REGION,
    DYNAMODB_TABLE_PORTFOLIO,
    DYNAMODB_TABLE_WATCHLIST,
    DYNAMODB_TABLE_ALERTS,
    DYNAMODB_TABLE_CONGRESS,
    DYNAMODB_TABLE_TRADES,
)

_dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)


def _table(name: str):
    return _dynamodb.Table(name)


def _to_decimal(obj: Any) -> Any:
    """Convert floats to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_decimal(i) for i in obj]
    return obj


def _from_decimal(obj: Any) -> Any:
    """Convert Decimals back to float from DynamoDB."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _from_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_from_decimal(i) for i in obj]
    return obj


# ── Portfolio ──────────────────────────────────────────────────────────────

def get_positions(chat_id: str) -> list[dict]:
    table = _table(DYNAMODB_TABLE_PORTFOLIO)
    resp = table.query(KeyConditionExpression=Key("chat_id").eq(chat_id))
    return [_from_decimal(i) for i in resp.get("Items", [])]


def put_position(chat_id: str, position: dict) -> None:
    table = _table(DYNAMODB_TABLE_PORTFOLIO)
    item = {
        "chat_id": chat_id,
        "position_id": _position_id(position),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **position,
    }
    table.put_item(Item=_to_decimal(item))


def delete_position(chat_id: str, position: dict) -> None:
    table = _table(DYNAMODB_TABLE_PORTFOLIO)
    table.delete_item(Key={"chat_id": chat_id, "position_id": _position_id(position)})


def _position_id(pos: dict) -> str:
    if pos.get("position_type") == "option":
        return f"opt#{pos['ticker']}#{pos['strike']}#{pos['expiry']}"
    return f"share#{pos['ticker']}"


# ── Watchlist ──────────────────────────────────────────────────────────────

def get_watchlist(chat_id: str) -> list[str]:
    table = _table(DYNAMODB_TABLE_WATCHLIST)
    resp = table.query(KeyConditionExpression=Key("chat_id").eq(chat_id))
    return [item["ticker"] for item in resp.get("Items", [])]


def add_to_watchlist(chat_id: str, ticker: str) -> None:
    table = _table(DYNAMODB_TABLE_WATCHLIST)
    table.put_item(Item={
        "chat_id": chat_id,
        "ticker": ticker.upper(),
        "added_at": datetime.now(timezone.utc).isoformat(),
    })


def remove_from_watchlist(chat_id: str, ticker: str) -> None:
    table = _table(DYNAMODB_TABLE_WATCHLIST)
    table.delete_item(Key={"chat_id": chat_id, "ticker": ticker.upper()})


# ── Alerts Config ──────────────────────────────────────────────────────────

def get_alert_config(chat_id: str) -> dict:
    table = _table(DYNAMODB_TABLE_ALERTS)
    resp = table.get_item(Key={"chat_id": chat_id, "sk": "config"})
    item = resp.get("Item")
    if not item:
        return {"chat_id": chat_id, "enabled": True}
    return _from_decimal(item)


def put_alert_config(chat_id: str, config: dict) -> None:
    table = _table(DYNAMODB_TABLE_ALERTS)
    item = {"chat_id": chat_id, "sk": "config", **config}
    table.put_item(Item=_to_decimal(item))


def get_price_alerts(chat_id: str) -> list[dict]:
    table = _table(DYNAMODB_TABLE_ALERTS)
    resp = table.query(
        KeyConditionExpression=Key("chat_id").eq(chat_id) & Key("sk").begins_with("price#"),
    )
    return [_from_decimal(i) for i in resp.get("Items", [])]


def put_price_alert(chat_id: str, ticker: str, direction: str, price: float) -> None:
    table = _table(DYNAMODB_TABLE_ALERTS)
    table.put_item(Item=_to_decimal({
        "chat_id": chat_id,
        "sk": f"price#{ticker}#{direction}",
        "ticker": ticker.upper(),
        "direction": direction,
        "target_price": price,
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }))


def delete_price_alerts(chat_id: str, ticker: str) -> None:
    table = _table(DYNAMODB_TABLE_ALERTS)
    resp = table.query(
        KeyConditionExpression=Key("chat_id").eq(chat_id) & Key("sk").begins_with(f"price#{ticker}"),
    )
    for item in resp.get("Items", []):
        table.delete_item(Key={"chat_id": chat_id, "sk": item["sk"]})


# ── Congress Trades ────────────────────────────────────────────────────────

def put_congress_trade(trade: dict) -> None:
    table = _table(DYNAMODB_TABLE_CONGRESS)
    item = {
        "pk": f"{trade['member']}#{trade['trade_date']}",
        "sk": f"{trade['ticker']}#{trade['filing_date']}",
        **trade,
    }
    table.put_item(Item=_to_decimal(item))


def query_congress_by_ticker(ticker: str, limit: int = 50) -> list[dict]:
    table = _table(DYNAMODB_TABLE_CONGRESS)
    resp = table.query(
        IndexName="ticker-trade_date-index",
        KeyConditionExpression=Key("ticker").eq(ticker.upper()),
        ScanIndexForward=False,
        Limit=limit,
    )
    return [_from_decimal(i) for i in resp.get("Items", [])]


def query_congress_recent(days: int = 30, limit: int = 200) -> list[dict]:
    table = _table(DYNAMODB_TABLE_CONGRESS)
    cutoff = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Scan with filter — acceptable for low-volume congress data (~200 trades/month)
    resp = table.scan(Limit=limit)
    items = [_from_decimal(i) for i in resp.get("Items", [])]
    # Sort by filing date descending
    items.sort(key=lambda x: x.get("filing_date", ""), reverse=True)
    return items[:limit]


# ── Trade Log ──────────────────────────────────────────────────────────────

def log_trade(chat_id: str, trade: dict) -> None:
    table = _table(DYNAMODB_TABLE_TRADES)
    item = {
        "chat_id": chat_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **trade,
    }
    table.put_item(Item=_to_decimal(item))


def get_trade_history(chat_id: str, limit: int = 20) -> list[dict]:
    table = _table(DYNAMODB_TABLE_TRADES)
    resp = table.query(
        KeyConditionExpression=Key("chat_id").eq(chat_id),
        ScanIndexForward=False,
        Limit=limit,
    )
    return [_from_decimal(i) for i in resp.get("Items", [])]
