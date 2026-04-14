"""AI-powered commands — code gathers data, Claude synthesizes.

Architecture:
1. Gather all data via pure code (yfinance, DynamoDB, FINRA) → $0
2. Format data into a compact text summary
3. Send ONLY the summary to Claude for synthesis → ~$0.01-0.03
4. Append Claude's response to the data sections

This keeps Claude costs minimal — it only sees pre-computed summaries,
not raw API responses.
"""

import json
import re

import anthropic

from shared.log import get_logger, Timer

logger = get_logger(__name__)

from shared.config import ANTHROPIC_API_KEY, CLAUDE_MODEL_SMART
from shared.db import get_positions, get_watchlist
from shared.formatters import (
    format_pnl_table, format_options_table, format_flow,
    format_technicals, format_congress_trades, format_darkpool,
    format_earnings, format_news,
)
from tools.portfolio import get_all_tickers
from tools.prices import fetch_prices, calculate_portfolio_pnl
from tools.options import analyze_all_options
from tools.options_flow import scan_options_flow, scan_flow_multiple
from tools.news import fetch_news, fetch_news_multiple
from tools.earnings import fetch_earnings
from tools.congress import get_congress_for_ticker, get_congress_recent, detect_clusters
from tools.darkpool import get_darkpool_flags, fetch_darkpool, analyze_darkpool_trend
from tools.technicals import analyze_technicals, get_technical_flags

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _ask_claude(system: str, user_msg: str, max_tokens: int = 1000) -> str:
    """Send a single prompt to Claude and return the text response.

    Args:
        system: System prompt defining Claude's role
        user_msg: The data summary + question for Claude
        max_tokens: Maximum response length

    Returns:
        Claude's text response
    """
    logger.info("Calling Claude", model=CLAUDE_MODEL_SMART, max_tokens=max_tokens,
                input_preview=user_msg[:100])
    client = _get_client()
    resp = client.messages.create(
        model=CLAUDE_MODEL_SMART,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return resp.content[0].text


SYSTEM_ANALYST = (
    "You are a concise investment analyst. Given market data, provide 2-4 actionable "
    "recommendations. Be specific (ticker, action, reasoning). No filler. Use plain text, "
    "no markdown headers. Keep it under 200 words."
)


def handle_brief(chat_id: str, args: str) -> str:
    """Morning intelligence brief — all data gathered by code, Claude synthesizes."""
    positions = get_positions(chat_id)
    tickers = list({p["ticker"] for p in positions})
    watchlist = get_watchlist(chat_id)
    all_tickers = list(set(tickers + watchlist))

    sections = ["<b>MORNING BRIEF</b>\n"]

    # 1. P&L
    if tickers:
        prices = fetch_prices(tickers)
        pnl = calculate_portfolio_pnl(positions, prices)
        sections.append(format_pnl_table(pnl["positions"], pnl["totals"]))

    # 2. Options
    option_analyses = analyze_all_options(positions)
    if option_analyses:
        sections.append(format_options_table(option_analyses))

    # 3. Urgent flags
    flags = []
    if tickers:
        for p in pnl["positions"]:
            if p["pct_pnl"] <= -10:
                flags.append(f"{p['ticker']} down {p['pct_pnl']:.1f}% from cost")
    for o in option_analyses:
        if o["dte"] <= 14:
            flags.append(f"{o['ticker']} ${o['strike']} {o['option_type']} expires in {o['dte']} days")
    earnings = fetch_earnings(tickers) if tickers else []
    for e in earnings:
        if e.get("urgent"):
            flags.append(f"{e['ticker']} earnings in {e['days_away']} days")
    if flags:
        sections.append("<b>URGENT FLAGS</b>\n" + "\n".join(f"! {f}" for f in flags))

    # 4. Unusual flow
    flow_results = scan_flow_multiple(all_tickers) if all_tickers else []
    if flow_results:
        flow_lines = ["<b>UNUSUAL OPTIONS ACTIVITY</b>"]
        for fr in flow_results[:3]:
            top = fr["alerts"][0] if fr["alerts"] else None
            if top:
                flow_lines.append(
                    f"  {fr['ticker']}: {top['option_type']} ${top['strike']:.0f} — "
                    f"{top['volume']:,} vol ({top['volume_oi_ratio']:.1f}x OI)"
                )
        sections.append("\n".join(flow_lines))

    # 5. Congress
    congress_trades = get_congress_recent(days=2)
    my_ticker_trades = [t for t in congress_trades if t["ticker"] in tickers]
    clusters = detect_clusters(get_congress_recent(days=14))
    if my_ticker_trades or clusters:
        congress_text = "<b>CONGRESS (48h)</b>\n"
        if my_ticker_trades:
            for t in my_ticker_trades[:3]:
                congress_text += f"  {t['member']} {t['tx_type']} {t['ticker']} ({t['amount']})\n"
        if clusters:
            for c in clusters[:2]:
                congress_text += f"  Cluster: {c['ticker']} — {len(c['members'])} members {c['direction']}\n"
        sections.append(congress_text)

    # 6. Dark pool
    dp_flags = get_darkpool_flags(all_tickers) if all_tickers else []
    if dp_flags:
        dp_text = "<b>DARK POOL FLAGS</b>\n"
        for f in dp_flags[:3]:
            dp_text += f"  {f['ticker']}: {f['dark_pct']:.1f}% off-exchange ({f['trend']})\n"
        sections.append(dp_text)

    # 7. News
    if tickers:
        all_news = fetch_news_multiple(tickers, limit_per=1)
        news_lines = ["<b>NEWS</b>"]
        for ticker, headlines in all_news.items():
            if headlines:
                news_lines.append(f"  {ticker}: {headlines[0]['title'][:80]}")
        sections.append("\n".join(news_lines))

    # 8. Technicals
    tech_flags = get_technical_flags(tickers) if tickers else []
    if tech_flags:
        tech_text = "<b>TECHNICALS</b>\n"
        for tf in tech_flags[:3]:
            tech_text += f"  {tf['ticker']}: {', '.join(tf['reasons'][:2])}\n"
        sections.append(tech_text)

    # 9. AI Recommendations (Claude — the only part that costs money)
    data_summary = "\n".join(sections)
    try:
        recs = _ask_claude(
            SYSTEM_ANALYST,
            f"Here is today's market data for my portfolio:\n\n{_strip_html(data_summary)}\n\n"
            "Give 2-4 specific, actionable recommendations. Be direct.",
            max_tokens=500,
        )
        sections.append(f"\n<b>AI RECOMMENDATIONS</b>\n{recs}")
    except Exception as e:
        sections.append(f"\n<i>AI recommendations unavailable: {e}</i>")

    return "\n\n".join(sections)


def handle_catalyst(chat_id: str, args: str) -> str:
    """Catalyst analysis for a ticker."""
    if not args:
        return "Usage: /catalyst AMZN"
    ticker = args.upper()

    # Gather all data via code
    data_parts = []

    earnings = fetch_earnings([ticker])
    if earnings:
        data_parts.append(f"Earnings: {earnings[0].get('next_earnings_date', 'Unknown')} ({earnings[0].get('days_away', '?')} days)")

    flow = scan_options_flow(ticker)
    if flow.get("alerts"):
        top = flow["alerts"][0]
        data_parts.append(f"Options flow: {top['option_type']} ${top['strike']:.0f} has {top['volume']:,} vol ({top['volume_oi_ratio']:.1f}x OI)")
    data_parts.append(f"Put/call ratio: {flow.get('put_call_ratio', 'N/A')}")

    congress = get_congress_for_ticker(ticker)
    if congress:
        data_parts.append(f"Congress: {len(congress)} trades — latest: {congress[0].get('member', '?')} {congress[0].get('tx_type', '?')} ({congress[0].get('amount', '')})")

    dp = fetch_darkpool(ticker, days=7)
    if dp:
        data_parts.append(f"Dark pool: {dp[0]['dark_pct']:.1f}% off-exchange, short: {dp[0]['short_pct']:.1f}%")

    tech = analyze_technicals(ticker)
    if "error" not in tech:
        data_parts.append(f"RSI: {tech['rsi_14']:.1f}, MACD hist: {tech['macd_histogram']:+.2f}, Signal: {tech['overall_signal']}")
        data_parts.append(f"SMA50: ${tech['sma_50']:.2f}, SMA200: ${tech['sma_200']:.2f}")

    headlines = fetch_news(ticker, limit=3)
    if headlines:
        data_parts.append("Headlines: " + " | ".join(h["title"][:60] for h in headlines))

    summary = "\n".join(data_parts)

    try:
        analysis = _ask_claude(
            SYSTEM_ANALYST,
            f"Analyze upcoming catalysts for {ticker}:\n\n{summary}\n\n"
            "What are the key upcoming catalysts? What's the likely impact on the stock? "
            "Give specific levels to watch and a clear bull/bear case.",
            max_tokens=600,
        )
        return f"<b>CATALYSTS — {ticker}</b>\n\n{summary}\n\n<b>AI ANALYSIS</b>\n{analysis}"
    except Exception as e:
        return f"<b>CATALYSTS — {ticker}</b>\n\n{summary}\n\n<i>AI analysis unavailable: {e}</i>"


def handle_risk(chat_id: str, args: str) -> str:
    """Portfolio risk scan."""
    positions = get_positions(chat_id)
    tickers = list({p["ticker"] for p in positions})
    if not tickers:
        return "No positions to assess."

    data_parts = []

    # P&L check
    prices = fetch_prices(tickers)
    pnl = calculate_portfolio_pnl(positions, prices)
    for p in pnl["positions"]:
        if p["pct_pnl"] <= -10:
            data_parts.append(f"DRAWDOWN: {p['ticker']} down {p['pct_pnl']:.1f}%")

    # Options expiry
    for o in analyze_all_options(positions):
        if o["dte"] <= 14:
            data_parts.append(f"EXPIRING: {o['ticker']} ${o['strike']} {o['option_type']} in {o['dte']}d (delta: {o['delta']:+.2f})")

    # Earnings
    for e in fetch_earnings(tickers):
        if e.get("days_away") is not None and e["days_away"] <= 30:
            data_parts.append(f"EARNINGS: {e['ticker']} in {e['days_away']} days")

    # Concentration
    total = pnl["totals"]["total_value"]
    if total > 0:
        for p in pnl["positions"]:
            weight = p["market_value"] / total * 100
            if weight > 30:
                data_parts.append(f"CONCENTRATION: {p['ticker']} is {weight:.0f}% of portfolio")

    # Dark pool flags
    dp_flags = get_darkpool_flags(tickers)
    for f in dp_flags:
        data_parts.append(f"DARK POOL: {f['ticker']} at {f['dark_pct']:.1f}% off-exchange ({f['trend']})")

    # Technical flags
    for tf in get_technical_flags(tickers):
        data_parts.append(f"TECHNICAL: {tf['ticker']} — {', '.join(tf['reasons'][:2])}")

    summary = "\n".join(data_parts) if data_parts else "No significant risk flags detected."

    try:
        assessment = _ask_claude(
            SYSTEM_ANALYST,
            f"Portfolio risk assessment:\n\n{summary}\n\n"
            f"Portfolio totals: ${pnl['totals']['total_value']:,.0f} value, {pnl['totals']['total_pct_pnl']:+.1f}% P&L\n\n"
            "Rank risks by severity. Give 2-3 specific actions to reduce risk.",
            max_tokens=500,
        )
        return f"<b>RISK SCAN</b>\n\n{summary}\n\n<b>AI ASSESSMENT</b>\n{assessment}"
    except Exception as e:
        return f"<b>RISK SCAN</b>\n\n{summary}\n\n<i>AI assessment unavailable: {e}</i>"


def handle_analyze(chat_id: str, args: str) -> str:
    """Deep analysis of a single ticker."""
    if not args:
        return "Usage: /analyze AMZN"
    ticker = args.upper()

    # Gather everything
    sections = [f"<b>ANALYSIS — {ticker}</b>\n"]

    tech = analyze_technicals(ticker)
    if "error" not in tech:
        sections.append(format_technicals(ticker, tech))

    flow = scan_options_flow(ticker)
    sections.append(format_flow(ticker, flow.get("alerts", [])[:3], flow.get("put_call_ratio", 1.0), flow.get("net_premium", {})))

    congress = get_congress_recent(days=30)
    ticker_congress = [t for t in congress if t["ticker"] == ticker]
    if ticker_congress:
        sections.append(format_congress_trades(ticker_congress[:5]))

    dp = fetch_darkpool(ticker, days=7)
    trend = analyze_darkpool_trend(dp)
    sections.append(format_darkpool(ticker, dp[:5], trend))

    headlines = fetch_news(ticker)
    sections.append(format_news(ticker, headlines))

    earnings = fetch_earnings([ticker])
    sections.append(format_earnings(earnings))

    data_summary = "\n".join(sections)

    try:
        thesis = _ask_claude(
            SYSTEM_ANALYST,
            f"Give a complete investment analysis for {ticker}:\n\n{_strip_html(data_summary)}\n\n"
            "Synthesize all signals into a clear bull/bear thesis. "
            "Give a specific recommendation: buy, sell, hold, or wait. Include key levels.",
            max_tokens=600,
        )
        sections.append(f"\n<b>AI THESIS</b>\n{thesis}")
    except Exception as e:
        sections.append(f"\n<i>AI thesis unavailable: {e}</i>")

    return "\n\n".join(sections)


def handle_ask(chat_id: str, args: str) -> str:
    """Free-form question answered by Claude with portfolio context."""
    if not args:
        return "Usage: /ask Should I roll my AMD put?"

    positions = get_positions(chat_id)
    if positions:
        summary_items = []
        for p in positions:
            if p.get("position_type") == "shares":
                summary_items.append(f"{p['ticker']}: {p.get('shares', 0):.0f} shares @ ${p.get('cost_basis', 0):.2f}")
            elif p.get("position_type") == "option":
                summary_items.append(f"{p['ticker']}: ${p.get('strike', 0):.0f} {p.get('option_type', '?')} exp {p.get('expiry', '?')}")
        context = "Portfolio: " + "; ".join(summary_items)
    else:
        context = "No positions"

    try:
        answer = _ask_claude(
            "You are an investment analyst assistant. The user has a portfolio you can see in the context. "
            "Answer their question concisely with specific, actionable advice.",
            f"Context: {context}\n\nQuestion: {args}",
            max_tokens=500,
        )
        return answer
    except Exception as e:
        return f"Error: {e}"


def _strip_html(text: str) -> str:
    """Remove HTML tags for Claude input."""
    return re.sub(r"<[^>]+>", "", text)
