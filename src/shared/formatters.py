"""Telegram message formatters. Pure string formatting — no I/O, no API calls.

All functions return plain text with Telegram MarkdownV2 or HTML formatting.
We use HTML mode for Telegram because it's less fussy with escaping.
"""


def format_pnl_table(positions: list[dict], totals: dict) -> str:
    lines = ["<b>PORTFOLIO P&amp;L</b>", "<pre>"]
    lines.append(f"{'Ticker':<6} {'Shares':>6} {'Cost':>8} {'Price':>8} {'$ P&L':>10} {'% P&L':>7}")
    lines.append("-" * 53)
    for p in positions:
        flag = " !!" if p.get("pct_pnl") is not None and p["pct_pnl"] <= -10 else ""
        lines.append(
            f"{p['ticker']:<6} {p['shares']:>6.0f} "
            f"${p['cost_basis']:>7.2f} ${p['current_price']:>7.2f} "
            f"${p['dollar_pnl']:>+9.2f} {p['pct_pnl']:>+6.1f}%{flag}"
        )
    lines.append("-" * 53)
    lines.append(
        f"{'TOTAL':<6} {'':>6} "
        f"${totals['total_cost']:>7.0f} ${totals['total_value']:>7.0f} "
        f"${totals['total_dollar_pnl']:>+9.2f} {totals['total_pct_pnl']:>+6.1f}%"
    )
    lines.append("</pre>")
    return "\n".join(lines)


def format_options_table(options: list[dict]) -> str:
    if not options:
        return "<b>OPTIONS</b>\nNo open options positions."
    lines = ["<b>OPTIONS</b>", "<pre>"]
    lines.append(f"{'Ticker':<6} {'Type':<5} {'Strike':>7} {'Expiry':<11} {'DTE':>4} {'Delta':>6} {'Rec':<12}")
    lines.append("-" * 57)
    for o in options:
        lines.append(
            f"{o['ticker']:<6} {o['option_type']:<5} ${o['strike']:>6.0f} "
            f"{o['expiry']:<11} {o['dte']:>4} {o['delta']:>+5.2f} {o['recommendation']:<12}"
        )
    lines.append("</pre>")
    return "\n".join(lines)


def format_risk_flags(flags: list[dict]) -> str:
    if not flags:
        return "<b>RISK FLAGS</b>\nNo urgent flags."
    lines = ["<b>URGENT FLAGS</b>"]
    for f in flags:
        severity = "!!" if f.get("severity") == "HIGH" else "!"
        lines.append(f"{severity} {f['message']}")
    return "\n".join(lines)


def format_news(ticker: str, headlines: list[dict]) -> str:
    lines = [f"<b>NEWS — {ticker}</b>"]
    if not headlines:
        lines.append("No recent headlines found.")
        return "\n".join(lines)
    for i, h in enumerate(headlines[:5], 1):
        title = html_escape(h.get("title", ""))
        pub = h.get("published", "")[:16]
        link = h.get("link", "")
        lines.append(f"{i}. <a href=\"{link}\">{title}</a>")
        if pub:
            lines.append(f"   {pub}")
    return "\n".join(lines)


def format_flow(ticker: str, alerts: list[dict], pcr: float, net_premium: dict) -> str:
    lines = [f"<b>OPTIONS FLOW — {ticker}</b>"]
    lines.append(f"Put/Call Ratio: {pcr:.2f}")
    lines.append(f"Net Premium: ${net_premium.get('bullish', 0):,.0f} bullish / ${net_premium.get('bearish', 0):,.0f} bearish")
    if not alerts:
        lines.append("\nNo unusual activity detected.")
        return "\n".join(lines)
    lines.append(f"\n<b>Top Unusual Contracts:</b>")
    for a in alerts[:5]:
        emoji = "C" if a["option_type"] == "call" else "P"
        lines.append(
            f"  {emoji} ${a['strike']:.0f} {a['expiry']} — "
            f"Vol: {a['volume']:,} ({a['volume_oi_ratio']:.1f}x OI) "
            f"Premium: ${a['premium']:,.0f} [{a['direction']}]"
        )
    return "\n".join(lines)


