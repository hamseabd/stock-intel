"""News scanner — checks for new headlines on held + watched tickers."""

from tools.news import fetch_news_multiple
from scanners.utils import get_all_scan_tickers, queue_alert


def run_news_scan() -> dict:
    tickers = get_all_scan_tickers()
    if not tickers:
        return {"alerts_sent": 0}

    all_news = fetch_news_multiple(tickers, limit_per=2)
    alerts_sent = 0

    # Simple keyword-based urgency detection
    URGENT_KEYWORDS = [
        "downgrade", "upgrade", "lawsuit", "SEC", "FDA", "recall",
        "bankruptcy", "acquisition", "merger", "guidance", "miss",
        "beat", "cut", "raise", "halt", "investigation", "scandal",
    ]

    for ticker, headlines in all_news.items():
        for h in headlines:
            title_lower = h.get("title", "").lower()
            if any(kw in title_lower for kw in URGENT_KEYWORDS):
                msg = (
                    f"🟡 <b>NEWS: {ticker}</b>\n"
                    f"{h['title'][:120]}\n"
                    f"{h.get('published', '')[:20]}\n"
                    f"→ /news {ticker}"
                )
                queue_alert("news", msg, buttons=[
                    [{"text": f"News {ticker}", "callback_data": f"/news {ticker}"}],
                    [{"text": f"Analyze {ticker}", "callback_data": f"/analyze {ticker}"}],
                ])
                alerts_sent += 1
                break  # one alert per ticker max

    return {"alerts_sent": alerts_sent, "tickers_checked": len(tickers)}
