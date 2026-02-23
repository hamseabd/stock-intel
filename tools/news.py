import json
import feedparser
from strands import tool


RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"


@tool
def get_news(ticker: str) -> str:
    """
    Fetches the 5 most recent news headlines for a given stock ticker from Yahoo Finance RSS.
    Use this tool when the user asks about news, headlines, or recent events for a specific ticker.

    Parameters:
    - ticker: Stock ticker symbol (e.g. "AMZN", "AMD", "SPY")

    Returns a JSON string with up to 5 recent headlines including title, summary, and published date.
    """
    url = RSS_URL.format(ticker=ticker.upper())
    feed = feedparser.parse(url)

    items = []
    for entry in feed.entries[:5]:
        items.append({
            "title": entry.get("title", ""),
            "summary": entry.get("summary", ""),
            "published": entry.get("published", ""),
            "link": entry.get("link", ""),
        })

    result = {
        "ticker": ticker.upper(),
        "headline_count": len(items),
        "headlines": items,
    }

    if not items:
        result["note"] = "No headlines found. RSS feed may be unavailable."

    return json.dumps(result, indent=2)
