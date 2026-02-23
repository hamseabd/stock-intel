import json
from pathlib import Path
from typing import Optional
from strands import tool
from tools.logger import log_trade

PORTFOLIO_PATH = Path(__file__).parent.parent / "data" / "portfolio.json"


def _load() -> dict:
    return json.loads(PORTFOLIO_PATH.read_text())


def _save(data: dict) -> None:
    PORTFOLIO_PATH.write_text(json.dumps(data, indent=2))


@tool
def get_portfolio() -> str:
    """
    Returns all current portfolio positions including shares and options.
    Use this tool whenever the user asks about their portfolio, positions, or holdings.
    Returns a JSON string with the full position list.
    """
    data = _load()
    return json.dumps(data, indent=2)


@tool
def update_portfolio(
    action: str,
    ticker: str,
    shares: Optional[float] = None,
    price: Optional[float] = None,
    position_type: Optional[str] = "shares",
    option_type: Optional[str] = None,
    strike: Optional[float] = None,
    expiry: Optional[str] = None,
    contracts: Optional[int] = None,
    strategy: Optional[str] = None,
) -> str:
    """
    Updates the portfolio by recording a trade or position change.

    Actions:
    - "buy": Add shares to an existing position or create a new one.
    - "sell": Reduce or close a share position. Logs the realized P&L.
    - "add_option": Add a new option position (put or call).
    - "close_option": Close/remove an existing option position.
    - "assign": Option was assigned; convert to shares at strike price.

    Parameters:
    - action: One of "buy", "sell", "add_option", "close_option", "assign"
    - ticker: Stock ticker symbol (e.g. "AMZN", "AMD")
    - shares: Number of shares for buy/sell actions
    - price: Execution price per share
    - position_type: "shares" or "option" (default: "shares")
    - option_type: "put" or "call" (required for add_option)
    - strike: Option strike price (required for options)
    - expiry: Option expiry date as YYYY-MM-DD (required for options)
    - contracts: Number of option contracts (default: 1)
    - strategy: Option strategy label e.g. "cash_secured_put", "covered_call"

    Returns a confirmation message with the action taken.
    """
    data = _load()
    positions = data["positions"]
    result_msg = ""

    if action == "buy":
        # Find existing share position
        existing = next(
            (p for p in positions if p["ticker"] == ticker and p["position_type"] == "shares"),
            None,
        )
        if existing:
            old_shares = existing["shares"]
            old_basis = existing["cost_basis"]
            new_shares = old_shares + shares
            # Weighted average cost basis
            existing["cost_basis"] = round(
                (old_shares * old_basis + shares * price) / new_shares, 4
            )
            existing["shares"] = new_shares
            result_msg = (
                f"Bought {shares} shares of {ticker} at ${price:.2f}. "
                f"New position: {new_shares} shares @ ${existing['cost_basis']:.2f} avg."
            )
        else:
            positions.append({
                "position_type": "shares",
                "ticker": ticker,
                "shares": shares,
                "cost_basis": price,
            })
            result_msg = f"Added new position: {shares} shares of {ticker} at ${price:.2f}."
        log_trade(action, ticker, shares, price)

    elif action == "sell":
        existing = next(
            (p for p in positions if p["ticker"] == ticker and p["position_type"] == "shares"),
            None,
        )
        if not existing:
            return f"Error: No share position found for {ticker}."
        if shares > existing["shares"]:
            return f"Error: Cannot sell {shares} shares; only {existing['shares']} held."
        realized_pnl = (price - existing["cost_basis"]) * shares
        existing["shares"] = round(existing["shares"] - shares, 6)
        result_msg = (
            f"Sold {shares} shares of {ticker} at ${price:.2f}. "
            f"Realized P&L: ${realized_pnl:+.2f}."
        )
        if existing["shares"] <= 0:
            positions.remove(existing)
            result_msg += " Position fully closed."
        log_trade(action, ticker, shares, price, realized_pnl=realized_pnl)

    elif action == "add_option":
        positions.append({
            "position_type": "option",
            "ticker": ticker,
            "option_type": option_type,
            "strategy": strategy or "",
            "strike": strike,
            "expiry": expiry,
            "contracts": contracts or 1,
            "cost_basis": price or 0.0,
            "status": "open",
        })
        result_msg = (
            f"Added option: {ticker} ${strike} {option_type} exp {expiry}, "
            f"{contracts or 1} contract(s)."
        )
        log_trade(action, ticker, None, price, option_type=option_type,
                  strike=strike, expiry=expiry)

    elif action == "close_option":
        match = next(
            (
                p for p in positions
                if p["position_type"] == "option"
                and p["ticker"] == ticker
                and (strike is None or p.get("strike") == strike)
                and (expiry is None or p.get("expiry") == expiry)
            ),
            None,
        )
        if not match:
            return f"Error: No matching option found for {ticker} strike={strike} expiry={expiry}."
        positions.remove(match)
        result_msg = (
            f"Closed option: {ticker} ${match['strike']} {match.get('option_type', '')} "
            f"exp {match['expiry']}."
        )
        log_trade(action, ticker, None, price, option_type=match.get("option_type"),
                  strike=strike, expiry=expiry)

    elif action == "assign":
        # Option assigned: remove option, add/adjust shares at strike
        opt = next(
            (
                p for p in positions
                if p["position_type"] == "option"
                and p["ticker"] == ticker
                and (strike is None or p.get("strike") == strike)
            ),
            None,
        )
        if not opt:
            return f"Error: No matching option found for assignment on {ticker}."
        assign_price = strike or opt["strike"]
        contracts_assigned = opt.get("contracts", 1)
        assigned_shares = contracts_assigned * 100
        positions.remove(opt)

        existing = next(
            (p for p in positions if p["ticker"] == ticker and p["position_type"] == "shares"),
            None,
        )
        if existing:
            old_shares = existing["shares"]
            old_basis = existing["cost_basis"]
            new_shares = old_shares + assigned_shares
            existing["cost_basis"] = round(
                (old_shares * old_basis + assigned_shares * assign_price) / new_shares, 4
            )
            existing["shares"] = new_shares
        else:
            positions.append({
                "position_type": "shares",
                "ticker": ticker,
                "shares": float(assigned_shares),
                "cost_basis": assign_price,
            })
        result_msg = (
            f"Option assigned: received {assigned_shares} shares of {ticker} at ${assign_price:.2f}."
        )
        log_trade(action, ticker, assigned_shares, assign_price)

    else:
        return f"Error: Unknown action '{action}'."

    _save(data)
    return result_msg