def format_technicals(ticker: str, t: dict) -> str:
    lines = [f"<b>TECHNICALS — {ticker}</b> (${t['price']:.2f})"]
    lines.append(f"Signal: <b>{t['overall_signal'].upper()}</b>")
    lines.append(f"<pre>")
    lines.append(f"RSI (14):    {t['rsi_14']:>6.1f}  {'(oversold)' if t['rsi_14'] < 30 else '(overbought)' if t['rsi_14'] > 70 else ''}")
    lines.append(f"MACD:        {t['macd_line']:>+6.2f}  Signal: {t['macd_signal']:>+6.2f}")
    lines.append(f"MACD Hist:   {t['macd_histogram']:>+6.2f}  {'(bullish)' if t['macd_histogram'] > 0 else '(bearish)'}")
    lines.append(f"SMA 50:      ${t['sma_50']:>7.2f}  {'above' if t['price'] > t['sma_50'] else 'BELOW'}")
    lines.append(f"SMA 200:     ${t['sma_200']:>7.2f}  {'above' if t['price'] > t['sma_200'] else 'BELOW'}")
    lines.append(f"Bollinger:   ${t['bb_lower']:.2f} / ${t['bb_middle']:.2f} / ${t['bb_upper']:.2f}")
    lines.append(f"Support:     ${t['support']:.2f}")
    lines.append(f"Resistance:  ${t['resistance']:.2f}")
    lines.append(f"Volume:      {t['current_volume']:,.0f} (avg: {t['avg_volume']:,.0f})")
    lines.append("</pre>")
    return "\n".join(lines)


def format_congress_trades(trades: list[dict], clusters: list[dict] = None) -> str:
    lines = ["<b>CONGRESSIONAL TRADES</b>"]
    if clusters:
        lines.append("\n<b>CLUSTER ALERTS:</b>")
        for c in clusters:
            members = ", ".join(c["members"][:3])
            if len(c["members"]) > 3:
                members += f" +{len(c['members']) - 3} more"
            lines.append(f"  {c['ticker']}: {len(c['members'])} members {c['direction']} ({members})")
    if not trades:
        lines.append("\nNo recent congressional trades.")
        return "\n".join(lines)
    lines.append(f"\n<pre>{'Date':<11} {'Member':<15} {'P':>1} {'Ticker':<6} {'Type':<5} {'Amount':<15}</pre>")
    for t in trades[:15]:
        member = t.get("member", "")[:14]
        party = t.get("party", "?")[0]
        lines.append(
            f"<pre>{t.get('trade_date', ''):<11} {member:<15} {party:>1} "
            f"{t.get('ticker', ''):<6} {t.get('tx_type', '')[:4]:<5} {t.get('amount', ''):<15}</pre>"
        )
    return "\n".join(lines)


def format_darkpool(ticker: str, data: list[dict], trend: str) -> str:
    lines = [f"<b>DARK POOL — {ticker}</b>"]
    if not data:
        lines.append("No dark pool data available.")
        return "\n".join(lines)
    latest = data[0]
    lines.append(f"Off-Exchange: <b>{latest['dark_pct']:.1f}%</b> {'(HIGH)' if latest['dark_pct'] > 40 else ''}")
    lines.append(f"Short Volume: <b>{latest['short_pct']:.1f}%</b> {'(HIGH)' if latest['short_pct'] > 50 else ''}")
    lines.append(f"Trend: {trend}")
    if len(data) > 1:
        lines.append(f"\n<pre>{'Date':<11} {'Dark%':>6} {'Short%':>7} {'Volume':>12}</pre>")
        for d in data[:7]:
            lines.append(f"<pre>{d['date']:<11} {d['dark_pct']:>5.1f}% {d['short_pct']:>6.1f}% {d['total_volume']:>12,}</pre>")
    return "\n".join(lines)


def format_earnings(tickers: list[dict]) -> str:
    lines = ["<b>EARNINGS</b>"]
    if not tickers:
        lines.append("No earnings data.")
        return "\n".join(lines)
    for t in tickers:
        status = ""
        days = t.get("days_away")
        if days is not None and days <= 7:
            status = " (THIS WEEK)"
        elif days is not None and days <= 14:
            status = " (SOON)"
        lines.append(f"  {t['ticker']}: {t.get('next_earnings_date', 'Unknown')} ({days}d away){status}")
    return "\n".join(lines)


