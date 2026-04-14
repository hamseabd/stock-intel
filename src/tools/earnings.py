"""Earnings date fetching — yfinance."""

from datetime import date, datetime

import yfinance as yf


def fetch_earnings(tickers: list[str]) -> list[dict]:
    """Fetch next earnings date for each ticker."""
    today = date.today()
    results = []

    for ticker in tickers:
        tkr = yf.Ticker(ticker)
        next_date = None
        source = None

        # Try get_earnings_dates first
        try:
            df = tkr.get_earnings_dates(limit=8)
            if df is not None and not df.empty:
                for idx in df.index:
                    edate = idx.date() if hasattr(idx, "date") else datetime.strptime(str(idx)[:10], "%Y-%m-%d").date()
                    if edate >= today:
                        next_date = edate
                        source = "earnings_dates"
                        break
        except Exception:
            pass

        # Fallback: calendar
        if next_date is None:
            try:
                cal = tkr.calendar
                if isinstance(cal, dict):
                    ed = cal.get("Earnings Date")
                    if ed:
                        if isinstance(ed, list):
                            ed = ed[0]
                        next_date = ed.date() if hasattr(ed, "date") else datetime.strptime(str(ed)[:10], "%Y-%m-%d").date()
                        source = "calendar"
            except Exception:
                pass

        days_away = (next_date - today).days if next_date else None
        results.append({
            "ticker": ticker,
            "next_earnings_date": str(next_date) if next_date else "Unknown",
            "days_away": days_away,
            "source": source,
            "urgent": days_away is not None and days_away <= 30,
        })

    return results
