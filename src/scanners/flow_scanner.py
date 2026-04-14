"""Options flow scanner — unusual activity detection."""

from shared.formatters import format_alert_flow
from tools.options_flow import scan_flow_multiple
from scanners.utils import get_all_scan_tickers, queue_alert, update_dashboard


def run_flow_scan() -> dict:
    tickers = get_all_scan_tickers()
    if not tickers:
        return {"alerts_sent": 0}

    results = scan_flow_multiple(tickers)
    alerts_sent = 0

    for flow in results:
        for alert in flow.get("alerts", [])[:2]:  # top 2 per ticker
            if alert["volume_oi_ratio"] >= 10 or alert["premium"] >= 1_000_000:
                msg = format_alert_flow(
                    alert["ticker"], alert["strike"], alert["expiry"],
                    alert["option_type"], alert["volume"], alert["open_interest"],
                    alert["premium"], alert["direction"],
                )
                queue_alert("flow", msg, buttons=[
                    [{"text": f"Full flow {alert['ticker']}", "callback_data": f"/flow {alert['ticker']}"}],
                    [{"text": f"Analyze {alert['ticker']}", "callback_data": f"/analyze {alert['ticker']}"}],
                ])
                alerts_sent += 1

    # Update dashboard
    dashboard_data = {
        "tickers": [
            {
                "ticker": r["ticker"],
                "unusual_count": r["unusual_count"],
                "put_call_ratio": r["put_call_ratio"],
                "net_premium": r["net_premium"],
                "top_alerts": r["alerts"][:5],
            }
            for r in results
        ]
    }
    update_dashboard("flow.json", dashboard_data)

    return {"alerts_sent": alerts_sent, "tickers_scanned": len(tickers)}
