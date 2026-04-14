# DIY Market Intelligence Platform — Transformation Plan

## Vision
Turn a local terminal REPL into a cloud-deployed market intelligence platform you interact with via Telegram from your phone. Think Unusual Whales, but yours, built cheap.

---

## Architecture Overview

```
┌─────────────┐     HTTPS webhook      ┌──────────────────┐
│  Telegram    │ ◄──────────────────►   │  API Gateway      │
│  (your phone)│                        │  (REST endpoint)  │
└─────────────┘                        └────────┬─────────┘
                                                │
                              ┌─────────────────┼─────────────────┐
                              │                 │                 │
                        ┌─────▼─────┐    ┌──────▼──────┐   ┌─────▼──────┐
                        │  Lambda:   │    │  Lambda:     │   │  Lambda:    │
                        │  Bot       │    │  Scheduled   │   │  Agent      │
                        │  Handler   │    │  Scanners    │   │  (Claude)   │
                        └─────┬─────┘    └──────┬──────┘   └─────┬──────┘
                              │                 │                 │
                   ┌──────────┼─────────────────┼─────────────────┤
                   │          │                 │                 │
             ┌─────▼────┐ ┌──▼───┐ ┌───────────▼──┐  ┌──────────▼──────┐
             │ DynamoDB  │ │ SQS  │ │ Data Sources  │  │ S3              │
             │ portfolio │ │alerts│ │ (free APIs)   │  │ historical data │
             │ positions │ │queue │ │               │  │ snapshots       │
             │ watchlist │ └──┬───┘ └───────────────┘  └─────────────────┘
             └──────────┘    │
                        ┌────▼─────┐
                        │ Telegram │
                        │ alert msg│
                        └──────────┘
```

---

## Phase 1: Core Infrastructure (Week 1-2)
> Goal: Get the current app running on AWS with Telegram interface

### 1A. Telegram Bot Setup
- Create bot via @BotFather, get token
- Register commands: `/pnl`, `/news`, `/risk`, `/brief`, `/update`, `/put`, `/catalyst`, `/flow`, `/congress`, `/darkpool`
- Bot handler Lambda receives webhook, routes to agent

### 1B. AWS Infrastructure (Serverless = Cheap)
| Service | Use | Monthly Cost |
|---------|-----|-------------|
| Lambda | Bot handler, agent, scanners | ~$0-3 (free tier: 1M requests) |
| API Gateway | Telegram webhook endpoint | ~$0 (free tier: 1M calls) |
| DynamoDB | Portfolio, watchlist, alerts config | ~$0 (free tier: 25GB) |
| S3 | Historical snapshots, trade logs | ~$0.02/GB |
| EventBridge | Cron triggers for scanners | Free |
| SQS | Alert queue | Free tier |
| **Total** | | **~$1-5/month + Claude API** |

### 1C. Migrate Data Layer
- `portfolio.json` → DynamoDB `positions` table
- `snapshots.jsonl` → S3 (partitioned by date)
- `trades.jsonl` → DynamoDB `trades` table
- Add `watchlist` table (tickers to monitor without holding)

### 1D. Project Structure (New)
```
infrastructure/
  main.tf                     — Terraform: Lambda, API Gateway, DynamoDB, S3, EventBridge, SQS
  variables.tf                — Environment variables (API keys, bot token, etc.)
  outputs.tf                  — API Gateway URL, S3 bucket name, etc.

src/
  bot/
    handler.py                — Telegram webhook → parse command → invoke agent
    telegram_client.py        — Send messages, format rich replies, inline keyboards
    commands.py               — Command routing (/pnl, /flow, /congress, etc.)

  agent/
    handler.py                — Lambda: receives command, runs Strands agent, returns response
    system_prompt.md          — Updated system prompt

  tools/
    portfolio.py              — DynamoDB-backed portfolio CRUD
    prices.py                 — yfinance batch pricing + P&L
    options.py                — Black-Scholes Greeks (keep existing)
    options_flow.py           — NEW: unusual options activity detection
    news.py                   — Yahoo RSS + FINVIZ + SEC filings
    earnings.py               — yfinance earnings (keep existing)
    congress.py               — NEW: congressional trading data
    darkpool.py               — NEW: dark pool / off-exchange volume
    technicals.py             — NEW: key technical indicators
    sentiment.py              — NEW: news sentiment scoring
    alerts.py                 — NEW: alert CRUD + delivery
    logger.py                 — S3-backed logging

  scanners/
    handler.py                — EventBridge-triggered Lambda
    unusual_activity.py       — Options flow anomaly scan
    congress_scan.py          — New congressional trades
    price_alerts.py           — Price threshold alerts
    earnings_scan.py          — Upcoming earnings proximity
    darkpool_scan.py          — Dark pool volume spikes

  shared/
    db.py                     — DynamoDB helpers
    s3.py                     — S3 helpers
    config.py                 — Environment config
    models.py                 — Pydantic models for positions, alerts, etc.

tests/
data/                         — Local dev fallback
```

---

## Phase 2: Data Sources — The Intelligence Layer (Week 2-3)
> Goal: Add the data feeds that make this actually useful

### 2A. Congressional Trading (FREE) — Deep Dive

#### Why This Matters (Academic Backing)
- **Ziobrowski et al. (2004)**: Senators beat the market by ~12% annually
- **Ziobrowski et al. (2011)**: House members beat by ~6% annually
- Post-STOCK Act (2012): advantage narrowed but did NOT disappear
- Most alpha comes from: Finance, Intelligence, and Armed Services committee members
- 45-day disclosure delay means the edge is in *pattern recognition*, not speed

#### What to Track: ALL Trades, Smart Prioritization

