"""Price scanner — checks price thresholds and big intraday moves."""

from shared.config import TELEGRAM_CHAT_ID
from shared.db import get_positions, get_price_alerts
from shared.formatters import format_alert_price
from tools.prices import fetch_prices, calculate_movers
from scanners.utils import get_all_scan_tickers, queue_alert, update_dashboard


def run_price_scan() -> dict:
    alerts_sent = 0

    # Check price threshold alerts
    price_alerts = get_price_alerts(TELEGRAM_CHAT_ID)
    if price_alerts:
        tickers = list({pa["ticker"] for pa in price_alerts})
        prices = fetch_prices(tickers)
        for pa in price_alerts:
            current = prices.get(pa["ticker"])
            if current is None:
                continue
            triggered = False
            if pa["direction"] == "above" and current >= pa["target_price"]:
                triggered = True
            elif pa["direction"] == "below" and current <= pa["target_price"]:
                triggered = True
            if triggered:
                msg = format_alert_price(
                    pa["ticker"], current, 0,
                    f"Hit your threshold: {pa['direction']} ${pa['target_price']:.2f}"
                )
                queue_alert("price", msg, buttons=[
                    [{"text": f"Analyze {pa['ticker']}", "callback_data": f"/analyze {pa['ticker']}"}],
                    [{"text": "Clear alert", "callback_data": f"/threshold clear {pa['ticker']}"}],
                ])
                alerts_sent += 1

    # Check for big movers (>3% intraday)
    positions = get_positions(TELEGRAM_CHAT_ID)
    movers = calculate_movers(positions)
    for m in movers:
        if abs(m["change_pct"]) >= 3:
            direction = "up" if m["change_pct"] > 0 else "down"
            msg = format_alert_price(
                m["ticker"], m["price"], m["change_pct"],
                f"Big move: {direction} {abs(m['change_pct']):.1f}% today"
            )
            queue_alert("price", msg, buttons=[
                [{"text": f"Analyze {m['ticker']}", "callback_data": f"/analyze {m['ticker']}"}],
            ])
            alerts_sent += 1

    # Update dashboard
    update_dashboard("movers.json", {"movers": movers})

    return {"alerts_sent": alerts_sent, "movers": len(movers)}
