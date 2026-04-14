"""Live price fetching and P&L calculation.

Uses yfinance for real-time and historical price data. All P&L math
is delegated to shared.math_utils for testability.
"""

import yfinance as yf
from shared.math_utils import calc_pnl
from shared.log import get_logger, Timer

logger = get_logger(__name__)


def fetch_prices(tickers: list[str]) -> dict[str, float | None]:
    """Batch fetch current prices for a list of tickers via yfinance.

    Args:
        tickers: List of stock ticker symbols

    Returns:
        Dict mapping ticker → current price (or None if unavailable)
    """
    if not tickers:
        return {}
    logger.info("Fetching prices", tickers=tickers)
    raw = yf.download(tickers, period="1d", progress=False, auto_adjust=True)
    # yfinance may return MultiIndex columns — flatten for single tickers
    if hasattr(raw.columns, "droplevel") and raw.columns.nlevels > 1:
        if len(tickers) == 1:
            raw.columns = raw.columns.droplevel(1)

    prices = {}
    if len(tickers) == 1:
        try:
            prices[tickers[0]] = float(raw["Close"].iloc[-1])
        except Exception:
            prices[tickers[0]] = None
    else:
        for ticker in tickers:
            try:
                prices[ticker] = float(raw["Close"][ticker].dropna().iloc[-1])
            except Exception:
                prices[ticker] = None
    return prices


def fetch_price_history(ticker: str, period: str = "6mo") -> dict:
    """Fetch OHLCV history for a single ticker.

    Args:
        ticker: Stock symbol
        period: yfinance period string (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

    Returns:
        Dict with closes, volumes, highs, lows as flat lists
    """
    logger.info("Fetching price history", ticker=ticker, period=period)
    hist = yf.download(ticker, period=period, progress=False, auto_adjust=True)
    if hist.empty:
        logger.warning("Empty price history", ticker=ticker)
        return {"closes": [], "volumes": [], "highs": [], "lows": []}

    # yfinance may return MultiIndex columns like ("Close", "AMZN") for single tickers.
    # Flatten to simple column names.
    if hasattr(hist.columns, "droplevel") and hist.columns.nlevels > 1:
        hist.columns = hist.columns.droplevel(1)

    # Drop rows with no Close price
    if "Close" in hist.columns:
        hist = hist.dropna(subset=["Close"])

    return {
        "closes": hist["Close"].values.flatten().tolist(),
        "volumes": hist["Volume"].fillna(0).values.flatten().tolist(),
        "highs": hist["High"].values.flatten().tolist(),
        "lows": hist["Low"].values.flatten().tolist(),
    }


def calculate_portfolio_pnl(positions: list[dict], prices: dict[str, float | None]) -> dict:
    """Calculate P&L for all share positions."""
    results = []
    total_cost = 0.0
    total_value = 0.0

    for pos in positions:
        if pos.get("position_type") != "shares":
            continue
        ticker = pos["ticker"]
        current_price = prices.get(ticker)
        if current_price is None:
            continue

        pnl = calc_pnl(pos["shares"], pos["cost_basis"], current_price)
        total_cost += pnl["total_cost"]
        total_value += pnl["market_value"]

        results.append({
            "ticker": ticker,
            "shares": pos["shares"],
            "cost_basis": pos["cost_basis"],
            "current_price": round(current_price, 2),
            "market_value": pnl["market_value"],
            "dollar_pnl": pnl["dollar_pnl"],
            "pct_pnl": pnl["pct_pnl"],
        })

    total_pnl = total_value - total_cost
    total_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

    return {
        "positions": results,
        "totals": {
            "total_cost": round(total_cost, 2),
            "total_value": round(total_value, 2),
            "total_dollar_pnl": round(total_pnl, 2),
            "total_pct_pnl": round(total_pct, 2),
        },
    }


def calculate_movers(positions: list[dict]) -> list[dict]:
    """Get today's movers for all positions."""
    tickers = list({p["ticker"] for p in positions if p.get("position_type") == "shares"})
    if not tickers:
        return []

    movers = []
    for ticker in tickers:
        try:
            hist = yf.download(ticker, period="2d", progress=False, auto_adjust=True)
            if len(hist) >= 2:
                prev = float(hist["Close"].iloc[-2])
                curr = float(hist["Close"].iloc[-1])
                change_pct = (curr - prev) / prev * 100
                movers.append({"ticker": ticker, "price": round(curr, 2), "change_pct": round(change_pct, 2)})
        except Exception:
            pass

    movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return movers
