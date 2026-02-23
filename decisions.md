# Architecture Decisions & Trade-offs

This file explains every significant choice made in this project — why we chose it,
what the alternatives were, and what the trade-offs are.

---

## 1. Why Strands Agents SDK (not raw Claude API)?

**What Strands does:**
When you call Claude with tools, the flow is:
1. Send message + tool definitions to Claude API
2. Claude responds with a `tool_use` block (it wants to call a tool)
3. You run the tool, get the result
4. Send the result back to Claude
5. Repeat until Claude gives a final text response

This loop is called the **agentic loop**. You have to implement it yourself if you
use the raw Anthropic SDK.

**Without Strands:**
```python
# You'd write ~100 lines of this yourself
while True:
    response = client.messages.create(model=..., tools=..., messages=history)
    if response.stop_reason == "tool_use":
        for block in response.content:
            if block.type == "tool_use":
                result = run_tool(block.name, block.input)  # your dispatch logic
                history.append({"role": "tool", "content": result})
    else:
        print(response.content[0].text)
        break
```

**With Strands:**
```python
agent = Agent(model=model, tools=[get_prices, get_portfolio, ...])
agent("brief")  # Strands handles everything above
```

**Trade-off:** Strands adds a dependency and some abstraction. If something breaks,
you're debugging inside the framework, not your own code. But for a personal tool
where simplicity matters, this is the right call.

---

## 2. Why not MCP (Model Context Protocol)?

**What MCP is:**
MCP is a protocol that lets Claude Code (the CLI) call external tools registered in
a config file. The tools run as a separate subprocess that communicates over stdin/stdout.

**Why we're not using it:**
- We're not using Claude Code — we're calling the Claude API directly from Python
- MCP requires a running server process, stdio transport, and a `mcp_config.json`
- Adds `mcp` package, server code, async complexity, and debugging difficulty
- Result is the same: Claude calls your tools. MCP is just a different transport mechanism.

**When MCP makes sense:**
- You want Claude Code (the CLI) to have custom tools
- You want to share the tool server across multiple projects or team members
- You need tools that run as a persistent background service

**Our case:** We own the full Python process. Tools are just functions. No server needed.

---

## 3. Why Anthropic API directly (not AWS Bedrock)?

**Anthropic direct API:**
- Simpler: just an API key in `.env`
- Fastest access to the latest Claude models
- Strands supports it via `AnthropicModel`

**AWS Bedrock:**
- Requires AWS account, IAM credentials, region config
- Useful if you're already in the AWS ecosystem
- Slightly more latency (routes through AWS)
- Good for compliance/enterprise reasons

**Our case:** Personal local tool. Direct API is the right choice.

---

## 4. Why plain Python functions for tools (not classes or separate scripts)?

**Option A: Plain functions with @tool** (chosen)
```python
@tool
def get_prices() -> list:
    """Fetch live prices for all portfolio positions."""
    ...
```

**Option B: Separate scripts + subprocess**
```bash
python tools/prices.py  # outputs JSON to stdout
```

**Option C: Class-based tool registry**
```python
class PricesTool(BaseTool):
    def run(self) -> dict: ...
```

**Why Option A:**
- Strands' `@tool` decorator is specifically designed for this — it auto-generates
  the tool schema (name, description, parameter types) from your function signature
  and docstring. No boilerplate.
- Functions are composable, testable, and importable
- No subprocess overhead, no stdout parsing risk
- One file per concern, easy to read and debug

---

## 5. Why Black-Scholes for Greeks (not just using yfinance data)?

**The problem:** yfinance's `option_chain()` returns a DataFrame with these columns:
- contractSymbol, lastTradeDate, strike, lastPrice, bid, ask, change, percentChange,
  volume, openInterest, **impliedVolatility**

Notice what's **missing**: delta, theta, gamma, vega.

yfinance does NOT return Greeks. It only returns implied volatility (IV).

**Our solution:** Use IV from yfinance as the `sigma` input to Black-Scholes formulas,
then compute delta/theta/gamma/vega ourselves using `scipy.stats.norm`.

**Trade-off:** Black-Scholes assumes:
- European-style options (American options can be exercised early — adds complexity)
- Log-normal price distribution (real markets have fat tails)
- Constant volatility (real IV varies by strike — the "volatility smile")

For a personal monitoring tool, these approximations are fine. You're using the Greeks
to make directional decisions ("is my delta getting too negative?"), not to price
options to 4 decimal places.

**Alternative:** Pay for a data provider like Tradier or CBOE LiveVol that returns
actual market Greeks. Free upgrade path if you want precision later.

