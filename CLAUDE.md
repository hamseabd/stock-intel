# Investment Workbench — Claude.md

## What This Is

A local terminal-based investment analyst. Run `python main.py` to start. The agent uses Claude (via Anthropic API) + Strands Agents SDK to call live data tools and manage a real portfolio.

## Setup

```bash
# Requires Python 3.10+
python3.12 -m venv .venv
source .venv/bin/activate
pip install strands-agents anthropic yfinance feedparser scipy numpy python-dotenv

# Add API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

python main.py
```

## File Structure

```
main.py                    — REPL, slash command expansion, agent initialization
tools/
  portfolio.py             — get_portfolio, update_portfolio
  prices.py                — get_prices (yfinance batch, P&L calc)
  options.py               — get_options_analysis (yfinance + Black-Scholes Greeks)
  news.py                  — get_news (Yahoo Finance RSS via feedparser)
  earnings.py              — get_earnings (yfinance, 30-day flag)
  logger.py                — log_snapshot(), log_trade() (internal, not @tool)
data/
  portfolio.json           — source of truth for all positions
  snapshots.jsonl          — P&L snapshot appended on every get_prices() call
  trades.jsonl             — trade log appended on every update_portfolio() call
prompts/
  system_prompt.md         — agent persona and behavior rules (generic, no hardcoded dates)
.env                       — ANTHROPIC_API_KEY (never commit this)
requirements.txt
```

## Commands

| Command | What it does |
|---------|-------------|
| `/news [TICKER]` | Latest headlines + impact on position |
| `/catalyst [TICKER]` | Earnings dates, events, macro catalysts |
| `/risk` | Full portfolio risk scan |
| `/put` | Analyze all open puts (roll vs hold vs close) |
| `/pnl` | Live P&L table for all positions |
| `/update [change]` | Record a trade (e.g. "sold 50 AMZN at 195") |
| `brief` | Full morning brief (P&L + flags + news + recommendations) |
| `/help` | Show command list |
| `exit` / `quit` | Exit |

## Key Design Notes

- **Strands handles the agentic loop** — tool calling, result parsing, and multi-step reasoning are automatic
- **@tool decorator** — Strands extracts parameter schema from type hints + docstrings; keep both accurate
- **Black-Scholes** — yfinance provides IV; delta/gamma/theta/vega are computed via scipy in `options.py`
- **Expiry matching** — `options.py` finds the nearest available expiry if exact date isn't in the chain
- **Earnings fallback** — tries `get_earnings_dates()` first, falls back to `ticker.calendar`
- **Slash commands** — expanded to natural language prompts in `expand_command()` before hitting the agent
- **System prompt is generic** — no hardcoded dates, tickers, or positions; those come from live tools

## Adding a New Tool

1. Create the function in `tools/` with `@tool` decorator, type hints, and a clear docstring
2. Import it in `main.py` and add to the `tools=[...]` list in `build_agent()`
3. Optionally add a slash command in `expand_command()` in `main.py`

## Portfolio Data Format

`data/portfolio.json` — edit directly to add/remove positions:

```json
{
  "positions": [
    {"position_type": "shares", "ticker": "AMZN", "shares": 100, "cost_basis": 250.00},
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

## Dependencies

| Package | Version | Use |
|---------|---------|-----|
| `strands-agents` | ≥1.0.0 | Agent loop + tool calling |
| `anthropic` | ≥0.40.0 | Claude API (required by strands AnthropicModel) |
| `yfinance` | ≥0.2.50 | Live prices, options chains, earnings |
| `feedparser` | ≥6.0.0 | Yahoo Finance RSS |
| `scipy` + `numpy` | ≥1.11 / ≥1.24 | Black-Scholes Greeks |
| `python-dotenv` | ≥1.0.0 | Load API key from .env |
