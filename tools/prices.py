import json
from pathlib import Path
from typing import Any
import yfinance as yf
from strands import tool
from tools.logger import log_snapshot

PORTFOLIO_PATH = Path(__file__).parent.parent / "data" / "portfolio.json"


@tool
def get_prices() -> str:
    """
    Fetches live prices for all positions in the portfolio and calculates P&L.
    Use this tool when the user asks about P&L, performance, current value, or portfolio summary.
    Returns a JSON string with per-position P&L data and portfolio totals.
    """
    data = json.loads(PORTFOLIO_PATH.read_text())
    positions = data["positions"]

    # Collect unique tickers
    tickers = list({p["ticker"] for p in positions})

    # Batch download latest prices
    raw = yf.download(tickers, period="1d", progress=False, auto_adjust=True)

    prices: dict[str, float] = {}
    if len(tickers) == 1:
        ticker = tickers[0]
        try:
            close = raw["Close"].iloc[-1]
            prices[ticker] = float(close)
        except Exception:
            prices[ticker] = None
    else:
        for ticker in tickers:
            try:
                close = raw["Close"][ticker].dropna().iloc[-1]
                prices[ticker] = float(close)
            except Exception:
                prices[ticker] = None

    results: list[dict[str, Any]] = []
    total_cost = 0.0
    total_value = 0.0

    for pos in positions:
        ticker = pos["ticker"]
        current_price = prices.get(ticker)

        if pos["position_type"] == "shares":
            shares = pos["shares"]
            cost_basis = pos["cost_basis"]
            cost = shares * cost_basis

            if current_price is not None:
                value = shares * current_price
                dollar_pnl = value - cost
                pct_pnl = (dollar_pnl / cost * 100) if cost != 0 else 0.0
                total_cost += cost
                total_value += value
            else:
                value = dollar_pnl = pct_pnl = None

            results.append({
                "position_type": "shares",
                "ticker": ticker,
                "shares": shares,
                "cost_basis": round(cost_basis, 2),
                "current_price": round(current_price, 2) if current_price else None,
                "market_value": round(value, 2) if value is not None else None,
                "dollar_pnl": round(dollar_pnl, 2) if dollar_pnl is not None else None,
                "pct_pnl": round(pct_pnl, 2) if pct_pnl is not None else None,
            })

        elif pos["position_type"] == "option":
            # Options P&L is tracked separately via get_options_analysis
            # Show option position info with current underlying price
            results.append({
                "position_type": "option",
                "ticker": ticker,
                "option_type": pos.get("option_type"),
                "strategy": pos.get("strategy"),
                "strike": pos.get("strike"),
                "expiry": pos.get("expiry"),
                "contracts": pos.get("contracts", 1),
                "cost_basis": pos.get("cost_basis", 0.0),
                "underlying_price": round(current_price, 2) if current_price else None,
                "status": pos.get("status", "open"),
                "note": "Use get_options_analysis for full Greeks and option P&L.",
            })

    total_dollar_pnl = total_value - total_cost
    total_pct_pnl = (total_dollar_pnl / total_cost * 100) if total_cost != 0 else 0.0

    output = {
        "positions": results,
        "portfolio_totals": {
            "total_cost_basis": round(total_cost, 2),
            "total_market_value": round(total_value, 2),
            "total_dollar_pnl": round(total_dollar_pnl, 2),
            "total_pct_pnl": round(total_pct_pnl, 2),
        },
    }

    # Log snapshot for performance history
    log_snapshot(output)

    return json.dumps(output, indent=2)
