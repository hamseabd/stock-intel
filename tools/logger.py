import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path(__file__).parent.parent / "data"
SNAPSHOTS_FILE = DATA_DIR / "snapshots.jsonl"
TRADES_FILE = DATA_DIR / "trades.jsonl"


def _append_jsonl(path: Path, record: dict) -> None:
    """Append a single JSON record as a line to a JSONL file."""
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def log_snapshot(pnl_data: dict) -> None:
    """
    Log a portfolio P&L snapshot to snapshots.jsonl.
    Called internally by get_prices() on every invocation.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "snapshot": pnl_data,
    }
    _append_jsonl(SNAPSHOTS_FILE, record)


def log_trade(
    action: str,
    ticker: str,
    shares: Optional[float],
    price: Optional[float],
    realized_pnl: Optional[float] = None,
    option_type: Optional[str] = None,
    strike: Optional[float] = None,
    expiry: Optional[str] = None,
) -> None:
    """
    Log a trade event to trades.jsonl.
    Called internally by update_portfolio() on every trade.
    """
    record: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "ticker": ticker,
    }
    if shares is not None:
        record["shares"] = shares
    if price is not None:
        record["price"] = price
    if realized_pnl is not None:
        record["realized_pnl"] = realized_pnl
    if option_type is not None:
        record["option_type"] = option_type
    if strike is not None:
        record["strike"] = strike
    if expiry is not None:
        record["expiry"] = expiry

    _append_jsonl(TRADES_FILE, record)