---

## 6. Why yfinance (and what are its limits)?

**Why yfinance:**
- Free, no API key needed
- Wraps Yahoo Finance data
- Returns prices, options chains, earnings calendars
- Widely used, well-maintained

**Known limitations:**
- **~15 min delayed prices** during market hours (not truly real-time)
- **Options data only during market hours** — outside 9:30–4:00 ET you get stale/empty data
- **Earnings dates are estimates** — companies don't always file on time
- **Can break without warning** if Yahoo Finance changes their internal API
- **Rate limiting** — don't call it in a tight loop; batch downloads help

**For our use case:** This is a daily briefing tool, not a HFT system. 15-min delay is fine.

---

## 7. Why feedparser for news (not a paid news API)?

**feedparser + Yahoo Finance RSS:**
- Free, no API key
- Yahoo Finance publishes RSS feeds per ticker:
  `https://feeds.finance.yahoo.com/rss/2.0/headline?s=AMD`
- feedparser parses XML into Python dicts cleanly
- ~5 headlines per fetch, typically recent (hours old)

**Limitations:**
- Yahoo can change/kill RSS endpoints without notice
- No sentiment analysis, no filtering by relevance
- Sometimes articles are duplicate or generic market commentary

**Alternative:** Newsapi.org ($50/month), Benzinga, Alpha Vantage news. Better signal,
but overkill for a personal tool.

---

## 8. Why portfolio.json (not a database)?

**Why plain JSON:**
- Zero setup — no Postgres, no SQLite, no ORM
- Human-readable — you can open it in any editor
- Easy to back up, version control, or edit manually in a pinch
- Sufficient for a single-user portfolio with <100 positions

**Why not SQLite:**
- Overkill for this use case
- Adds query complexity for no benefit
- JSON is fine until you need query performance or multi-user access

**One rule:** Never edit portfolio.json manually. Always use `update_portfolio()`.
This ensures cost basis calculations (weighted average) stay correct.

---

## 9. Why a system_prompt.md file (not hardcoded in main.py)?

The system prompt defines how Claude behaves — its persona, what tools to call when,
how to format responses, what to flag proactively.

Keeping it in a separate `.md` file means:
- Easy to edit and iterate without touching Python code
- Readable as documentation
- Can be versioned separately

---

## 10. Why JSONL for History (not a database or CSV)?

**What we're logging:**
- `data/snapshots.jsonl` — one line per session: total portfolio value + per-position P&L
- `data/trades.jsonl` — one line per trade: action, ticker, price, P&L

**Why JSONL (newline-delimited JSON):**
- Append-only — just `file.write(json.dumps(record) + "\n")`, never rewrite the file
- Human-readable — open it in any editor
- Each line is valid JSON — easy to parse in Python: `[json.loads(l) for l in open(...)]`
- Works with pandas for charting: `pd.read_json("data/snapshots.jsonl", lines=True)`
- No schema migration headaches like SQL

**Why not CSV:**
- Nested structures (per-position breakdown) don't fit cleanly in CSV rows
- JSONL handles arbitrary depth without flattening hacks

**Why not SQLite:**
- Overkill for append-only logs with <10,000 rows
- JSONL is trivially portable and needs no setup

**What you can build with this data later:**
- Plot portfolio value over time (pandas + matplotlib)
- Compare your trades against "what if I held"
- Ask the agent "how has AMD done since I first bought it?" — it can read the snapshots

---

## 11. The AMD $230 Put — What to Watch (4 DTE as of Feb 23, 2026)

This is the most time-sensitive position right now. Here's the framework:

**If AMD is above $230 at expiry (Feb 27):**
- Put expires worthless — you keep 100% of premium collected. Best outcome.
- DTE 4 + AMD above strike → Hold, let it expire.

**If AMD drops toward $230:**
- Watch delta. If delta crosses -0.40, the option is getting expensive to hold.
- With only 4 DTE, there's almost no extrinsic value left to roll for meaningful credit.
- Consider closing early (buy back the put) to avoid assignment risk.

**If AMD is below $230 at expiry:**
- Assignment: you buy 100 shares at $230 per share ($23,000 cash required)
- This is the CSP strategy working as designed — you'd own AMD at $230 cost basis
- Only bad if you don't want to own AMD at $230

**How the tool helps:**
`get_options_analysis("AMD", 230.0, "2026-02-27")` will return live delta, DTE, intrinsic/extrinsic,
and a recommendation (roll/hold/close/expired) based on these thresholds.
