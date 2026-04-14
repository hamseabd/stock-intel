"""Help text — static, zero cost, instant response."""

HELP_MAIN = """<b>STOCK ASSISTANT — COMMANDS</b>

<b>PORTFOLIO</b>
  /pnl [TICKER]          Live P&amp;L (all or one)
  /portfolio              All positions with status
  /options                Analyze all open options
  /put                    Analyze open puts
  /update [trade]         Record a trade
  /history                Recent trade log

<b>RESEARCH</b> (per ticker)
  /news TICKER            Top headlines
  /flow TICKER            Unusual options activity
  /technicals TICKER      RSI, MACD, SMA, Bollinger
  /darkpool TICKER        Dark pool volume + short %
  /congress TICKER        Congressional trades
  /earnings TICKER        Next earnings date

<b>INTELLIGENCE</b> (cross-portfolio)
  /flow                   Unusual options — all tickers
  /congress               All congressional trades + clusters
  /darkpool               Dark pool flags — all tickers
  /movers                 Biggest portfolio movers today
  /sector                 Congress trading by sector
  /scan TICKER            Run ALL checks on one ticker
  /compare T1 T2          Side-by-side comparison

<b>AI-POWERED</b> (uses Claude)
  /brief                  Morning intelligence brief
  /catalyst TICKER        Catalysts + impact analysis
  /risk                   Portfolio risk scan + recs
  /analyze TICKER         Complete picture + thesis
  /ask [question]         Ask anything

<b>WATCHLIST &amp; ALERTS</b>
  /watch TICKER [T2 T3]   Add to watchlist
  /unwatch TICKER         Remove from watchlist
  /watchlist              Show watched tickers
  /alerts                 Show alert config
  /alerts on/off          Enable/disable alerts
  /alerts mute 2h         Snooze alerts
  /threshold T above $N   Set price alert
  /threshold clear T      Remove price alerts

Type /help [command] for details on any command."""

