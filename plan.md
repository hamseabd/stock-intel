# Investment Workbench — Build Plan

> **Today: Feb 23, 2026** | AMD $230 put expires Feb 27 — 4 DTE, urgent

## What We're Building

A local terminal-based investment analyst. You run `python main.py`, type "brief" or
"what should I do with my put?" and get live data + sharp analysis back instantly.

**Stack: Strands Agents SDK + Claude API + Python tools**

No MCP. No Claude Code. No server process to manage.

---

## Final File Structure

```
/Users/hamseabdi/Desktop/Stocks/
├── main.py                    ← entry point — terminal REPL with Strands Agent
├── tools/
│   ├── __init__.py
│   ├── portfolio.py           ← @tool: get_portfolio, update_portfolio
│   ├── prices.py              ← @tool: get_prices (live P&L via yfinance)
│   ├── options.py             ← @tool: get_options_analysis (Greeks via Black-Scholes)
│   ├── news.py                ← @tool: get_news (Yahoo Finance RSS via feedparser)
│   ├── earnings.py            ← @tool: get_earnings (yfinance, flags 30-day window)
│   └── logger.py              ← append-only history logging (no @tool, called internally)
├── data/
│   ├── portfolio.json         ← source of truth — never edit manually, use update_portfolio
│   ├── snapshots.jsonl        ← P&L snapshot on every run (for performance tracking)
│   └── trades.jsonl           ← log of every trade (buy/sell/option events)
├── prompts/
│   └── system_prompt.md       ← agent persona + behavior rules loaded at startup
├── .env                       ← ANTHROPIC_API_KEY=sk-...  (never commit this)
└── requirements.txt
```

---

## How the Agent Works

```python
# main.py — simplified
from strands import Agent
from strands.models import AnthropicModel
from tools.portfolio import get_portfolio, update_portfolio
from tools.prices import get_prices
from tools.options import get_options_analysis
from tools.news import get_news
from tools.earnings import get_earnings

model = AnthropicModel(model_id="claude-sonnet-4-6")

agent = Agent(
    model=model,
    tools=[get_portfolio, update_portfolio, get_prices,
           get_options_analysis, get_news, get_earnings],
    system_prompt=open("prompts/system_prompt.md").read()
)

while True:
    query = input("\nYou: ").strip()
    if query.lower() in ("exit", "quit"):
        break
    agent(query)
```

Strands handles the full loop: Claude decides which tools to call → calls them →
reads results → responds. You just talk to it.

---

## Initial Portfolio (data/portfolio.json)

```json
{
  "positions": [
    {"position_type": "shares", "ticker": "AMZN", "shares": 100, "cost_basis": 250.00},
    {"position_type": "shares", "ticker": "AMD",  "shares": 100, "cost_basis": 215.00},
    {"position_type": "shares", "ticker": "SPY",  "shares": 18,  "cost_basis": 445.00},
    {"position_type": "shares", "ticker": "QQQ",  "shares": 20,  "cost_basis": 385.00},
    {
      "position_type": "option",
      "ticker": "AMD",
      "option_type": "put",
      "strategy": "cash_secured_put",
      "strike": 230.00,
      "expiry": "2026-02-27",
      "contracts": 1,
      "cost_basis": 0.0,
      "status": "open"
    }
  ]
}
```

**AMD put: 4 DTE as of today. Roll, close early, or let expire?**

---

## Tools Overview

Each tool is a plain Python function decorated with `@tool`.
Strands auto-generates the schema from type hints + docstrings.

| Tool | Inputs | What it returns |
|------|--------|----------------|
| `get_portfolio` | — | All positions from portfolio.json |
| `update_portfolio` | action, ticker, shares, price, position_type, strike, expiry | Updated positions + confirmation |
| `get_prices` | — | Current price, market value, $P&L, %P&L per position |
| `get_options_analysis` | ticker, strike, expiry | bid/ask, IV, intrinsic/extrinsic, delta/theta/gamma, DTE, recommendation |
| `get_news` | ticker | 5 most recent Yahoo Finance headlines + summaries |
| `get_earnings` | — | Next earnings date per ticker, flags within 30 days |

---

## History & Performance Tracking

Two append-only log files in `data/` — one line of JSON per event (JSONL format).

### data/snapshots.jsonl — P&L snapshot on every run
Written automatically by `main.py` at the start of each session after `get_prices()` is called.
One line per run, giving you a time-series of portfolio value you can chart later.

```json
{"ts": "2026-02-23T09:31:00", "total_value": 84230.00, "total_cost": 91750.00, "total_pnl": -7520.00, "total_pct": -8.2, "positions": [{"ticker": "AMZN", "price": 198.5, "pnl": -5150}, ...]}
```

### data/trades.jsonl — trade log
Written by `update_portfolio()` every time a trade is recorded.

```json
{"ts": "2026-02-23T10:15:00", "action": "sell", "ticker": "AMZN", "shares": 10, "price": 195.0, "pnl_on_trade": -550.0}
```

### What you can do with this data later
- Chart portfolio value over time (total value per snapshot)
- See P&L per position over time
- Review what you traded and whether the recommendation was right
- Ask the agent: "how has my portfolio done over the last 30 days?" — it reads snapshots.jsonl

### logger.py (not a @tool — called internally)
```python
def log_snapshot(prices: list) -> None:
    """Append a P&L snapshot to data/snapshots.jsonl."""

def log_trade(action, ticker, shares, price, pnl=None) -> None:
    """Append a trade event to data/trades.jsonl."""
```

---

## Dependencies

```
strands-agents     # agent loop + tool calling
yfinance>=0.2.50   # prices, options chains, earnings
feedparser>=6.0.0  # Yahoo Finance RSS
scipy>=1.11.0      # Black-Scholes Greeks
numpy>=1.24.0      # array math for Greeks
python-dotenv      # load ANTHROPIC_API_KEY from .env
```

---

## Setup (one time)

```bash
cd /Users/hamseabdi/Desktop/Stocks
python3 -m venv .venv
source .venv/bin/activate
pip install strands-agents yfinance feedparser scipy numpy python-dotenv
echo "ANTHROPIC_API_KEY=your-key-here" > .env
python main.py
```

---

## Verification Checklist

- [ ] `python main.py` starts with no errors
- [ ] Type `portfolio` → lists all 5 positions
- [ ] Type `pnl` → live prices + P&L for each position
- [ ] Type `put` → AMD options analysis with Greeks and roll/hold/close recommendation
- [ ] Type `brief` → full morning brief (all tools called)
- [ ] Type `sold 10 AMZN at 195` → portfolio updates, P&L on the trade confirmed
- [ ] Type `news AMZN` → recent AMZN headlines
- [ ] Type `earnings` → upcoming dates for all tickers
- [ ] Check `data/snapshots.jsonl` — should have 1 line after first run
- [ ] Check `data/trades.jsonl` — should have 1 line after the test sell above
- [ ] Type `how has my portfolio changed since I started?` → agent reads snapshots and reports

---

> See `decisions.md` for the full reasoning behind every choice made here.
