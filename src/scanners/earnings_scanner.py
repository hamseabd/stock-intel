"""Earnings scanner — countdown alerts at 14d, 7d, 3d, 1d."""

from shared.formatters import format_alert_earnings
from tools.earnings import fetch_earnings
from scanners.utils import get_all_scan_tickers, queue_alert

ALERT_DAYS = {14, 7, 3, 1}


def run_earnings_scan() -> dict:
    tickers = get_all_scan_tickers()
    if not tickers:
        return {"alerts_sent": 0}

    earnings = fetch_earnings(tickers)
    alerts_sent = 0

    for e in earnings:
        days = e.get("days_away")
        if days is not None and days in ALERT_DAYS:
            msg = format_alert_earnings(e["ticker"], days)
            queue_alert("earnings", msg, buttons=[
                [{"text": f"Catalyst {e['ticker']}", "callback_data": f"/catalyst {e['ticker']}"}],
            ])
            alerts_sent += 1

    return {"alerts_sent": alerts_sent, "tickers_checked": len(tickers)}
