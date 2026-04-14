"""Risk scanner — checks drawdowns, expiring options, concentration."""

from shared.config import TELEGRAM_CHAT_ID, DRAWDOWN_ALERT_PCT, OPTIONS_EXPIRY_WARN_DAYS
from shared.db import get_positions
from shared.formatters import format_alert_options_expiry, format_alert_price
from tools.prices import fetch_prices, calculate_portfolio_pnl
from tools.options import analyze_all_options
from scanners.utils import queue_alert


def run_risk_scan() -> dict:
    positions = get_positions(TELEGRAM_CHAT_ID)
    if not positions:
        return {"alerts_sent": 0}

    tickers = list({p["ticker"] for p in positions})
    prices = fetch_prices(tickers)
    pnl = calculate_portfolio_pnl(positions, prices)
    alerts_sent = 0

    # Drawdown alerts
    for p in pnl["positions"]:
        if p["pct_pnl"] <= DRAWDOWN_ALERT_PCT:
            msg = format_alert_price(
                p["ticker"], p["current_price"], p["pct_pnl"],
                f"Position: {p['shares']:.0f} shares, cost ${p['cost_basis']:.2f}\n"
                f"P&L: ${p['dollar_pnl']:+,.2f} ({p['pct_pnl']:+.1f}%)"
            )
            queue_alert("risk", msg, buttons=[
                [{"text": f"Analyze {p['ticker']}", "callback_data": f"/analyze {p['ticker']}"}],
                [{"text": f"Risk scan", "callback_data": "/risk"}],
            ])
            alerts_sent += 1

    # Expiring options
    option_analyses = analyze_all_options(positions)
    for o in option_analyses:
        if o["dte"] <= OPTIONS_EXPIRY_WARN_DAYS:
            msg = format_alert_options_expiry(
                o["ticker"], o["option_type"], o["strike"],
                o["dte"], o["delta"], o["recommendation"],
            )
            queue_alert("risk", msg, buttons=[
                [{"text": "Options analysis", "callback_data": "/options"}],
            ])
            alerts_sent += 1

    return {"alerts_sent": alerts_sent}
