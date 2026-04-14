"""Congress scanner — scrape new trades, detect clusters, alert."""

from shared.config import TELEGRAM_CHAT_ID
from shared.db import get_positions
from shared.formatters import format_alert_congress, format_alert_congress_cluster
from shared.s3 import write_raw_data
from tools.congress import scrape_capitol_trades, store_trades, detect_clusters, get_sector_breakdown
from scanners.utils import queue_alert, update_dashboard


def run_congress_scan() -> dict:
    # Scrape latest trades
    trades = scrape_capitol_trades(pages=3)
    if not trades:
        return {"scraped": 0, "stored": 0, "alerts_sent": 0}

    # Store raw data
    write_raw_data("congress", {"trades": trades})

    # Store in DynamoDB
    stored = store_trades(trades)

    # Get user's tickers for matching
    positions = get_positions(TELEGRAM_CHAT_ID)
    held_tickers = {p["ticker"] for p in positions}

    alerts_sent = 0

    # Alert on trades matching user's tickers
    for trade in trades:
        if trade["ticker"] in held_tickers:
            msg = format_alert_congress(trade)
            queue_alert("congress", msg, buttons=[
                [{"text": f"Congress {trade['ticker']}", "callback_data": f"/congress {trade['ticker']}"}],
                [{"text": f"Analyze {trade['ticker']}", "callback_data": f"/analyze {trade['ticker']}"}],
            ])
            alerts_sent += 1

    # Detect and alert on clusters
    clusters = detect_clusters(trades)
    for cluster in clusters:
        if len(cluster["members"]) >= 3 or cluster["ticker"] in held_tickers:
            msg = format_alert_congress_cluster(
                cluster["ticker"], cluster["members"], cluster["direction"]
            )
            buttons = [[{"text": f"Watch {cluster['ticker']}", "callback_data": f"/watch {cluster['ticker']}"}]]
            if cluster["ticker"] in held_tickers:
                buttons = [[{"text": f"Analyze {cluster['ticker']}", "callback_data": f"/analyze {cluster['ticker']}"}]]
            queue_alert("congress", msg, buttons=buttons)
            alerts_sent += 1

    # Alert on whale trades ($1M+)
    for trade in trades:
        if "whale_trade" in trade.get("signals", []) and trade["ticker"] not in held_tickers:
            msg = format_alert_congress(trade)
            queue_alert("congress", msg, buttons=[
                [{"text": f"Watch {trade['ticker']}", "callback_data": f"/watch {trade['ticker']}"}],
            ])
            alerts_sent += 1

    # Update dashboard
    sectors = get_sector_breakdown(trades)
    update_dashboard("congress.json", {
        "recent_trades": trades[:50],
        "clusters": clusters,
        "sectors": sectors,
    })

    return {"scraped": len(trades), "stored": stored, "alerts_sent": alerts_sent, "clusters": len(clusters)}
