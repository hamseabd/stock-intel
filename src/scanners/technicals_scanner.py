"""Technicals scanner — RSI extremes, MACD crosses, SMA crosses."""

from shared.formatters import format_alert_technical
from tools.technicals import get_technical_flags
from scanners.utils import get_all_scan_tickers, queue_alert, update_dashboard


def run_technicals_scan() -> dict:
    tickers = get_all_scan_tickers()
    if not tickers:
        return {"alerts_sent": 0}

    flags = get_technical_flags(tickers)
    alerts_sent = 0

    for tf in flags:
        for reason in tf["reasons"]:
            msg = format_alert_technical(tf["ticker"], tf["signal"], reason)
            queue_alert("technicals", msg, buttons=[
                [{"text": f"Technicals {tf['ticker']}", "callback_data": f"/technicals {tf['ticker']}"}],
            ])
            alerts_sent += 1

    # Update dashboard
    from tools.technicals import analyze_technicals
    dashboard_data = []
    for ticker in tickers[:20]:
        t = analyze_technicals(ticker)
        if "error" not in t:
            dashboard_data.append(t)
    update_dashboard("technicals.json", {"tickers": dashboard_data})

    return {"alerts_sent": alerts_sent, "flags": len(flags)}
