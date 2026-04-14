"""Command router — two execution paths.

Direct commands: data fetch + math + format → response ($0, instant).
AI commands: data fetch + math + Claude synthesis → response (~$0.02).

Every command function signature: (chat_id: str, args: str) -> str
"""

import re
from datetime import datetime, timedelta, timezone

from shared.log import get_logger

logger = get_logger(__name__)

from bot.help import get_help
from bot.ai_commands import handle_brief, handle_catalyst, handle_risk, handle_analyze, handle_ask
from shared.db import (
    get_positions, get_watchlist, add_to_watchlist, remove_from_watchlist,
    get_alert_config, put_alert_config, get_price_alerts, put_price_alert,
    delete_price_alerts, get_trade_history,
)
from shared.formatters import (
    format_pnl_table, format_options_table, format_risk_flags, format_news,
    format_flow, format_technicals, format_congress_trades, format_darkpool,
    format_earnings, format_movers, format_watchlist, format_alert_config,
)
from tools.portfolio import get_portfolio, get_all_tickers, update_portfolio, parse_trade_text
from tools.prices import fetch_prices, calculate_portfolio_pnl, calculate_movers
from tools.options import analyze_option, analyze_all_options
from tools.options_flow import scan_options_flow, scan_flow_multiple
from tools.news import fetch_news, fetch_news_multiple
from tools.earnings import fetch_earnings
from tools.congress import get_congress_for_ticker, get_congress_recent, detect_clusters, get_sector_breakdown
from tools.darkpool import fetch_darkpool, analyze_darkpool_trend, get_darkpool_flags
from tools.technicals import analyze_technicals, get_technical_flags

_TICKER_RE = re.compile(r'^[A-Z]{1,5}(-[A-Z])?$')


def _valid_ticker(ticker: str) -> bool:
    """Validate that a string looks like a stock ticker symbol."""
    return bool(_TICKER_RE.match(ticker))


# ── Direct Commands (no Claude, $0) ───────────────────────────────────────

def cmd_pnl(chat_id: str, args: str) -> str:
    positions = get_portfolio(chat_id)
    if not positions:
        return "No positions. Use /update to add trades."

    if args:
        # Single ticker
        ticker = args.upper()
        pos = [p for p in positions if p["ticker"] == ticker and p["position_type"] == "shares"]
        if not pos:
            return f"No share position for {ticker}."
        prices = fetch_prices([ticker])
        pnl = calculate_portfolio_pnl(pos, prices)
        return format_pnl_table(pnl["positions"], pnl["totals"])

    tickers = list({p["ticker"] for p in positions})
    prices = fetch_prices(tickers)
    pnl = calculate_portfolio_pnl(positions, prices)
    return format_pnl_table(pnl["positions"], pnl["totals"])


def cmd_portfolio(chat_id: str, args: str) -> str:
    positions = get_portfolio(chat_id)
    if not positions:
        return "No positions. Use /update to add trades."

    lines = ["<b>PORTFOLIO</b>"]
    shares = [p for p in positions if p["position_type"] == "shares"]
    options = [p for p in positions if p["position_type"] == "option"]

    if shares:
        lines.append("\n<b>Shares:</b>")
        for p in shares:
            lines.append(f"  {p['ticker']}: {p['shares']:.0f} shares @ ${p['cost_basis']:.2f}")
    if options:
        lines.append("\n<b>Options:</b>")
        for p in options:
            status = p.get("status", "open")
            lines.append(
                f"  {p['ticker']} ${p['strike']:.0f} {p.get('option_type', '?')} "
                f"exp {p['expiry']} x{p.get('contracts', 1)} [{status}]"
            )
    return "\n".join(lines)


def cmd_options(chat_id: str, args: str) -> str:
    positions = get_portfolio(chat_id)
    analyses = analyze_all_options(positions)
    if not analyses:
        return "No open options positions."
    return format_options_table(analyses)


def cmd_put(chat_id: str, args: str) -> str:
    positions = get_portfolio(chat_id)
    put_positions = [p for p in positions if p.get("position_type") == "option" and p.get("option_type") == "put"]
    if not put_positions:
        return "No open put positions."
    analyses = analyze_all_options(put_positions)
    return format_options_table(analyses)


