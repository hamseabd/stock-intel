import os
import sys
import json
import warnings
from pathlib import Path
from dotenv import load_dotenv

# Suppress Pydantic serialization warnings caused by anthropic SDK returning
# ParsedTextBlock (citations feature) that strands-agents hasn't modeled yet.
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic.*")

# Load .env before importing strands (which may init the Anthropic client)
load_dotenv(Path(__file__).parent / ".env")

from strands import Agent
from strands.models.anthropic import AnthropicModel

from tools.portfolio import get_portfolio, update_portfolio
from tools.prices import get_prices
from tools.options import get_options_analysis
from tools.news import get_news
from tools.earnings import get_earnings

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.md"
PORTFOLIO_PATH = Path(__file__).parent / "data" / "portfolio.json"

HELP_TEXT = """
Commands:
  /news [TICKER]     — latest headlines and what they mean for your position
  /catalyst [TICKER] — upcoming earnings, events, and macro catalysts
  /risk              — full portfolio risk scan (drawdowns, expiring options, earnings)
  /put               — analyze all open put positions (roll vs hold vs close)
  /pnl               — current P&L based on live prices
  /update [change]   — update portfolio (e.g. "sold 50 AMZN at 195")
  brief              — full morning brief
  exit / quit        — exit
"""


def _get_option_tickers() -> list[str]:
    """Return tickers that have open option positions."""
    data = json.loads(PORTFOLIO_PATH.read_text())
    return [
        p["ticker"]
        for p in data["positions"]
        if p["position_type"] == "option" and p.get("status") == "open"
    ]


def _get_all_tickers() -> list[str]:
    data = json.loads(PORTFOLIO_PATH.read_text())
    return list({p["ticker"] for p in data["positions"]})


def expand_command(raw: str) -> str:
    """
    Translate slash commands into natural language prompts for the agent.
    Returns the original string if not a slash command.
    """
    parts = raw.strip().split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/news":
        if not arg:
            tickers = _get_all_tickers()
            return (
                f"Fetch the latest news for {', '.join(tickers)}. "
                "For each, summarize the top headlines and flag anything that could impact my position."
            )
        return (
            f"Fetch the latest news for {arg.upper()} using get_news. "
            "Summarize the headlines and explain what they mean for my position."
        )

    if cmd == "/catalyst":
        ticker = arg.upper() if arg else None
        if ticker:
            return (
                f"What are the upcoming catalysts for {ticker}? "
                f"Call get_earnings to check for earnings dates, and get_news('{ticker}') for recent events. "
                "Summarize all near-term catalysts and their potential impact."
            )
        tickers = _get_all_tickers()
        return (
            f"What are the upcoming catalysts for my portfolio tickers ({', '.join(tickers)})? "
            "Call get_earnings and get_news for each. Summarize all near-term catalysts."
        )

    if cmd == "/risk":
        return (
            "Run a full portfolio risk scan. Call get_portfolio, get_prices, and get_earnings. "
            "Flag: (1) any options expiring within 14 days with their DTE, delta, and recommendation; "
            "(2) any positions down >10% from cost basis; "
            "(3) any tickers with earnings within 30 days; "
            "(4) overall portfolio concentration risk. "
            "Be specific and actionable."
        )

    if cmd == "/put":
        opt_tickers = _get_option_tickers()
        if not opt_tickers:
            return "Check my portfolio for any open put positions and confirm there are none, or analyze any you find."
        # Build analysis request for each open put
        parts_list = []
        data = json.loads(PORTFOLIO_PATH.read_text())
        for p in data["positions"]:
            if p["position_type"] == "option" and p.get("option_type") == "put" and p.get("status") == "open":
                parts_list.append(
                    f"get_options_analysis('{p['ticker']}', {p['strike']}, '{p['expiry']}')"
                )
        calls = " and ".join(parts_list) if parts_list else "get_portfolio to find open puts"
        return (
            f"Analyze all my open put positions. Call {calls}. "
            "For each: show strike vs current price, DTE, delta, theta, intrinsic/extrinsic value, IV. "
            "Give a clear roll / hold / close recommendation with specific reasoning."
        )

    if cmd == "/pnl":
        return (
            "Call get_prices to fetch live prices for all positions. "
            "Show me a P&L table: ticker | shares | cost basis | current price | $ P&L | % P&L. "
            "Then show portfolio totals. Flag any position down >10%."
        )

    if cmd == "/update":
        if not arg:
            return "What portfolio update would you like to make? Please describe the trade."
        return (
            f"Process this portfolio update: '{arg}'. "
            "Extract the action, ticker, shares/contracts, and price. "
            "Call update_portfolio() with the correct parameters and confirm what was recorded."
        )

    return raw  # not a slash command — pass through as-is


def build_agent() -> Agent:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "your-key-here":
        print("ERROR: ANTHROPIC_API_KEY not set. Add it to your .env file.")
        sys.exit(1)

    model = AnthropicModel(
        model_id="claude-sonnet-4-6",
        max_tokens=8096,
        client_args={"api_key": api_key},
    )

    system_prompt = SYSTEM_PROMPT_PATH.read_text()

    agent = Agent(
        model=model,
        tools=[
            get_portfolio,
            update_portfolio,
            get_prices,
            get_options_analysis,
            get_news,
            get_earnings,
        ],
        system_prompt=system_prompt,
    )
    return agent


def main() -> None:
    print("=" * 60)
    print("  Investment Workbench — AI Analyst")
    print("  Type /help to see available commands.")
    print("=" * 60)

    agent = build_agent()

    # Startup: flag urgent items from live data
    print("\nAgent: Initializing — checking for urgent flags...\n")
    agent(
        "Call get_portfolio and get_prices. Flag any urgent items: "
        "options expiring within 14 days, positions down >10%, and note total portfolio P&L. "
        "Keep it to 5 lines max."
    )

    while True:
        try:
            query = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not query:
            continue

        if query.lower() in ("exit", "quit", "q"):
            print("Goodbye.")
            break

        if query.lower() in ("/help", "help"):
            print(HELP_TEXT)
            continue

        agent(expand_command(query))


if __name__ == "__main__":
    main()
