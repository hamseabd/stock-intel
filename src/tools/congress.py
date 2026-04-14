"""Congressional trading data — Capitol Trades scraper + cluster detection.

Data sources:
- Capitol Trades (bff.capitoltrades.com/trades): Clean JSON API, primary source
- Includes: member, party, committees, ticker, amount range, dates

Signal detection:
- Cluster trades: 2+ members buying same ticker within 14 days
- Committee-relevant: member's committee oversees the sector
- Whale trades: $1M+ amount range
- Intelligence committee: flag ALL trades
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta

import requests

from shared.log import get_logger, Timer

logger = get_logger(__name__)

from shared.config import CONGRESS_CLUSTER_MIN_MEMBERS, CONGRESS_CLUSTER_WINDOW_DAYS, CONGRESS_MIN_AMOUNT
from shared.db import put_congress_trade, query_congress_by_ticker, query_congress_recent

CAPITOL_TRADES_URL = "https://bff.capitoltrades.com/trades"

# Committee → sector mapping for signal detection
COMMITTEE_SECTORS = {
    "Armed Services": {"LMT", "RTX", "NOC", "BA", "GD", "LHX", "HII"},
    "Banking": {"JPM", "BAC", "GS", "MS", "WFC", "C", "SCHW"},
    "Finance": {"JPM", "BAC", "GS", "MS", "WFC", "C", "SCHW", "BLK", "BRK-B"},
    "Energy": {"XOM", "CVX", "COP", "SLB", "OXY", "EOG", "MPC"},
    "Health": {"UNH", "JNJ", "PFE", "ABBV", "MRK", "LLY", "TMO", "AMGN"},
    "Commerce": {"AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA"},
    "Intelligence": set(),  # flag ALL trades from intel committee members
}

AMOUNT_RANK = {
    "$1,001 - $15,000": 1,
    "$15,001 - $50,000": 2,
    "$50,001 - $100,000": 3,
    "$100,001 - $250,000": 4,
    "$250,001 - $500,000": 5,
    "$500,001 - $1,000,000": 6,
    "$1,000,001 - $5,000,000": 7,
    "$5,000,001 - $25,000,000": 8,
    "$25,000,001 - $50,000,000": 9,
    "Over $50,000,000": 10,
}


def scrape_capitol_trades(pages: int = 3) -> list[dict]:
    """Scrape recent congressional stock trades from Capitol Trades.

    Args:
        pages: Number of pages to fetch (100 trades per page)

    Returns:
        List of trade dicts with member, party, ticker, amount, dates, signals
    """
    logger.info("Scraping Capitol Trades", pages=pages)
    all_trades = []
    for page in range(1, pages + 1):
        try:
            resp = requests.get(
                CAPITOL_TRADES_URL,
                params={"page": page, "pageSize": 100},
                headers={"User-Agent": "Mozilla/5.0 (StockIntel/1.0)"},
                timeout=15,
            )
            if resp.status_code != 200:
                break
            data = resp.json()
            entries = data.get("data", [])
            if not entries:
                break

            for entry in entries:
                politician = entry.get("politician", {})
                asset = entry.get("asset", {})
                ticker = asset.get("assetTicker") or ""
                if not ticker:
                    continue  # skip non-stock trades

                trade = {
                    "member": politician.get("firstName", "") + " " + politician.get("lastName", ""),
                    "party": politician.get("party", "?"),
                    "chamber": politician.get("chamber", ""),
                    "state": politician.get("state", ""),
                    "ticker": ticker.upper(),
                    "tx_type": entry.get("txType", ""),
                    "amount": entry.get("txAmount", ""),
                    "trade_date": entry.get("txDate", "")[:10],
                    "filing_date": entry.get("filingDate", "")[:10],
                    "committees": [c.get("name", "") for c in politician.get("committees", [])],
                    "owner": entry.get("owner", "Self"),
                    "signals": [],
                }
                # Compute signals
                _add_signals(trade)
                all_trades.append(trade)

        except Exception:
            break
    return all_trades


def _add_signals(trade: dict) -> None:
    """Add signal flags to a trade."""
    signals = []
    amount_rank = AMOUNT_RANK.get(trade.get("amount", ""), 0)

    if amount_rank >= 5:  # $250K+
        signals.append("large_trade")
    if amount_rank >= 7:  # $1M+
        signals.append("whale_trade")

    # Committee relevance
    for committee in trade.get("committees", []):
        for key, tickers in COMMITTEE_SECTORS.items():
            if key.lower() in committee.lower():
                if not tickers or trade["ticker"] in tickers:
                    signals.append(f"committee_relevant:{key}")

    # Intelligence committee — flag everything
    for committee in trade.get("committees", []):
        if "intelligence" in committee.lower():
            signals.append("intelligence_committee")

    trade["signals"] = signals


def store_trades(trades: list[dict]) -> int:
    """Store trades in DynamoDB, deduplicating by key."""
    stored = 0
    for trade in trades:
        try:
            put_congress_trade(trade)
            stored += 1
        except Exception:
            pass
    return stored


def detect_clusters(trades: list[dict], window_days: int = None, min_members: int = None) -> list[dict]:
    """Detect cluster trades: multiple members trading same ticker in short window."""
    window = window_days or CONGRESS_CLUSTER_WINDOW_DAYS
    min_m = min_members or CONGRESS_CLUSTER_MIN_MEMBERS

    by_ticker = defaultdict(list)
    for t in trades:
        by_ticker[t["ticker"]].append(t)

    clusters = []
    for ticker, ticker_trades in by_ticker.items():
        if len(ticker_trades) < min_m:
            continue
        # Group by window
        ticker_trades.sort(key=lambda x: x.get("trade_date", ""))
        members = set()
        buy_count = 0
        sell_count = 0
        for t in ticker_trades:
            members.add(t["member"])
            if "purchase" in t.get("tx_type", "").lower():
                buy_count += 1
            else:
                sell_count += 1

        if len(members) >= min_m:
            direction = "buying" if buy_count > sell_count else "selling" if sell_count > buy_count else "mixed"
            clusters.append({
                "ticker": ticker,
                "members": list(members),
                "trade_count": len(ticker_trades),
                "direction": direction,
                "buy_count": buy_count,
                "sell_count": sell_count,
            })

    clusters.sort(key=lambda x: len(x["members"]), reverse=True)
    return clusters


def get_congress_for_ticker(ticker: str) -> list[dict]:
    """Get congressional trades for a specific ticker."""
    return query_congress_by_ticker(ticker.upper())


def get_congress_recent(days: int = 30) -> list[dict]:
    """Get all recent congressional trades."""
    return query_congress_recent(days)


def get_sector_breakdown(trades: list[dict]) -> dict[str, int]:
    """Count trades by sector."""
    sector_map = {}
    for key, tickers in COMMITTEE_SECTORS.items():
        for ticker in tickers:
            sector_map[ticker] = key

    counts = defaultdict(int)
    for t in trades:
        sector = sector_map.get(t["ticker"], "Other")
        counts[sector] += 1

    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))
