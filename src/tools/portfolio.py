"""Portfolio management — DynamoDB-backed CRUD."""

import re
from shared.db import get_positions, put_position, delete_position, log_trade
from shared.math_utils import weighted_avg_cost


def get_portfolio(chat_id: str) -> list[dict]:
    return get_positions(chat_id)


def get_share_positions(chat_id: str) -> list[dict]:
    return [p for p in get_positions(chat_id) if p.get("position_type") == "shares"]


def get_option_positions(chat_id: str) -> list[dict]:
    return [p for p in get_positions(chat_id) if p.get("position_type") == "option"]


def get_all_tickers(chat_id: str) -> list[str]:
    return list({p["ticker"] for p in get_positions(chat_id)})


def update_portfolio(chat_id: str, action: str, ticker: str, **kwargs) -> str:
    """Process a portfolio update and return a confirmation message."""
    ticker = ticker.upper()
    positions = get_positions(chat_id)

    if action == "buy":
        shares = kwargs["shares"]
        price = kwargs["price"]
        existing = next((p for p in positions if p["ticker"] == ticker and p["position_type"] == "shares"), None)
        if existing:
            new_shares = existing["shares"] + shares
            new_basis = weighted_avg_cost(existing["shares"], existing["cost_basis"], shares, price)
            existing["shares"] = new_shares
            existing["cost_basis"] = new_basis
            put_position(chat_id, existing)
            msg = f"Bought {shares} {ticker} at ${price:.2f}. Now {new_shares} shares @ ${new_basis:.2f} avg."
        else:
            pos = {"position_type": "shares", "ticker": ticker, "shares": shares, "cost_basis": price}
            put_position(chat_id, pos)
            msg = f"New position: {shares} {ticker} at ${price:.2f}."
        log_trade(chat_id, {"action": "buy", "ticker": ticker, "shares": shares, "price": price})
        return msg

    elif action == "sell":
        shares = kwargs["shares"]
        price = kwargs["price"]
        existing = next((p for p in positions if p["ticker"] == ticker and p["position_type"] == "shares"), None)
        if not existing:
            return f"No share position found for {ticker}."
        if shares > existing["shares"]:
            return f"Can't sell {shares} shares — only {existing['shares']} held."
        realized_pnl = (price - existing["cost_basis"]) * shares
        existing["shares"] = round(existing["shares"] - shares, 6)
        msg = f"Sold {shares} {ticker} at ${price:.2f}. P&L: ${realized_pnl:+.2f}."
        if existing["shares"] <= 0:
            delete_position(chat_id, existing)
            msg += " Position closed."
        else:
            put_position(chat_id, existing)
        log_trade(chat_id, {"action": "sell", "ticker": ticker, "shares": shares, "price": price, "realized_pnl": realized_pnl})
        return msg

    elif action == "add_option":
        pos = {
            "position_type": "option",
            "ticker": ticker,
            "option_type": kwargs.get("option_type", "put"),
            "strategy": kwargs.get("strategy", ""),
            "strike": kwargs["strike"],
            "expiry": kwargs["expiry"],
            "contracts": kwargs.get("contracts", 1),
            "cost_basis": kwargs.get("price", 0.0),
            "status": "open",
        }
        put_position(chat_id, pos)
        log_trade(chat_id, {"action": "add_option", "ticker": ticker, **{k: v for k, v in kwargs.items()}})
        return f"Added {ticker} ${pos['strike']} {pos['option_type']} exp {pos['expiry']}."

    elif action == "close_option":
        strike = kwargs.get("strike")
        expiry = kwargs.get("expiry")
        match = next(
            (p for p in positions
             if p["position_type"] == "option" and p["ticker"] == ticker
             and (strike is None or p.get("strike") == strike)
             and (expiry is None or p.get("expiry") == expiry)),
            None,
        )
        if not match:
            return f"No matching option found for {ticker}."
        delete_position(chat_id, match)
        log_trade(chat_id, {"action": "close_option", "ticker": ticker, "strike": strike, "expiry": expiry})
        return f"Closed {ticker} ${match['strike']} {match.get('option_type', '')} exp {match['expiry']}."

    return f"Unknown action: {action}"


def parse_trade_text(text: str) -> dict | None:
    """Parse natural language trade: 'sold 50 AMZN at 195' → dict.

    Returns dict with action, ticker, shares, price or None if unparseable.
    """
    text = text.lower().strip()

    # "sold 50 AMZN at 195" / "bought 100 AMD at 165.50"
    m = re.match(r"(bought|sold|buy|sell)\s+(\d+\.?\d*)\s+([a-z]+)\s+(?:at|@)\s+\$?(\d+\.?\d*)", text, re.IGNORECASE)
    if m:
        action_word = m.group(1).lower()
        action = "buy" if action_word in ("bought", "buy") else "sell"
        return {
            "action": action,
            "ticker": m.group(3).upper(),
            "shares": float(m.group(2)),
            "price": float(m.group(4)),
        }

    # "sell 50 AMZN 195"
    m = re.match(r"(buy|sell)\s+(\d+\.?\d*)\s+([a-z]+)\s+\$?(\d+\.?\d*)", text, re.IGNORECASE)
    if m:
        return {
            "action": m.group(1).lower(),
            "ticker": m.group(3).upper(),
            "shares": float(m.group(2)),
            "price": float(m.group(4)),
        }

    return None