HELP_DETAIL = {
    "pnl": """<b>/pnl — Live P&amp;L</b>

Fetches live prices and calculates P&amp;L for all positions.

<b>Usage:</b>
  /pnl           All positions
  /pnl AMZN      Single position

<b>Output:</b> Table with ticker, shares, cost basis, current price, $ P&amp;L, % P&amp;L, portfolio totals. Flags positions down &gt;10%.

<b>Data:</b> yfinance (free, real-time)
<b>Cost:</b> $0 (pure math)""",

    "portfolio": """<b>/portfolio — All Positions</b>

Shows all positions including shares and options with status.

<b>Usage:</b> /portfolio
<b>Cost:</b> $0""",

    "options": """<b>/options — Options Analysis</b>

Analyzes all open options positions with full Greeks.

<b>Output per option:</b>
  Strike vs price, DTE, bid/ask/mid, IV
  Delta, gamma, theta, vega
  Intrinsic/extrinsic value
  Recommendation: roll / hold / close / let expire

<b>Usage:</b> /options
<b>Data:</b> yfinance options chains + Black-Scholes math
<b>Cost:</b> $0""",

    "put": """<b>/put — Put Analysis</b>

Same as /options but filtered to puts only.

<b>Usage:</b> /put
<b>Cost:</b> $0""",

    "update": """<b>/update — Record a Trade</b>

Parse and record a trade from natural language.

<b>Usage:</b>
  /update sold 50 AMZN at 195
  /update bought 100 AMD at 165.50
  /update buy 20 QQQ at 420

<b>Cost:</b> $0 (regex parsing)""",

    "history": """<b>/history — Trade Log</b>

Shows your last 20 trades.

<b>Usage:</b> /history
<b>Cost:</b> $0""",

    "news": """<b>/news — Headlines</b>

Fetches top 5 headlines from Yahoo Finance RSS.

<b>Usage:</b>
  /news AMZN     Headlines for AMZN
  /news          Headlines for all held tickers

<b>Data:</b> Yahoo Finance RSS (free)
<b>Cost:</b> $0""",

    "flow": """<b>/flow — Unusual Options Activity</b>

Scans options chains for unusual volume and premium.

<b>Flags:</b>
  Volume &gt; 5x open interest
  Single-strike premium &gt; $500K
  Put/call ratio extremes
  Net premium flow direction

<b>Usage:</b>
  /flow AMZN     Scan AMZN only
  /flow          Scan all held + watchlist tickers

<b>Output:</b> Top unusual contracts, put/call ratio, net premium.
<b>Data:</b> yfinance options chains (free)
<b>Cost:</b> $0""",

    "technicals": """<b>/technicals — Technical Analysis</b>

Key technical indicators and levels.

<b>Output:</b>
  RSI (14-day), MACD + signal + histogram
  50/200 SMA (golden/death cross)
  Bollinger Bands
  Support/resistance levels
  Volume trend
  Overall signal: bullish/bearish/neutral

<b>Usage:</b> /technicals AMZN
<b>Data:</b> yfinance price history + math
<b>Cost:</b> $0""",

    "darkpool": """<b>/darkpool — Dark Pool Data</b>

Off-exchange volume % and short volume analysis.

<b>Flags:</b> &gt;40% off-exchange, &gt;50% short volume
<b>Shows:</b> Daily data, trend (rising/falling/stable)

<b>Usage:</b>
  /darkpool AMZN    Single ticker
  /darkpool         All held + watchlist

<b>Data:</b> FINRA short volume reports (free, T+1)
<b>Cost:</b> $0""",

    "congress": """<b>/congress — Congressional Trades</b>

Recent congressional stock trades with signal detection.

<b>Signals:</b>
  Cluster trades (2+ members, same ticker)
  Committee-relevant trades
  Large trades ($500K+)
  Intelligence committee activity

<b>Usage:</b>
  /congress AMZN    Trades on AMZN
  /congress         All recent trades + clusters

<b>Data:</b> Capitol Trades (free)
<b>Cost:</b> $0""",

    "earnings": """<b>/earnings — Earnings Dates</b>

Next earnings date and countdown for your tickers.

<b>Usage:</b>
  /earnings AMZN    Single ticker
  /earnings         All held tickers

<b>Data:</b> yfinance
<b>Cost:</b> $0""",

    "brief": """<b>/brief — Morning Intelligence Brief</b>

The flagship command. Gathers ALL data and delivers a full report.

<b>Sections:</b>
  1. Portfolio P&amp;L table
  2. Open options with Greeks
  3. Urgent flags
  4. Unusual options activity
  5. Congressional trades (last 48h)
  6. Dark pool signals
  7. News headlines
  8. Technical levels
  9. AI Recommendations (Claude)

Sections 1-8: pure data ($0). Section 9: Claude (~$0.02).

<b>Usage:</b> /brief
<b>Best used:</b> Once daily, pre-market.""",

    "catalyst": """<b>/catalyst — Catalyst Analysis</b>

Upcoming catalysts and their potential impact.

<b>Covers:</b> Earnings, events, options activity, congressional trades, dark pool, technicals.
<b>AI-powered:</b> Claude synthesizes all data into catalyst analysis.

<b>Usage:</b> /catalyst AMZN
<b>Cost:</b> ~$0.02 (Claude for analysis paragraph)""",

    "risk": """<b>/risk — Risk Scan</b>

Full portfolio risk scan with recommendations.

<b>Checks:</b>
  Positions down &gt;10%
  Options expiring within 14 days
  Earnings within 30 days
  Concentration risk
  Dark pool anomalies
  Bearish technical signals

<b>Usage:</b> /risk
<b>Cost:</b> ~$0.02 (Claude for risk assessment paragraph)""",

    "analyze": """<b>/analyze — Deep Analysis</b>

Complete picture of a ticker: price + flow + congress + dark pool + technicals + news. Claude synthesizes into an investment thesis.

<b>Usage:</b> /analyze AMZN
<b>Cost:</b> ~$0.03 (Claude for thesis)""",

    "ask": """<b>/ask — Free-Form Question</b>

Ask anything. Claude has access to all tools.

<b>Examples:</b>
  /ask Should I roll my AMD call?
  /ask Why is SPY dropping?
  /ask Compare AMD and NVDA

<b>Cost:</b> ~$0.02-0.05 per question""",

    "watch": """<b>/watch — Add to Watchlist</b>

Watchlist tickers get scanned by all scanners but don't appear in P&amp;L.

<b>Usage:</b>
  /watch NVDA
  /watch NVDA TSLA PLTR""",

    "unwatch": """<b>/unwatch — Remove from Watchlist</b>

<b>Usage:</b> /unwatch NVDA""",

    "watchlist": """<b>/watchlist — Show Watchlist</b>

<b>Usage:</b> /watchlist""",

    "alerts": """<b>/alerts — Alert Configuration</b>

<b>Usage:</b>
  /alerts              Show config
  /alerts on           Enable all
  /alerts off          Disable all
  /alerts mute 2h      Snooze for 2 hours
  /alerts congress on  Toggle specific type
  /alerts flow off     Toggle specific type

<b>Types:</b> congress, flow, darkpool, technicals, earnings, price, risk, news""",

    "threshold": """<b>/threshold — Price Alerts</b>

Set price alerts that fire when a ticker crosses a level.

<b>Usage:</b>
  /threshold AMZN above 200
  /threshold AMD below 155
  /threshold clear AMZN""",

    "movers": """<b>/movers — Today's Movers</b>

Biggest intraday movers in your portfolio.

<b>Usage:</b> /movers
<b>Cost:</b> $0""",

    "sector": """<b>/sector — Congress by Sector</b>

What sectors Congress is trading most.

<b>Usage:</b> /sector
<b>Cost:</b> $0""",

    "scan": """<b>/scan — Full Scan</b>

Run ALL checks on a single ticker: price, flow, technicals, dark pool, congress, news, earnings.

<b>Usage:</b> /scan NVDA
<b>Cost:</b> $0 (no AI)""",

    "compare": """<b>/compare — Side-by-Side</b>

Compare two tickers across all metrics.

<b>Usage:</b> /compare AMD NVDA
<b>Cost:</b> $0""",
}


def get_help(command: str = None) -> str:
    if command:
        cmd = command.lstrip("/").lower()
        return HELP_DETAIL.get(cmd, f"Unknown command: {cmd}. Try /help")
    return HELP_MAIN
