"""Dark pool scanner — FINRA short volume anomaly detection."""

from shared.formatters import format_alert_darkpool
from tools.darkpool import get_darkpool_flags, fetch_darkpool, analyze_darkpool_trend
from scanners.utils import get_all_scan_tickers, queue_alert, update_dashboard


def run_darkpool_scan() -> dict:
    tickers = get_all_scan_tickers()
    if not tickers:
        return {"alerts_sent": 0}

    flags = get_darkpool_flags(tickers)
    alerts_sent = 0

    for f in flags:
        msg = format_alert_darkpool(f["ticker"], f["dark_pct"], f["short_pct"])
        queue_alert("darkpool", msg, buttons=[
            [{"text": f"Dark pool {f['ticker']}", "callback_data": f"/darkpool {f['ticker']}"}],
            [{"text": f"Analyze {f['ticker']}", "callback_data": f"/analyze {f['ticker']}"}],
        ])
        alerts_sent += 1

    # Build dashboard data with history for each ticker
    dashboard_tickers = []
    for ticker in tickers[:20]:  # limit for performance
        data = fetch_darkpool(ticker, days=14)
        if data:
            trend = analyze_darkpool_trend(data)
            dashboard_tickers.append({
                "ticker": ticker,
                "history": data,
                "trend": trend,
                "latest_dark_pct": data[0]["dark_pct"],
                "latest_short_pct": data[0]["short_pct"],
            })

    update_dashboard("darkpool.json", {"tickers": dashboard_tickers})

    return {"alerts_sent": alerts_sent, "tickers_scanned": len(tickers)}