def cmd_update(chat_id: str, args: str) -> str:
    if not args:
        return "Usage: /update sold 50 AMZN at 195"
    parsed = parse_trade_text(args)
    if not parsed:
        return f"Couldn't parse: '{args}'\nTry: /update sold 50 AMZN at 195"
    return update_portfolio(chat_id, **parsed)


def cmd_history(chat_id: str, args: str) -> str:
    trades = get_trade_history(chat_id)
    if not trades:
        return "No trade history."
    lines = ["<b>RECENT TRADES</b>", "<pre>"]
    for t in trades[:20]:
        ts = t.get("timestamp", "")[:16]
        action = t.get("action", "?")
        ticker = t.get("ticker", "?")
        shares = t.get("shares", "")
        price = t.get("price", "")
        pnl = t.get("realized_pnl")
        pnl_str = f" P&L: ${pnl:+.2f}" if pnl is not None else ""
        lines.append(f"{ts} {action} {shares} {ticker} @${price}{pnl_str}")
    lines.append("</pre>")
    return "\n".join(lines)


def cmd_news(chat_id: str, args: str) -> str:
    if args:
        ticker = args.upper()
        headlines = fetch_news(ticker)
        return format_news(ticker, headlines)
    tickers = get_all_tickers(chat_id)
    if not tickers:
        return "No positions. Use /news TICKER for specific tickers."
    all_news = fetch_news_multiple(tickers, limit_per=2)
    lines = []
    for ticker, headlines in all_news.items():
        lines.append(format_news(ticker, headlines))
    return "\n\n".join(lines)


def cmd_flow(chat_id: str, args: str) -> str:
    if args:
        ticker = args.upper()
        flow = scan_options_flow(ticker)
        return format_flow(ticker, flow.get("alerts", []), flow.get("put_call_ratio", 1.0), flow.get("net_premium", {}))
    tickers = get_all_tickers(chat_id) + get_watchlist(chat_id)
    tickers = list(set(tickers))
    if not tickers:
        return "No tickers to scan. Add positions or use /watch."
    results = scan_flow_multiple(tickers)
    if not results:
        return "No unusual options activity detected across your tickers."
    lines = []
    for r in results[:5]:
        lines.append(format_flow(r["ticker"], r["alerts"][:3], r["put_call_ratio"], r["net_premium"]))
    return "\n\n".join(lines)


def cmd_technicals(chat_id: str, args: str) -> str:
    if not args:
        return "Usage: /technicals AMZN"
    ticker = args.upper()
    t = analyze_technicals(ticker)
    if "error" in t:
        return t["error"]
    return format_technicals(ticker, t)


def cmd_darkpool(chat_id: str, args: str) -> str:
    if args:
        ticker = args.upper()
        data = fetch_darkpool(ticker, days=14)
        trend = analyze_darkpool_trend(data)
        return format_darkpool(ticker, data, trend)
    tickers = get_all_tickers(chat_id) + get_watchlist(chat_id)
    tickers = list(set(tickers))
    if not tickers:
        return "No tickers to scan."
    flags = get_darkpool_flags(tickers)
    if not flags:
        return "No dark pool anomalies detected."
    lines = ["<b>DARK POOL FLAGS</b>"]
    for f in flags:
        lines.append(f"  {f['ticker']}: {f['dark_pct']:.1f}% off-exchange, {f['short_pct']:.1f}% short ({f['trend']})")
    return "\n".join(lines)


def cmd_congress(chat_id: str, args: str) -> str:
    if args:
        ticker = args.upper()
        trades = get_congress_for_ticker(ticker)
        return format_congress_trades(trades)
    trades = get_congress_recent(days=30)
    clusters = detect_clusters(trades)
    return format_congress_trades(trades[:20], clusters)


def cmd_earnings(chat_id: str, args: str) -> str:
    if args:
        tickers = [args.upper()]
    else:
        tickers = get_all_tickers(chat_id)
    if not tickers:
        return "No tickers. Use /earnings TICKER."
    results = fetch_earnings(tickers)
    return format_earnings(results)


def cmd_movers(chat_id: str, args: str) -> str:
    positions = get_portfolio(chat_id)
    movers = calculate_movers(positions)
    if not movers:
        return "No movers data available."
    return format_movers(movers)


