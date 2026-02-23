import json
from datetime import date, datetime, timezone
from pathlib import Path
import yfinance as yf
from strands import tool

PORTFOLIO_PATH = Path(__file__).parent.parent / "data" / "portfolio.json"
EARNINGS_WINDOW_DAYS = 30


@tool
def get_earnings() -> str:
    """
    Fetches upcoming earnings dates for all tickers in the portfolio.
    Flags any ticker with earnings within the next 30 days as urgent.
    Use this tool when the user asks about earnings, earnings risk, or the morning brief.

    Returns a JSON string with earnings dates per ticker and an urgent flags list.
    """
    data = json.loads(PORTFOLIO_PATH.read_text())
    tickers = list({p["ticker"] for p in data["positions"]})

    today = date.today()
    results = []
    urgent = []

    for ticker in tickers:
        tkr = yf.Ticker(ticker)
        next_earnings_date = None
        source = None

        # Try get_earnings_dates() first (most reliable)
        try:
            earnings_df = tkr.get_earnings_dates(limit=8)
            if earnings_df is not None and not earnings_df.empty:
                for idx in earnings_df.index:
                    # Index is a DatetimeTZAware or datetime
                    if hasattr(idx, "date"):
                        edate = idx.date()
                    else:
                        edate = datetime.strptime(str(idx)[:10], "%Y-%m-%d").date()
                    if edate >= today:
                        next_earnings_date = edate
                        source = "earnings_dates"
                        break
        except Exception:
            pass

        # Fallback: calendar
        if next_earnings_date is None:
            try:
                cal = tkr.calendar
                if cal is not None:
                    # calendar may be a dict or DataFrame
                    if isinstance(cal, dict):
                        ed = cal.get("Earnings Date")
                        if ed:
                            if isinstance(ed, list):
                                ed = ed[0]
                            if hasattr(ed, "date"):
                                next_earnings_date = ed.date()
                            else:
                                next_earnings_date = datetime.strptime(
                                    str(ed)[:10], "%Y-%m-%d"
                                ).date()
                            source = "calendar"
                    else:
                        # DataFrame — try to extract
                        if "Earnings Date" in cal.columns:
                            val = cal["Earnings Date"].iloc[0]
                            if hasattr(val, "date"):
                                next_earnings_date = val.date()
                            else:
                                next_earnings_date = datetime.strptime(
                                    str(val)[:10], "%Y-%m-%d"
                                ).date()
                            source = "calendar"
            except Exception:
                pass

        days_away = (next_earnings_date - today).days if next_earnings_date else None
        is_urgent = days_away is not None and days_away <= EARNINGS_WINDOW_DAYS

        entry = {
            "ticker": ticker,
            "next_earnings_date": str(next_earnings_date) if next_earnings_date else "Unknown",
            "days_away": days_away,
            "source": source,
            "urgent": is_urgent,
        }
        results.append(entry)
        if is_urgent:
            urgent.append({
                "ticker": ticker,
                "date": str(next_earnings_date),
                "days_away": days_away,
            })

    return json.dumps({
        "today": str(today),
        "earnings_window_days": EARNINGS_WINDOW_DAYS,
        "tickers": results,
        "urgent_flags": urgent,
    }, indent=2)