| Priority | What | Action |
|----------|------|--------|
| **Tier 1** | Congress trades YOUR held tickers | Telegram alert immediately |
| **Tier 2** | Cluster trades (2+ members, same ticker, <14 days) | Telegram alert + dashboard flag |
| **Tier 3** | Committee-relevant trades (member's committee oversees the sector) | Telegram alert |
| **Tier 4** | Large trades ($500K+ range) by any member | Dashboard highlight |
| **Tier 5** | ALL trades | Dashboard table (sortable, filterable) |
| **Tier 6** | Member scorecards (historical win rate) | Dashboard leaderboard |

#### Data Sources (Ranked by Quality)

| Source | Method | Data Quality | Cost |
|--------|--------|-------------|------|
| **Capitol Trades** (`bff.capitoltrades.com/trades`) | JSON API (undocumented, paginated) | Best — normalized tickers, committee data, clean JSON | Free |
| **QuiverQuant** (`api.quiverquant.com/beta/`) | REST API | Good — may need paid key now ($10-30/mo) | Free/Paid |
| **House Clerk** (`disclosures-clerk.house.gov`) | XML bulk + HTML scrape | Raw — free-text asset names need ticker resolution | Free |
| **Senate EFDS** (`efdsearch.senate.gov`) | HTML scrape (has CAPTCHA) | Raw — harder to automate | Free |
| **SEC EDGAR Form 4** | REST API | Indirect — only if member is a 10%+ holder | Free |

**Start with Capitol Trades** — clean JSON, includes committees, no auth needed.
Add QuiverQuant as dedup/coverage source.
Skip raw House/Senate filings initially (parsing burden too high).

#### Capitol Trades API Response Shape
```json
{
  "data": [{
    "politician": {"name": "Pelosi, Nancy", "party": "D", "chamber": "House",
                   "state": "CA", "committees": ["Financial Services"]},
    "ticker": "NVDA",
    "assetType": "Stock",
    "txType": "Purchase",
    "txDate": "2026-03-15",
    "filingDate": "2026-04-08",
    "amount": "$1,000,001 - $5,000,000",
    "owner": "Spouse"
  }]
}
```

#### Available Data Fields

| Field | Source | Notes |
|-------|--------|-------|
| Member name | All sources | Normalized differently per source |
| Party (D/R/I) | Capitol Trades, QuiverQuant | Must be joined for raw filings |
| State/District | Capitol Trades, QuiverQuant | |
| Chamber (House/Senate) | All | Senators are more predictive |
| **Committee assignments** | Capitol Trades | Critical for Tier 3 signals |
| Ticker | Capitol Trades, QuiverQuant | Raw filings use free-text descriptions |
| Transaction type | All | Purchase, Sale (Full), Sale (Partial), Exchange |
| **Amount range** | All | $1K-15K, $15K-50K, $50K-100K, $100K-250K, $250K-500K, $500K-1M, $1M-5M, $5M+ |
| Trade date | All | Actual transaction date |
| Filing date | All | When disclosed (up to 45 days after trade) |
| Owner | Some | Self, Spouse, Dependent Child, Joint |

#### Signal Detection Logic

**Cluster Detection** (strongest signal):
```python
# GROUP BY ticker WHERE count(distinct member) >= 2 AND date_range <= 14 days
# Example: 4 members bought NVDA within 7 days = strong buy signal
```

**Committee Relevance** (requires sector mapping):
```python
COMMITTEE_SECTORS = {
    "Armed Services": ["LMT", "RTX", "NOC", "BA", "GD", "LHX"],
    "Banking/Finance": ["JPM", "BAC", "GS", "MS", "WFC", "C"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "OXY"],
    "Health": ["UNH", "JNJ", "PFE", "ABBV", "MRK", "LLY"],
    "Intelligence": [],  # Flag ALL trades — they have classified briefings
    "Commerce/Tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"],
}
# Flag when member's committee matches the trade's sector
```

**Conviction Sizing**:
```python
# Only alert on >= $50,001 range (skip $1K-$15K noise)
# Highlight $500K+ as "high conviction"
# $1M+ as "whale trade"
```

#### Tool: `get_congress_trades(ticker=None, member=None, days=30, min_amount="$50,001")`
```python
# If ticker provided: trades for that ticker across all members
# If member provided: all trades by that member
# If neither: all trades in the time window, ranked by signal strength
# Always returns: cluster alerts, committee flags, conviction score
```

#### Scanner: `congress_scan` — Every 6 hours via EventBridge
Alerts to Telegram when:
1. ANY member trades a ticker you hold or have on watchlist
2. Cluster detected: 2+ members, same ticker, within 14 days
3. Committee-relevant trade: member trades in their oversight sector
4. Whale trade: any member at $1M+ range
5. Intelligence Committee member makes ANY stock trade

#### S3 Static Dashboard — Congress Section

**Dashboard panels** (Tailwind + Chart.js + AG Grid):

```
┌─────────────────────────────────────────────────────────┐
│  🏛️ Congressional Trade Tracker              Updated 2m │
├───────────────────────────┬─────────────────────────────┤
│ 🔴 CLUSTER ALERTS         │ 📊 SECTOR HEATMAP (Chart.js)│
│ NVDA: 4 members bought    │ Tech ████████████ 42%       │
│   in 7 days ($3M+ total)  │ Defense ██████ 18%          │
│ LMT: 2 Armed Services     │ Finance █████ 15%           │
│   members bought           │ Health ████ 12%             │
│                            │ Energy ███ 8%               │
├───────────────────────────┴─────────────────────────────┤
│ 📋 RECENT TRADES (AG Grid — sortable, filterable)       │
│ Date    | Member       |P| Ticker | Type | Amount       │
│ Apr 8   | Pelosi, N    |D| NVDA   | Buy  | $1M-$5M  🔥 │
│ Apr 7   | Tuberville,T |R| NVDA   | Buy  | $250K-500K   │
│ Apr 5   | Ossoff, J    |D| MSFT   | Buy  | $50K-100K    │
│ [Filter: Party ▼] [Committee ▼] [Ticker ▼] [Amount ▼]  │
├───────────────────────────┬─────────────────────────────┤
│ 🏆 MEMBER SCORECARDS      │ 📈 FOLLOW-CONGRESS INDEX     │
│ 1. Pelosi    +34% (6mo)  │ (Lightweight Charts)         │
│ 2. Tuberville +28%       │ [chart: portfolio if you      │
│ 3. Ossoff    +22%        │  mirrored all congress buys   │
│ 4. Crenshaw  +19%        │  vs S&P 500 over 12 months]  │
│ 5. Sullivan  +15%        │                               │
└───────────────────────────┴─────────────────────────────┘
```

#### Dashboard Tech Stack
| Component | Library | Size | Why |
|-----------|---------|------|-----|
| Price/time charts | **TradingView Lightweight Charts** | 40KB | Built for financial data, GPU-accelerated |
| Trade tables | **AG Grid Community** | Free | Sort, filter, paginate — the best free grid |
| Bar/pie/heatmap | **Chart.js** | 60KB | Sector allocation, member rankings |
| CSS | **Tailwind CSS** (CDN) | 0 (CDN) | Dark mode, responsive, no build step |
| Auth | **S3 bucket policy (IP restrict) or none** | Free | Unguessable URL + public market data = fine |

#### Dashboard Hosting Cost
| Component | Monthly |
|-----------|---------|
| S3 storage (<1GB) | $0.02 |
| S3 requests (~5K GETs) | $0.002 |
| **Total** | **~$0.02/month** |

No CloudFront needed — S3 static website hosting serves directly. You're the only user.

#### Data Pipeline
```
EventBridge (every 6h) → Lambda (scraper)
  → Capitol Trades API → raw JSON to S3
  → Lambda (processor)
    → deduplicate, detect clusters, score signals
    → write to DynamoDB (congress_trades table)
    → generate dashboard JSON → write to S3
  → Dashboard JS fetches JSON, renders charts/tables
```

#### DynamoDB Schema for Congress Trades
```
Table: congress_trades
PK: {member_id}#{trade_date}
SK: {ticker}#{filing_date}
Attributes: member_name, party, state, chamber, committees[],
            ticker, asset_description, tx_type, amount_range,
            trade_date, filing_date, owner, signals[], score
GSI1: ticker-trade_date-index  (query by ticker)
GSI2: filing_date-index        (query recent filings)
GSI3: score-index              (query by signal strength)
```

### 2B. Dark Pool / Off-Exchange Data (FREE)
**Source**: FINRA ADF (Alternative Display Facility) + OTC data

| Source | Method | Delay | Cost |
|--------|--------|-------|------|
| FINRA Short Volume | Daily CSV download | T+1 | Free |
| FINRA ADF/OTC volume | REST API | T+1 | Free |
| SEC FTD data | Bi-monthly CSV | 2 weeks | Free |

**Tool: `get_darkpool(ticker, days=14)`**
```python
# Returns:
# - Dark pool volume vs lit exchange volume (% off-exchange)
# - Short volume ratio
# - Trend: is dark pool % increasing/decreasing?
# - Unusual flag: >40% off-exchange or short ratio >50%
```

**Scanner: `darkpool_scan`** — Daily after market close:
- Flag tickers where dark pool % is abnormally high (>40%)
- Flag rising short volume trends
- Correlate with price action (divergence = bearish signal)

### 2C. Options Flow & Unusual Activity (FREE via yfinance)
**Source**: yfinance options chains (already using) + volume analysis

**Tool: `get_options_flow(ticker)`**
```python
# Scans ALL expiries and strikes for unusual activity:
# - Volume > 5x average open interest (unusual)
# - Large OI changes day-over-day
# - Put/call ratio extremes
# - Premium concentration (where is smart money?)
#
# Returns:
# - Top 5 most unusual contracts
# - Overall put/call ratio
# - Total premium flow (bullish vs bearish)
# - "Smart money" signal: large single-strike bets
```

**Scanner: `unusual_activity_scan`** — Runs every 30 min during market hours:
- Scan watchlist + held tickers
- Alert on volume > 10x OI
- Alert on single contract with >$1M premium
- Classify: bullish sweep, bearish put buy, hedge, etc.

### 2D. Enhanced News & Sentiment (FREE)
**Sources**: Yahoo RSS (have it) + FINVIZ + SEC EDGAR

| Source | What | Cost |
|--------|------|------|
| Yahoo Finance RSS | Headlines | Free (have it) |
| FINVIZ | Analyst ratings, price targets | Free (scrape) |
| SEC EDGAR | 8-K filings, insider Form 4 | Free API |
| Reddit/StockTwits | Retail sentiment | Free API |

**Tool: `get_sentiment(ticker)`**
```python
# Aggregates:
# - News sentiment score (-1 to +1)
# - Analyst consensus (buy/hold/sell count)
# - Average price target vs current
# - Insider buying/selling (Form 4)
# - Social sentiment trend
```

### 2E. Technical Indicators (FREE via yfinance)
**Tool: `get_technicals(ticker)`**
```python
# Key levels:
# - RSI (14-day)
# - MACD signal
# - 50/200 SMA (golden/death cross)
# - Bollinger Band position
# - Volume trend (above/below average)
# - Support/resistance levels
# - Overall signal: bullish/bearish/neutral
```

---

## Full Command System — On-Demand + Proactive Alerts

### Design Principle
Every piece of intelligence works TWO ways:
1. **On-demand** — you ask for it via Telegram command, get instant response
2. **Proactive** — scanners detect it and push an alert to you automatically

Same data, same math functions, two delivery modes.

---

### Command Categories

#### PORTFOLIO — Your Positions (Direct path, no Claude, $0)

| Command | What It Does | Example Response |
|---------|-------------|-----------------|
| `/pnl` | Live P&L table for all positions | Ticker/Shares/Cost/Price/$PnL/%PnL table + totals |
| `/pnl AMZN` | P&L for a single position | AMZN: 100 shares, cost $250 → $198.50, -$5,150 (-20.6%) |
| `/portfolio` | All positions (shares + options) | Full position list with status |
| `/put` | Analyze all open puts: Greeks, DTE, roll/hold/close | Strike vs price, delta, theta, extrinsic, recommendation |
| `/options` | Analyze ALL open options (puts + calls) | Same as /put but includes covered calls too |
| `/update sold 50 AMZN at 195` | Record a trade | Parses via regex, updates DynamoDB, confirms |
| `/history` | Recent trade log | Last 20 trades from DynamoDB |

#### RESEARCH — Deep Dive on a Ticker (Direct path, no Claude, $0)

| Command | What It Does | Data Source |
|---------|-------------|------------|
| `/news AMZN` | Top 5 headlines + links | Yahoo RSS |
| `/flow AMZN` | Unusual options activity scan | yfinance: volume vs OI, put/call ratio, premium flow |
| `/technicals AMZN` | Key levels: RSI, MACD, SMA, Bollinger, volume | yfinance price history + math |
| `/darkpool AMZN` | Dark pool % + short volume + trend | FINRA data |
| `/congress AMZN` | Congressional trades on this ticker | Capitol Trades / DynamoDB |
| `/earnings AMZN` | Next earnings date + days away | yfinance |

#### INTEL — Cross-Cutting Intelligence (Direct path, no Claude, $0)

| Command | What It Does | Example |
|---------|-------------|---------|
| `/congress` (no ticker) | All recent congressional trades, ranked by signal | Cluster alerts first, then large trades, then all |
| `/flow` (no ticker) | Unusual activity across ALL held + watchlist tickers | "3 tickers flagged: AMZN (10x OI calls), AMD..." |
| `/darkpool` (no ticker) | Dark pool flags across portfolio + watchlist | "AMD: 47% off-exchange (up from 32% last week)" |
| `/movers` | Biggest movers in your portfolio today | "AMD +4.2%, AMZN -1.8%, QQQ +0.3%" |
| `/sector` | What sectors is Congress trading? Heatmap data | "Tech: 42% of trades, Defense: 18%, ..." |

#### SYNTHESIS — AI-Powered (Claude, ~$0.01-0.04 per call)

| Command | What It Does | Why Claude Needed |
|---------|-------------|-------------------|
| `/brief` | Full morning intelligence brief | Synthesizes all data into priorities + recommendations |
| `/catalyst AMZN` | Upcoming catalysts + impact analysis | Reasoning about earnings, events, macro, position impact |
| `/risk` | Full portfolio risk scan + recommendations | Judgment on what risks are real vs noise |
| `/analyze AMZN` | Complete picture: price + flow + congress + darkpool + technicals + news | Cross-referencing multiple signals into a thesis |
| `/ask [anything]` | Free-form question | "Should I roll my AMD call?", "Why is SPY dropping?" |

#### WATCHLIST & CONFIG (Direct path, no Claude, $0)

| Command | What It Does |
|---------|-------------|
| `/watch NVDA TSLA` | Add tickers to watchlist (scanned by all scanners, no P&L) |
| `/unwatch TSLA` | Remove from watchlist |
| `/watchlist` | Show all watched tickers |
| `/alerts` | Show alert config (what's on, what's off) |
| `/alerts on` / `/alerts off` | Enable/disable all alerts |
| `/alerts mute 2h` | Snooze alerts for 2 hours |
| `/threshold AMZN above 200` | Set a price alert |
| `/threshold AMZN below 180` | Set a price floor alert |
| `/help` | Show all commands grouped by category |
| `/help [command]` | Detailed help for a specific command |

---

### How `/brief` Works (The Supercharged Morning Brief)

`/brief` is the flagship command. It gathers ALL data via code ($0), then feeds a compact summary to Claude for synthesis (~$0.02).

```
You: /brief

Bot:

MORNING BRIEF — Apr 10, 2026 (Pre-Market)
==========================================

PORTFOLIO P&L
| Ticker | Shares | Cost    | Price   | $ P&L     | % P&L  |
|--------|--------|---------|---------|-----------|--------|
| AMZN   | 100    | $250.00 | $198.50 | -$5,150   | -20.6% |  <-- flagged
| AMD    | 200    | $222.50 | $165.30 | -$11,440  | -25.7% |  <-- flagged
| SPY    | 18     | $445.00 | $502.10 | +$1,027   | +12.8% |
| QQQ    | 20     | $385.00 | $421.50 | +$730     | +9.5%  |
Total: -$14,833 (-14.1%)

OPTIONS
| Ticker | Type | Strike | Expiry   | DTE | Delta | Status        |
|--------|------|--------|----------|-----|-------|---------------|
| AMD    | Call | $250   | May 15   | 35  | 0.12  | OTM, safe     |

URGENT FLAGS
• AMZN down 20.6% from cost — review position
• AMD down 25.7% from cost — review position
• AMD earnings in 18 days (Apr 28)

UNUSUAL OPTIONS ACTIVITY
• AMZN: $200 calls showing 8x normal volume (12,400 vs 1,500 OI)
• AMD: Put/call ratio spiked to 2.1 (bearish)

CONGRESS (Last 48h)
• No trades on your tickers
• Cluster alert: 3 members bought NVDA (not held — /watch NVDA?)

DARK POOL
• AMD: 44% off-exchange (above 40% threshold, up from 35%)

NEWS
• AMZN: "Amazon Web Services announces new AI chip partnership"
• AMD: "AMD cuts Q2 guidance amid China export restrictions"

TECHNICALS
• AMZN: RSI 38 (approaching oversold), below 200-SMA
• AMD: RSI 29 (oversold), MACD bearish crossover

AI RECOMMENDATIONS (Claude)
1. AMD is showing multiple bearish signals (dark pool spike, high
   put/call, oversold RSI, guidance cut). Your covered call at $250
   is safe (deep OTM) but consider trimming shares if earnings
   confirms the weakness. Watch Apr 28 closely.
2. AMZN at RSI 38 with unusual call buying could signal a bottom.
   The AI chip news is a potential catalyst. Hold — don't add yet.
3. Consider /watch NVDA — 3 Congress members bought this week.
```

**Cost breakdown of `/brief`:**
- Portfolio P&L: yfinance batch + math → $0.00
- Options Greeks: Black-Scholes math → $0.00
- Urgent flags: threshold checks → $0.00
- Options flow: yfinance chains + volume math → $0.00
- Congress: DynamoDB query + cluster detection → $0.00
- Dark pool: FINRA data + % calc → $0.00
- News: Yahoo RSS fetch → $0.00
- Technicals: price history + RSI/MACD math → $0.00
- **AI Recommendations only**: Claude Sonnet, ~4K input (compact data summary), ~500 output → **~$0.02**

---

### How `/catalyst` Works (Enhanced)

```
You: /catalyst AMZN

Bot:

CATALYSTS — AMZN
================

EARNINGS
• Next: May 1, 2026 (21 days away)
• Consensus: EPS $1.12 | Revenue $155.2B
• Last quarter: Beat by 8% (EPS $1.21 vs $1.12 est)

UPCOMING EVENTS
• Apr 15: AWS Summit (potential product announcements)
• Apr 22: Fed rate decision (macro impact)
• May 1: Q1 earnings report

OPTIONS ACTIVITY (unusual)
• $200 calls May expiry: 8x volume (bullish positioning)
• $180 puts May expiry: 3x volume (hedging?)
• Net premium flow: +$4.2M bullish

CONGRESS
• No recent trades on AMZN
• Last trade: Sen. Tuberville sold $100K-250K (3 months ago)

DARK POOL
• 38% off-exchange (normal range)
• Short volume ratio: 42% (slightly elevated)

TECHNICALS
• RSI: 38 (approaching oversold)
• MACD: Bearish but flattening (possible reversal)
• Below 200-SMA ($215) — needs to reclaim for bullish
• Support: $192 | Resistance: $210

AI ANALYSIS (Claude)
The unusual bullish call activity ahead of earnings is notable.
Smart money may be positioning for a beat. However, RSI and MACD
are still bearish — wait for a reclaim of $210 before adding.
The AWS Summit on Apr 15 could be the near-term catalyst.
Watch for AI chip partnership details.
```

**Cost: ~$0.02** (only the AI Analysis paragraph uses Claude)

---

### How `/risk` Works (Enhanced)

```
You: /risk

Bot:

PORTFOLIO RISK SCAN
===================

POSITION RISK
| Ticker | Issue                              | Severity |
|--------|------------------------------------|----------|
| AMD    | Down 25.7% from cost basis         | HIGH     |
| AMD    | Earnings in 18 days (Apr 28)       | HIGH     |
| AMD    | Dark pool 44% (elevated)           | MEDIUM   |
| AMD    | Put/call ratio 2.1 (bearish)       | MEDIUM   |
| AMD    | RSI 29 (oversold)                  | LOW      |
| AMZN   | Down 20.6% from cost basis         | HIGH     |
| AMZN   | Below 200-SMA                      | MEDIUM   |

OPTIONS RISK
| Ticker | Type | Strike | DTE | Risk                         |
|--------|------|--------|-----|------------------------------|
| AMD    | Call | $250   | 35  | Low — deep OTM, safe         |

CONCENTRATION
• AMD: 38% of portfolio (overweight)
• Single sector (tech): 100%

MACRO
• Fed decision Apr 22 (12 days)
• VIX: 22.5 (elevated)

AI RISK ASSESSMENT (Claude)
AMD is your biggest risk: 38% of portfolio, down 26%, earnings
in 18 days, and bearish signals everywhere (dark pool, put/call,
RSI, guidance cut). Consider:
1. Trim 50 shares before earnings to reduce concentration
2. Your $250 covered call is safe — let theta work
3. Set a stop-loss alert: /threshold AMD below 155
```

---

### How `/help` Works

`/help` shows a clean grouped summary. `/help [command]` gives detailed usage for one command.

```
You: /help

Bot:

📋 STOCK ASSISTANT — COMMANDS
==============================

PORTFOLIO
  /pnl [TICKER]          Live P&L (all positions or one)
  /portfolio              All positions with status
  /options                Analyze all open options (Greeks, DTE, rec)
  /put                    Analyze open puts specifically
  /update [trade]         Record a trade ("sold 50 AMZN at 195")
  /history                Recent trade log

RESEARCH (per ticker)
  /news TICKER            Top headlines
  /flow TICKER            Unusual options activity
  /technicals TICKER      RSI, MACD, SMA, Bollinger, support/resistance
  /darkpool TICKER        Dark pool volume % + short volume
  /congress TICKER        Congressional trades on this ticker
  /earnings TICKER        Next earnings date + countdown

INTELLIGENCE (cross-portfolio)
  /flow                   Unusual options across all held + watched
  /congress               All recent congressional trades + clusters
  /darkpool               Dark pool flags across portfolio
  /movers                 Biggest portfolio movers today
  /sector                 Congress trading by sector
  /top congress           Most-traded tickers by Congress
  /top flow               Top unusual options activity
  /scan TICKER            Run ALL checks on one ticker
  /compare TICKER TICKER  Side-by-side comparison

AI-POWERED (uses Claude for analysis)
  /brief                  Full morning intelligence brief
  /catalyst TICKER        Upcoming catalysts + impact analysis
  /risk                   Portfolio risk scan + recommendations
  /analyze TICKER         Complete picture + investment thesis
  /ask [question]         Ask anything ("Should I roll my put?")

WATCHLIST & ALERTS
  /watch TICKER [TICKER]  Add to watchlist
  /unwatch TICKER         Remove from watchlist
  /watchlist              Show watched tickers
  /alerts                 Show alert config
  /alerts on/off          Enable/disable alerts
  /alerts mute 2h         Snooze alerts
  /threshold TICKER above/below PRICE   Set price alert
  /threshold clear TICKER               Remove price alert

Tip: Most commands work with or without a ticker.
  /flow        → scan all held + watchlist
  /flow AMZN   → scan AMZN only
```

```
You: /help brief

Bot:

/brief — Morning Intelligence Brief
====================================

Gathers ALL data sources and delivers a full market
intelligence report with AI-powered recommendations.

Sections:
  1. Portfolio P&L table
  2. Open options with Greeks
  3. Urgent flags (drawdowns, expiring options, earnings)
  4. Unusual options activity
  5. Congressional trades (last 48h)
  6. Dark pool signals
  7. News headlines
  8. Technical levels
  9. AI Recommendations (Claude)

Sections 1-8 are pure data (instant, $0).
Section 9 uses Claude for synthesis (~$0.02).

Usage: /brief
Frequency: Best used once in the morning, pre-market.

Related: /risk (focused on risk), /catalyst TICKER (one ticker deep-dive)
```

```
You: /help flow

Bot:

/flow — Unusual Options Activity
=================================

Scans options chains for unusual volume, premium
concentration, and put/call imbalances.

Flags:
  • Volume > 5x open interest (unusual)
  • Single-strike premium > $500K (large bet)
  • Put/call ratio > 1.5 or < 0.5 (extreme)
  • Net premium flow direction (bullish/bearish)

Usage:
  /flow           Scan ALL held + watchlist tickers
  /flow AMZN      Scan AMZN only

Output includes:
  • Top 5 most unusual contracts
  • Put/call ratio
  • Net premium flow ($ bullish vs bearish)
  • Classification: sweep, block, hedge

Data source: yfinance options chains (free, real-time)
Cost: $0 (pure math, no AI)

Related: /scan TICKER (all checks), /analyze TICKER (AI thesis)
```

The help system is implemented as a static dictionary — zero cost, instant response:

```python
# bot/help.py

HELP_MAIN = """📋 STOCK ASSISTANT — COMMANDS
==============================
...
"""

HELP_DETAIL = {
    "pnl": "...",
    "brief": "...",
    "flow": "...",
    "congress": "...",
    # ... one entry per command
}

def handle_help(text):
    parts = text.strip().split(None, 1)
    if len(parts) > 1:
        cmd = parts[1].lstrip("/").lower()
        return HELP_DETAIL.get(cmd, f"Unknown command: {cmd}. Try /help")
    return HELP_MAIN
```

---

## Phase 3: Proactive Alert System
> These fire AUTOMATICALLY — you don't ask for them

### Alert Pipeline
```
EventBridge (cron) → Scanner Lambda → Evaluate thresholds → SQS → Alert Lambda → Telegram
```

All scanners use the same math functions as on-demand commands. No Claude needed.

### Scanner Schedule

| Scanner | Runs | When | What It Checks |
|---------|------|------|---------------|
| `price_scanner` | Every 5 min | Market hours | Price thresholds, big moves (>3% intraday) |
| `options_scanner` | Every 30 min | Market hours | Volume vs OI anomalies on held + watchlist tickers |
| `risk_scanner` | Every 1 hour | Market hours | DTE on options, drawdown thresholds, earnings proximity |
| `congress_scanner` | Every 6 hours | Always | New filings, cluster detection |
| `darkpool_scanner` | Daily 5PM ET | After close | FINRA data (T+1), off-exchange % spikes |
| `technicals_scanner` | Every 1 hour | Market hours | RSI extremes, MACD crosses, SMA crosses |
| `news_scanner` | Every 30 min | Always | New headlines on held + watchlist tickers |
| `earnings_scanner` | Daily 8AM ET | Pre-market | Earnings countdown (flag at 14d, 7d, 3d, 1d) |

### Alert Priority & Formatting

**RED — Immediate action needed:**
```
🔴 AMD DOWN 5.2% TODAY ($156.30)
Your position: 200 shares, now -28.4% from cost
Dark pool: 44% | RSI: 26 (oversold)
→ /analyze AMD for full picture
```

```
🔴 OPTIONS EXPIRY: AMD $250 Call
DTE: 3 | Delta: 0.08 | Extrinsic: $0.12
Recommendation: Let expire worthless (deep OTM)
→ [Let Expire] [Close Early $0.05]
```

**YELLOW — Noteworthy, review when convenient:**
```
🟡 UNUSUAL FLOW: AMZN $200 Calls
Volume: 12,400 (8.3x OI) | Premium: $1.8M
Expiry: May 15 | Direction: Bullish sweep
You hold: 100 shares | → /flow AMZN
```

```
🟡 CONGRESS: 3 members bought NVDA this week
Pelosi (D) $1M-5M | Tuberville (R) $250K-500K | Ossoff (D) $100K-250K
You hold: No | → /watch NVDA
→ [Watch NVDA] [Ignore]
```

```
🟡 EARNINGS ALERT: AMD reports in 7 days (Apr 28)
You hold: 200 shares + 2 covered calls
Last quarter: Beat by 8% | Consensus: EPS $0.78
→ /catalyst AMD
```

**BLUE — Informational:**
```
🔵 TECHNICAL: AMZN RSI hit 30 (oversold)
Price: $192.40 | 200-SMA: $215 | Support: $188
Below 200-SMA but approaching oversold bounce zone
→ /technicals AMZN
```

```
🔵 DARK POOL: AMD off-exchange volume hit 47%
14-day avg: 35% | Today: 47% | Trend: Rising
Short volume ratio: 51%
→ /darkpool AMD
```

### Inline Keyboard Actions

Every alert includes quick-action buttons:

```
🔴 AMD DOWN 5.2% TODAY ($156.30)
...
[Analyze] [Set Stop-Loss] [Trim Position] [Dismiss]
```

```
🟡 CONGRESS: 3 members bought NVDA
...
[Watch NVDA] [Analyze NVDA] [Ignore]
```

```
🟡 UNUSUAL FLOW: AMZN $200 Calls
...
[Full Flow] [Analyze] [Watch Chain] [Dismiss]
```

Tapping a button sends the corresponding command — no typing needed.

### Alert Config

```
/alerts                    — show current config
/alerts on                 — enable all
/alerts off                — disable all
/alerts mute 2h            — snooze for 2 hours
/alerts red only           — only urgent alerts
/alerts [type] on/off      — toggle specific type:
  /alerts congress on
  /alerts flow off
  /alerts darkpool on
  /alerts technicals off
  /alerts earnings on
  /alerts price on
/threshold AMZN above 210  — custom price alert
/threshold AMD below 155   — custom price floor
/threshold clear AMZN      — remove price alerts for ticker
```

### Deduplication & Rate Limiting

Alerts are throttled to avoid spam:
- Same alert type + ticker: max once per 4 hours
- Total alerts per day: soft cap at 20 (overflow goes to `/alerts history`)
- During market close: only congress, news, earnings countdown
- Mute respects snooze timer exactly

---

## Phase 4: Analytics Dashboard (S3 Static Site)
> Visual complement to Telegram — same data, chart format

Dashboard auto-updates via Lambda writing JSON to S3 after each scanner run.

### Dashboard Pages

| Page | What It Shows |
|------|--------------|
| **Portfolio** | P&L table, allocation pie chart, performance line chart (Lightweight Charts) |
| **Congress** | Cluster alerts, recent trades table (AG Grid), sector heatmap, member scorecards |
| **Options Flow** | Unusual activity table, put/call ratio chart, premium flow bar chart |
| **Dark Pool** | Off-exchange % per ticker (bar chart), short volume trend (line chart) |
| **Technicals** | RSI/MACD gauges per ticker, SMA overlays on price charts |
| **Alerts** | Alert history log, alert stats (how many per type per week) |

---

## Phase 5: Polish & Power Features

### Smart Combinations (On-Demand)
```
You: /scan NVDA           — run ALL checks on a ticker (flow + congress + dark pool +
                            technicals + news + earnings) — pure code, $0

You: /compare AMD NVDA    — side-by-side comparison table — pure code, $0

You: /top congress         — top 5 most-traded tickers by Congress this month — $0

You: /top flow             — top 5 unusual options activity today — $0

You: "Should I buy NVDA?"  — free-form → Claude with all data context — ~$0.03
```

### Watchlist Intelligence
Watchlist tickers get the SAME scanning as held positions:
- Options flow anomalies
- Congressional trades
- Dark pool spikes
- Earnings proximity
- Technical signals
- News headlines

The difference: they don't appear in P&L. They appear in alerts and `/brief`.

### Multi-User (Optional)
- Each Telegram chat_id gets its own DynamoDB partition key
- Separate portfolio, watchlist, alert config per user
- Shared data (congress trades, dark pool) is global — fetched once

---

## Implementation Order

### Sprint 1: Foundation + Core Commands
1. [ ] Terraform config (Lambda + API Gateway + DynamoDB + S3 + EventBridge + SQS)
2. [ ] Telegram bot handler (webhook, two-path command router)
3. [ ] Math library: P&L calc, Black-Scholes Greeks, RSI, MACD, SMA, Bollinger
4. [ ] DynamoDB: portfolio table, watchlist table, alerts config table
5. [ ] Direct commands: `/pnl`, `/portfolio`, `/options`, `/update`, `/help`
6. [ ] Direct commands: `/news`, `/earnings`
7. [ ] Deploy — basic bot works from your phone

### Sprint 2: Intelligence Tools (All Direct Path, $0)
8. [ ] `/flow` — options flow scanner (yfinance chains + volume math)
9. [ ] `/technicals` — RSI, MACD, SMA, Bollinger, support/resistance
10. [ ] `/congress` — Capitol Trades scraper + DynamoDB + cluster detection
11. [ ] `/darkpool` — FINRA short volume data + trend calc
12. [ ] `/scan TICKER` — run all checks on one ticker
13. [ ] `/movers`, `/top congress`, `/top flow`
14. [ ] S3 dashboard v1 (portfolio + congress pages)

### Sprint 3: AI Commands + Alerts
15. [ ] `/brief` — gather all data (code), synthesize (Claude)
16. [ ] `/catalyst` — data gathering (code) + analysis (Claude)
17. [ ] `/risk` — threshold scan (code) + assessment (Claude)
18. [ ] `/analyze` — full picture (code) + thesis (Claude)
19. [ ] Free-form `/ask` — Claude agent with all tools available
20. [ ] Alert scanners (EventBridge → Lambda → SQS → Telegram)
21. [ ] Alert config commands: `/alerts`, `/threshold`, `/watch`, `/unwatch`
22. [ ] Inline keyboard buttons on alerts

### Sprint 4: Dashboard + Polish
23. [ ] S3 dashboard: options flow, dark pool, technicals pages
24. [ ] Alert history page
25. [ ] `/compare`, `/history`
26. [ ] Deduplication + rate limiting on alerts
27. [ ] Performance tracking (snapshot history → portfolio chart)

---

## Cost Analysis — Full Breakdown

### AWS Free Tier Reality Check

Not all free tiers are equal. Some are **always free** (forever), some expire after **12 months**.

| Service | Free Tier Type | Free Limits |
|---------|---------------|-------------|
| Lambda | **Always free** | 1M requests + 400K GB-sec/month |
| DynamoDB (provisioned) | **Always free** | 25 RCU/WCU + 25 GB storage |
| CloudFront | **Always free** | 1 TB transfer + 10M requests/month |
| SQS | **Always free** | 1M requests/month |
| CloudWatch Logs | **Always free** | 5 GB ingestion + 5 GB storage/month |
| EventBridge Scheduler | **Always free** | 14M invocations/month |
| API Gateway | **12-month only** | 1M calls/month (then $1/M for HTTP API) |
| S3 | **12-month only** | 5 GB + 20K GET/month (then $0.023/GB) |

**After year 1**, API Gateway and S3 start charging — but at our volume it's pennies.

---

### Usage Estimates (Your Actual Workload)

#### Telegram Bot Interactions (API Gateway + Lambda)
| Activity | Frequency | Monthly Requests |
|----------|-----------|-----------------|
| You sending commands (/pnl, /brief, /news, etc.) | ~15/day | ~450 |
| Agent multi-turn (avg 3 tool calls per command) | 3x per command | ~1,350 |
| **Total bot requests** | | **~1,800** |

#### Scheduled Scanners (EventBridge + Lambda)
| Scanner | Frequency | Monthly Invocations |
|---------|-----------|-------------------|
| Congress trade scan | Every 6 hours | 120 |
| Options flow scan (market hours only, 6.5h/day) | Every 30 min | ~286 |
| Dark pool scan | Daily after close | 22 |
| Price alert scan (market hours) | Every 5 min | ~1,716 |
| Earnings proximity scan | Daily | 22 |
| Dashboard JSON generator | After each scan | ~2,166 |
| **Total scanner invocations** | | **~4,332** |

#### DynamoDB Operations
| Operation | Frequency | Monthly |
|-----------|-----------|---------|
| Portfolio reads (per command) | ~15/day | ~450 reads |
| Congress trade writes (new filings) | ~200 trades/month across all Congress | ~200 writes |
| Alert config reads/writes | Occasional | ~50 |
| Watchlist reads | Per scan | ~4,332 reads |
| **Total** | | **~5,000 reads, ~300 writes** |

#### S3 Operations
| Operation | Frequency | Monthly |
|-----------|-----------|---------|
| Dashboard JSON writes (per scan) | ~4,332/month | ~4,332 PUTs |
| Dashboard page loads (you checking it) | ~10/day | ~300 GETs |
| Historical data writes | Per trade/snapshot | ~500 PUTs |
| Raw data storage | Growing ~5 MB/month | <1 GB total/year |

#### CloudFront (Dashboard)
| Metric | Monthly |
|--------|---------|
| Page loads | ~300 |
| Auto-refresh JSON fetches (30s interval, ~1hr/day viewing) | ~3,600 |
| Total requests | ~4,000 |
| Data transfer | ~50 MB |

---

### Cost Calculation: Year 1 (Free Tier Active)

| Service | Usage | Free Tier Covers? | Monthly Cost |
|---------|-------|-------------------|-------------|
| **Lambda** | ~6,100 invocations, 128MB, avg 500ms | Yes (1M free) | **$0.00** |
| **API Gateway (HTTP)** | ~1,800 requests | Yes (1M free, 12mo) | **$0.00** |
| **DynamoDB** | ~5K reads, ~300 writes, <1 GB | Yes (25 RCU/WCU free) | **$0.00** |
| **S3** | <1 GB storage, ~5K requests | Yes (5 GB + 20K free, 12mo) | **$0.00** |
| **CloudFront** | Not used | Skipped — unnecessary for single user | **$0.00** |
| **EventBridge** | ~4,300 scheduled invocations | Yes (14M free) | **$0.00** |
| **SQS** | ~500 alert messages | Yes (1M free) | **$0.00** |
| **CloudWatch** | ~100 MB logs | Yes (5 GB free) | **$0.00** |
| **AWS Subtotal** | | | **$0.00** |
| | | | |
| **Claude API (Sonnet)** | AI path only (~82 calls) | N/A | **$1-3** |
| **Data Sources** | yfinance, Capitol Trades, FINRA, SEC | All free | **$0.00** |
| **Telegram Bot API** | | Free forever | **$0.00** |
| | | | |
| **TOTAL YEAR 1** | | | **$1-3/month** |

---

### Cost Calculation: After Year 1 (Free Tier Expired for Some)

| Service | Usage | Monthly Cost |
|---------|-------|-------------|
| **Lambda** | ~6,100 invocations | **$0.00** (always free covers this) |
| **API Gateway (HTTP)** | ~1,800 requests | **$0.002** ($1.00/M requests) |
| **DynamoDB** | ~5K reads, ~300 writes | **$0.00** (always free covers this with provisioned mode) |
| **S3** | <1 GB + ~5K requests | **$0.03** ($0.023/GB + $0.005/1K PUTs) |
| **CloudFront** | Not used | **$0.00** |
| **EventBridge** | ~4,300 invocations | **$0.00** (always free covers this) |
| **SQS** | ~500 messages | **$0.00** (always free covers this) |
| **CloudWatch** | ~100 MB logs | **$0.00** (always free covers this) |
| **AWS Subtotal** | | **$0.03/month** |
| | | |
| **Claude API** | | **$1-3/month** |
| | | |
| **TOTAL AFTER YEAR 1** | | **$1-3/month** |

**AWS infrastructure is effectively free.** Even after year 1, you're paying 3 cents.

---

### Claude API Cost — Smart Routing (Most Commands Skip Claude Entirely)

**Key insight: 80% of commands are data fetch + format. No LLM needed.**

The bot handler routes commands into two paths:
1. **Direct path** (no Claude) — Lambda fetches data, formats response, sends to Telegram
2. **AI path** (Claude) — only for reasoning, synthesis, or free-form questions

#### What SKIPS Claude (pure code, $0.00)

| Command | What Code Does | Claude Needed? |
|---------|---------------|:-:|
| `/pnl` | yfinance prices → P&L math → format table | **No** |
| `/news AMZN` | RSS fetch → format headlines | **No** |
| `/flow AMZN` | yfinance chains → volume vs OI thresholds → format | **No** |
| `/congress` | DynamoDB query → cluster detection → format table | **No** |
| `/darkpool AMD` | FINRA data → % calc → trend → format | **No** |
| `/technicals AMD` | Price history → RSI/MACD/SMA math → format | **No** |
| `/risk` | Portfolio scan → threshold checks → flag list | **No** |
| `/watch NVDA` | DynamoDB write | **No** |
| `/alerts config` | DynamoDB read → format | **No** |
| `/update sold 50 AMZN at 195` | Regex parse → DynamoDB write | **No** |
| All scanner alerts | Threshold triggers → template message | **No** |
| Dashboard data generation | Aggregation + JSON write to S3 | **No** |

#### What USES Claude (AI reasoning required)

| Command | Why Claude Is Needed | Frequency |
|---------|---------------------|-----------|
| `/brief` | Synthesize all data into prioritized morning summary | ~1/day |
| `/analyze AMZN` | Cross-reference flow + congress + dark pool + technicals into a thesis | ~5/week |
| "What should I do with my AMD put?" | Weigh Greeks, DTE, earnings, IV → recommendation | ~3/week |
| "Why is Congress buying defense?" | Pattern recognition across trades + context | ~2/week |
| "Compare AMD vs NVDA setup" | Multi-factor comparison requiring judgment | ~2/week |
| Any free-form question | Natural language → reasoning | ~5/week |

#### Revised Claude Cost (Sonnet 4: $3/M input, $15/M output)

| AI Interaction | Input Tok | Output Tok | Cost/Call | Monthly Calls | Monthly Cost |
|---------------|----------|-----------|----------|---------------|-------------|
| `/brief` (morning synthesis) | ~4,000 | ~1,500 | ~$0.035 | 30 | $1.04 |
| `/analyze TICKER` (deep dive) | ~5,000 | ~1,500 | ~$0.038 | 20 | $0.75 |
| Options strategy questions | ~3,000 | ~1,000 | ~$0.024 | 12 | $0.29 |
| Free-form reasoning | ~2,500 | ~800 | ~$0.020 | 20 | $0.39 |
| **Total** | | | | **~82 calls** | **~$2.47** |

#### Further Optimization

| Technique | Savings |
|-----------|---------|
| Use **Haiku** for `/brief` (it's mostly formatting the synthesis) | -$0.70/mo |
| **Prompt caching** on system prompt (90% cheaper on cache hit) | -$0.30/mo |
| Skip Claude on `/brief` too — use templates + code for 80% of briefs, only call Claude for the "recommendations" section | -$0.50/mo |
| **Optimized total** | **~$1.00/month** |

#### Architecture: Two-Path Command Router

```python
# bot/commands.py — the router

DIRECT_COMMANDS = {
    "/pnl": handle_pnl,           # Pure code: yfinance → math → format
    "/news": handle_news,          # Pure code: RSS → format
    "/flow": handle_flow,          # Pure code: yfinance → thresholds → format
    "/congress": handle_congress,  # Pure code: DynamoDB → cluster detect → format
    "/darkpool": handle_darkpool,  # Pure code: FINRA → calc → format
    "/technicals": handle_technicals,  # Pure code: price math → format
    "/risk": handle_risk,          # Pure code: threshold scan → format
    "/watch": handle_watch,        # Pure code: DynamoDB write
    "/unwatch": handle_unwatch,    # Pure code: DynamoDB delete
    "/alerts": handle_alerts,      # Pure code: DynamoDB CRUD
    "/update": handle_update,      # Regex parse → DynamoDB write
    "/watchlist": handle_watchlist, # Pure code: DynamoDB read → format
    "/help": handle_help,          # Static text
}

AI_COMMANDS = {
    "/brief": handle_brief,        # Gather all data via code, then Claude synthesizes
    "/analyze": handle_analyze,    # Gather data via code, then Claude reasons
}

def route_command(text):
    cmd = text.split()[0].lower()
    if cmd in DIRECT_COMMANDS:
        return DIRECT_COMMANDS[cmd](text)  # No Claude, instant, $0
    if cmd in AI_COMMANDS:
        return AI_COMMANDS[cmd](text)      # Code gathers data, Claude reasons
    # Free-form text → Claude agent with tools
    return handle_freeform(text)           # Full agent loop
```

#### The `/brief` Hybrid Pattern (Mostly Code, Tiny Claude Call)

```python
def handle_brief(text):
    # Step 1: ALL data gathering is pure code ($0)
    pnl = get_pnl_data()           # yfinance → math
    risks = scan_risks()            # threshold checks
    news = fetch_news()             # RSS
    congress = get_recent_congress() # DynamoDB
    flow = scan_unusual_flow()      # yfinance → thresholds
    darkpool = get_darkpool_flags() # FINRA
    
    # Step 2: Format 80% as templates ($0)
    sections = format_pnl_table(pnl) + format_risk_flags(risks) + ...
    
    # Step 3: ONLY call Claude for the recommendation paragraph (~$0.01)
    recommendations = claude_sonnet(
        f"Given this portfolio data, give 3 actionable recommendations:\n{json.dumps(summary)}"
    )
    
    return sections + "\n\n**Recommendations:**\n" + recommendations
```

---

### Cost Comparison: You vs Unusual Whales

| Feature | Unusual Whales | Your Platform |
|---------|---------------|--------------|
| Congressional trades | ✅ | ✅ (same data, free sources) |
| Options flow | ✅ | ✅ (yfinance + anomaly detection) |
| Dark pool data | ✅ | ✅ (FINRA, free) |
| Alerts | ✅ | ✅ (Telegram push) |
| AI analysis | ❌ | ✅ (Claude explains everything) |
| Custom portfolio tracking | Basic | ✅ (full P&L, Greeks, recommendations) |
| Dashboard | Web app | ✅ (S3 static, mobile-friendly) |
| Conversational queries | ❌ | ✅ (ask anything via Telegram) |
| **Monthly cost** | **$30-50/month** | **$1-3/month** |
| **Annual cost** | **$360-600/year** | **$12-36/year** |

**You save $320-590/year** and get AI analysis that Unusual Whales doesn't have.

---

### Scaling Cost (If You Share With Friends)

If 5 people use your bot (multi-user via Telegram chat_id partitioning):

| Item | 1 User | 5 Users |
|------|--------|---------|
| AWS infra | $0.03 | $0.15 |
| Claude API | $1-3 | $5-15 |
| **Total** | **$1-3** | **$5-15** |

Still cheaper than ONE Unusual Whales subscription, and covers 5 people.

---

### The Bottom Line

```
┌──────────────────────────────────────────────┐
│  MONTHLY COST BREAKDOWN                      │
│                                              │
│  AWS Infrastructure:  ~$0.00 (year 1)        │
│                       ~$0.03 (after year 1)  │
│  Claude API:          ~$1-3  (AI path only)  │
│  Data Sources:        $0.00  (all free)      │
│  Telegram:            $0.00  (free forever)  │
│  ─────────────────────────────────────────── │
│  TOTAL:               $1-3/month             │
│                                              │
│  vs Unusual Whales:   $30-50/month           │
│  Your savings:        ~$320-590/year         │
└──────────────────────────────────────────────┘
```

---

## Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| AI Agent | Strands Agents SDK + Claude Sonnet (interactive) / Haiku (scanners) |
| Interface | Telegram Bot API (webhook) |
| Dashboard | S3 static website hosting (Lightweight Charts + Tailwind) |
| Compute | AWS Lambda ARM/Graviton (Python 3.12) |
| API | API Gateway (HTTP API — 3.5x cheaper than REST) |
| Database | DynamoDB (provisioned, always-free tier) |
| Storage | S3 |
| Scheduling | EventBridge Scheduler |
| Queue | SQS |
| Market Data | yfinance (free) |
| Congress | Capitol Trades API (free) |
| Dark Pool | FINRA ADF / Short Volume (free) |
| News | Yahoo RSS + FINVIZ + SEC EDGAR (free) |
| Options | yfinance chains + custom anomaly detection (free) |
| IaC | Terraform (free, cloud-agnostic) |
| Deploy | `terraform plan && terraform apply` |