def cmd_sector(chat_id: str, args: str) -> str:
    trades = get_congress_recent(days=30)
    sectors = get_sector_breakdown(trades)
    if not sectors:
        return "No sector data available."
    lines = ["<b>CONGRESS TRADING BY SECTOR</b>"]
    total = sum(sectors.values())
    for sector, count in sectors.items():
        pct = count / total * 100 if total > 0 else 0
        bar = "█" * int(pct / 5)
        lines.append(f"  {sector:<15} {bar} {pct:.0f}% ({count})")
    return "\n".join(lines)


def cmd_scan(chat_id: str, args: str) -> str:
    if not args:
        return "Usage: /scan NVDA"
    ticker = args.upper()

    sections = []

    # Price
    prices = fetch_prices([ticker])
    price = prices.get(ticker)
    if price:
        sections.append(f"<b>SCAN — {ticker}</b> (${price:.2f})")

    # Technicals
    t = analyze_technicals(ticker)
    if "error" not in t:
        sections.append(format_technicals(ticker, t))

    # Options flow
    flow = scan_options_flow(ticker)
    sections.append(format_flow(ticker, flow.get("alerts", [])[:3], flow.get("put_call_ratio", 1.0), flow.get("net_premium", {})))

    # Congress
    congress = get_congress_for_ticker(ticker)
    if congress:
        sections.append(format_congress_trades(congress[:5]))

    # Dark pool
    dp = fetch_darkpool(ticker, days=7)
    trend = analyze_darkpool_trend(dp)
    sections.append(format_darkpool(ticker, dp[:5], trend))

    # News
    headlines = fetch_news(ticker)
    sections.append(format_news(ticker, headlines))

    # Earnings
    earnings = fetch_earnings([ticker])
    sections.append(format_earnings(earnings))

    return "\n\n".join(sections)


def cmd_compare(chat_id: str, args: str) -> str:
    parts = args.upper().split()
    if len(parts) < 2:
        return "Usage: /compare AMD NVDA"
    t1, t2 = parts[0], parts[1]

    tech1 = analyze_technicals(t1)
    tech2 = analyze_technicals(t2)

    if "error" in tech1 or "error" in tech2:
        return f"Error fetching data for {t1 if 'error' in tech1 else t2}."

    lines = [f"<b>COMPARE: {t1} vs {t2}</b>", "<pre>"]
    lines.append(f"{'Metric':<14} {t1:>10} {t2:>10}")
    lines.append("-" * 36)
    lines.append(f"{'Price':<14} ${tech1['price']:>9.2f} ${tech2['price']:>9.2f}")
    lines.append(f"{'RSI':<14} {tech1['rsi_14']:>10.1f} {tech2['rsi_14']:>10.1f}")
    lines.append(f"{'MACD Hist':<14} {tech1['macd_histogram']:>+10.2f} {tech2['macd_histogram']:>+10.2f}")
    lines.append(f"{'SMA 50':<14} ${tech1['sma_50']:>9.2f} ${tech2['sma_50']:>9.2f}")
    lines.append(f"{'SMA 200':<14} ${tech1['sma_200']:>9.2f} ${tech2['sma_200']:>9.2f}")
    lines.append(f"{'Signal':<14} {tech1['overall_signal']:>10} {tech2['overall_signal']:>10}")
    lines.append("</pre>")
    return "\n".join(lines)


# ── Watchlist & Alerts ─────────────────────────────────────────────────────

def cmd_watch(chat_id: str, args: str) -> str:
    if not args:
        return "Usage: /watch NVDA TSLA"
    tickers = args.upper().split()
    for t in tickers:
        add_to_watchlist(chat_id, t)
    return f"Added to watchlist: {', '.join(tickers)}"


def cmd_unwatch(chat_id: str, args: str) -> str:
    if not args:
        return "Usage: /unwatch NVDA"
    ticker = args.upper()
    remove_from_watchlist(chat_id, ticker)
    return f"Removed {ticker} from watchlist."


def cmd_watchlist(chat_id: str, args: str) -> str:
    tickers = get_watchlist(chat_id)
    return format_watchlist(tickers)


