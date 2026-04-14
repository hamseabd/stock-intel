"""News fetching — Yahoo Finance RSS."""

import feedparser

RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"


def fetch_news(ticker: str, limit: int = 5) -> list[dict]:
    """Fetch latest headlines for a ticker from Yahoo Finance RSS."""
    url = RSS_URL.format(ticker=ticker.upper())
    feed = feedparser.parse(url)

    items = []
    for entry in feed.entries[:limit]:
        items.append({
            "title": entry.get("title", ""),
            "summary": entry.get("summary", ""),
            "published": entry.get("published", ""),
            "link": entry.get("link", ""),
        })
    return items


def fetch_news_multiple(tickers: list[str], limit_per: int = 3) -> dict[str, list[dict]]:
    """Fetch headlines for multiple tickers."""
    results = {}
    for ticker in tickers:
        results[ticker] = fetch_news(ticker, limit=limit_per)
    return results
