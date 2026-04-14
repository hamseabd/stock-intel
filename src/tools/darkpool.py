"""Dark pool / off-exchange data — FINRA short volume reports."""

import csv
import io
from datetime import date, timedelta

import requests


FINRA_SHORT_VOLUME_URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{date}.txt"


def _fetch_finra_day(target_date: date) -> list[dict]:
    """Fetch FINRA short volume data for a single day."""
    date_str = target_date.strftime("%Y%m%d")
    url = FINRA_SHORT_VOLUME_URL.format(date=date_str)
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        reader = csv.DictReader(io.StringIO(resp.text), delimiter="|")
        rows = []
        for row in reader:
            if row.get("Symbol"):
                rows.append(row)
        return rows
    except Exception:
        return []


def fetch_darkpool(ticker: str, days: int = 14) -> list[dict]:
    """Fetch dark pool / short volume data for a ticker over recent trading days."""
    ticker = ticker.upper()
    results = []
    today = date.today()

    for i in range(days + 10):  # extra buffer for weekends/holidays
        d = today - timedelta(days=i)
        if d.weekday() >= 5:  # skip weekends
            continue
        rows = _fetch_finra_day(d)
        for row in rows:
            if row.get("Symbol", "").upper() == ticker:
                short_vol = int(float(row.get("ShortVolume", 0)))
                short_exempt = int(float(row.get("ShortExemptVolume", 0)))
                total_vol = int(float(row.get("TotalVolume", 0)))
                if total_vol == 0:
                    continue
                dark_vol = short_vol + short_exempt
                results.append({
                    "ticker": ticker,
                    "date": d.strftime("%Y-%m-%d"),
                    "short_volume": short_vol,
                    "short_exempt_volume": short_exempt,
                    "total_volume": total_vol,
                    "dark_volume": dark_vol,
                    "dark_pct": round(dark_vol / total_vol * 100, 1),
                    "short_pct": round(short_vol / total_vol * 100, 1),
                })
                break

        if len(results) >= days:
            break

    return results


def analyze_darkpool_trend(data: list[dict]) -> str:
    """Determine if dark pool activity is trending up, down, or stable."""
    if len(data) < 3:
        return "insufficient data"

    recent = sum(d["dark_pct"] for d in data[:3]) / 3
    older = sum(d["dark_pct"] for d in data[-3:]) / 3

    if recent > older + 5:
        return "rising"
    elif recent < older - 5:
        return "falling"
    return "stable"


def get_darkpool_flags(tickers: list[str], threshold: float = 40.0) -> list[dict]:
    """Scan multiple tickers for dark pool anomalies."""
    flags = []
    for ticker in tickers:
        data = fetch_darkpool(ticker, days=5)
        if not data:
            continue
        latest = data[0]
        if latest["dark_pct"] > threshold or latest["short_pct"] > 50:
            trend = analyze_darkpool_trend(data)
            flags.append({
                "ticker": ticker,
                "dark_pct": latest["dark_pct"],
                "short_pct": latest["short_pct"],
                "trend": trend,
                "date": latest["date"],
            })
    return flags