def cmd_alerts(chat_id: str, args: str) -> str:
    config = get_alert_config(chat_id)

    if not args:
        price_alerts = get_price_alerts(chat_id)
        return format_alert_config(config, price_alerts)

    parts = args.lower().split()
    action = parts[0]

    if action == "on":
        config["enabled"] = True
        config["muted_until"] = None
        put_alert_config(chat_id, config)
        return "All alerts enabled."

    if action == "off":
        config["enabled"] = False
        put_alert_config(chat_id, config)
        return "All alerts disabled."

    if action == "mute":
        try:
            hours = int(parts[1].replace("h", "")) if len(parts) > 1 else 2
        except ValueError:
            return "Invalid mute duration. Usage: /alerts mute 2h"
        until = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
        config["muted_until"] = until
        put_alert_config(chat_id, config)
        return f"Alerts muted for {hours} hours."

    # Toggle specific types: /alerts congress on
    if len(parts) >= 2 and parts[1] in ("on", "off"):
        alert_type = parts[0]
        valid_types = ["congress", "flow", "darkpool", "technicals", "earnings", "price", "risk", "news"]
        if alert_type in valid_types:
            config[alert_type] = parts[1] == "on"
            put_alert_config(chat_id, config)
            return f"Alert type '{alert_type}' set to {parts[1].upper()}."

    return "Usage: /alerts [on|off|mute 2h|TYPE on|TYPE off]"


def cmd_threshold(chat_id: str, args: str) -> str:
    if not args:
        return "Usage: /threshold AMZN above 200"
    parts = args.upper().split()

    if parts[0] == "CLEAR" and len(parts) >= 2:
        delete_price_alerts(chat_id, parts[1])
        return f"Cleared price alerts for {parts[1]}."

    if len(parts) < 3:
        return "Usage: /threshold AMZN above 200"

    ticker = parts[0]
    direction = parts[1].lower()
    if direction not in ("above", "below"):
        return "Direction must be 'above' or 'below'."
    try:
        price = float(parts[2].replace("$", ""))
    except ValueError:
        return f"Invalid price: {parts[2]}"

    put_price_alert(chat_id, ticker, direction, price)
    return f"Price alert set: {ticker} {direction} ${price:.2f}"


def cmd_help(chat_id: str, args: str) -> str:
    return get_help(args if args else None)


# ── Command Router ─────────────────────────────────────────────────────────

DIRECT_COMMANDS = {
    "/pnl": cmd_pnl,
    "/portfolio": cmd_portfolio,
    "/options": cmd_options,
    "/put": cmd_put,
    "/update": cmd_update,
    "/history": cmd_history,
    "/news": cmd_news,
    "/flow": cmd_flow,
    "/technicals": cmd_technicals,
    "/darkpool": cmd_darkpool,
    "/congress": cmd_congress,
    "/earnings": cmd_earnings,
    "/movers": cmd_movers,
    "/sector": cmd_sector,
    "/scan": cmd_scan,
    "/compare": cmd_compare,
    "/watch": cmd_watch,
    "/unwatch": cmd_unwatch,
    "/watchlist": cmd_watchlist,
    "/alerts": cmd_alerts,
    "/threshold": cmd_threshold,
    "/help": cmd_help,
    "/start": cmd_help,
}

AI_COMMANDS = {
    "/brief": handle_brief,
    "/catalyst": handle_catalyst,
    "/risk": handle_risk,
    "/analyze": handle_analyze,
    "/ask": handle_ask,
}


def route_command(chat_id: str, text: str) -> str:
    """Route a Telegram message to the appropriate command handler.

    Args:
        chat_id: Telegram chat ID
        text: Raw message text from user

    Returns:
        Formatted response string (HTML) to send back via Telegram
    """
    text = text.strip()
    if not text:
        return "Send /help to see available commands."

    parts = text.split(None, 1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    # Validate ticker args for commands that take a single ticker
    _TICKER_COMMANDS = {
        "/pnl", "/news", "/flow", "/technicals", "/darkpool", "/congress",
        "/earnings", "/scan", "/catalyst", "/analyze",
    }
    if cmd in _TICKER_COMMANDS and args and not _valid_ticker(args.split()[0].upper()):
        return f"Invalid ticker: {args.split()[0].upper()}"

    # Direct commands — no Claude, instant, $0
    if cmd in DIRECT_COMMANDS:
        logger.info("Routing direct command", command=cmd, args=args[:50])
        return DIRECT_COMMANDS[cmd](chat_id, args)

    # AI commands — code gathers data, Claude reasons
    if cmd in AI_COMMANDS:
        logger.info("Routing AI command", command=cmd, args=args[:50])
        return AI_COMMANDS[cmd](chat_id, args)

    # Free-form text → AI
    if text.startswith("/"):
        return f"Unknown command: {cmd}\nType /help for available commands."

    # Treat non-command text as free-form question
    return handle_ask(chat_id, text)