def format_movers(movers: list[dict]) -> str:
    lines = ["<b>TODAY'S MOVERS</b>"]
    for m in movers:
        arrow = "+" if m["change_pct"] >= 0 else ""
        lines.append(f"  {m['ticker']}: ${m['price']:.2f} ({arrow}{m['change_pct']:.1f}%)")
    return "\n".join(lines)


def format_watchlist(tickers: list[str]) -> str:
    if not tickers:
        return "<b>WATCHLIST</b>\nEmpty. Use /watch TICKER to add."
    return "<b>WATCHLIST</b>\n" + ", ".join(tickers)


def format_alert_config(config: dict, price_alerts: list[dict]) -> str:
    lines = ["<b>ALERT CONFIG</b>"]
    lines.append(f"Alerts: {'ON' if config.get('enabled', True) else 'OFF'}")
    muted = config.get("muted_until")
    if muted:
        lines.append(f"Muted until: {muted}")
    lines.append(f"\n<pre>")
    for key in ["congress", "flow", "darkpool", "technicals", "earnings", "price", "risk", "news"]:
        state = "ON" if config.get(key, True) else "OFF"
        lines.append(f"  {key:<12} {state}")
    lines.append("</pre>")
    if price_alerts:
        lines.append("\n<b>Price Alerts:</b>")
        for pa in price_alerts:
            lines.append(f"  {pa['ticker']} {pa['direction']} ${pa['target_price']:.2f}")
    return "\n".join(lines)


# ── Alert Messages ─────────────────────────────────────────────────────────

def format_alert_price(ticker: str, price: float, change_pct: float, details: str) -> str:
    emoji = "🔴" if abs(change_pct) > 5 else "🟡"
    direction = "UP" if change_pct > 0 else "DOWN"
    return f"{emoji} <b>{ticker} {direction} {abs(change_pct):.1f}%</b> (${price:.2f})\n{details}"


def format_alert_flow(ticker: str, strike: float, expiry: str, option_type: str,
                      volume: int, oi: int, premium: float, direction: str) -> str:
    ratio = volume / oi if oi > 0 else volume
    return (
        f"🟡 <b>UNUSUAL FLOW: {ticker} ${strike:.0f} {option_type}s</b>\n"
        f"Volume: {volume:,} ({ratio:.1f}x OI) | Premium: ${premium:,.0f}\n"
        f"Expiry: {expiry} | Direction: {direction}\n"
        f"→ /flow {ticker}"
    )


def format_alert_congress(trade: dict) -> str:
    return (
        f"🔵 <b>CONGRESS: {trade['member']}</b> ({trade['party']})\n"
        f"{trade['tx_type']} {trade['ticker']} | {trade['amount']}\n"
        f"Filed: {trade['filing_date']}\n"
        f"→ /congress {trade['ticker']}"
    )


def format_alert_congress_cluster(ticker: str, members: list[str], direction: str) -> str:
    member_str = ", ".join(members[:3])
    if len(members) > 3:
        member_str += f" +{len(members) - 3}"
    return (
        f"🔴 <b>CONGRESS CLUSTER: {ticker}</b>\n"
        f"{len(members)} members {direction} in the last 14 days\n"
        f"{member_str}\n"
        f"→ /congress {ticker}"
    )


def format_alert_earnings(ticker: str, days: int) -> str:
    urgency = "🔴" if days <= 3 else "🟡"
    return (
        f"{urgency} <b>EARNINGS: {ticker} in {days} days</b>\n"
        f"→ /catalyst {ticker}"
    )


def format_alert_options_expiry(ticker: str, option_type: str, strike: float, dte: int,
                                delta: float, recommendation: str) -> str:
    return (
        f"🔴 <b>EXPIRING: {ticker} ${strike:.0f} {option_type}</b>\n"
        f"DTE: {dte} | Delta: {delta:+.2f}\n"
        f"Rec: {recommendation}\n"
        f"→ /options"
    )


def format_alert_darkpool(ticker: str, dark_pct: float, short_pct: float) -> str:
    return (
        f"🔵 <b>DARK POOL: {ticker}</b>\n"
        f"Off-exchange: {dark_pct:.1f}% | Short: {short_pct:.1f}%\n"
        f"→ /darkpool {ticker}"
    )


def format_alert_technical(ticker: str, signal: str, details: str) -> str:
    return (
        f"🔵 <b>TECHNICAL: {ticker}</b>\n"
        f"{signal}: {details}\n"
        f"→ /technicals {ticker}"
    )


def html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
