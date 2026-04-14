"""Options analysis — Greeks, chain data, recommendations."""

from datetime import date, datetime

import yfinance as yf

from shared.math_utils import black_scholes, days_to_expiry, option_recommendation


def _find_nearest_expiry(available: list[str], target: str) -> str:
    target_date = datetime.strptime(target, "%Y-%m-%d").date()
    return min(available, key=lambda d: abs((datetime.strptime(d, "%Y-%m-%d").date() - target_date).days))


def analyze_option(ticker: str, strike: float, expiry: str, option_type: str = "put",
                   risk_free_rate: float = 0.045) -> dict:
    """Full option analysis: Greeks, intrinsic/extrinsic, bid/ask, recommendation."""
    tkr = yf.Ticker(ticker)
    try:
        S = float(tkr.fast_info.last_price)
    except Exception:
        hist = tkr.history(period="1d")
        S = float(hist["Close"].iloc[-1])

    available_dates = list(tkr.options)
    if not available_dates:
        return {"error": f"No options available for {ticker}."}

    use_expiry = expiry if expiry in available_dates else _find_nearest_expiry(available_dates, expiry)

    chain = tkr.option_chain(use_expiry)
    df = chain.puts if option_type == "put" else chain.calls
    df = df.copy()
    df["strike_diff"] = (df["strike"] - strike).abs()
    row = df.sort_values("strike_diff").iloc[0]

    import math

    def _safe_float(val, default=0.0):
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return float(val)

    def _safe_int(val, default=0):
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return int(val)

    actual_strike = float(row["strike"])
    bid = _safe_float(row.get("bid", 0))
    ask = _safe_float(row.get("ask", 0))
    mid = round((bid + ask) / 2, 4)
    iv = _safe_float(row.get("impliedVolatility", 0))
    volume = _safe_int(row.get("volume", 0))
    open_interest = _safe_int(row.get("openInterest", 0))

    dte = days_to_expiry(use_expiry)
    sigma = iv if iv > 0.01 else 0.30
    T = max(dte / 365, 0)
    greeks = black_scholes(S, actual_strike, T, risk_free_rate, sigma, option_type)

    itm = (S < actual_strike) if option_type == "put" else (S > actual_strike)
    moneyness = round((S - actual_strike) / actual_strike * 100, 2)
    rec, reason = option_recommendation(dte, itm, greeks["delta"], greeks["extrinsic"], moneyness)

    return {
        "ticker": ticker,
        "option_type": option_type,
        "strike": actual_strike,
        "expiry": use_expiry,
        "underlying_price": round(S, 2),
        "dte": dte,
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "iv": round(iv * 100, 2),
        "delta": greeks["delta"],
        "gamma": greeks["gamma"],
        "theta": greeks["theta"],
        "vega": greeks["vega"],
        "intrinsic": greeks["intrinsic"],
        "extrinsic": greeks["extrinsic"],
        "volume": volume,
        "open_interest": open_interest,
        "itm": itm,
        "moneyness_pct": moneyness,
        "recommendation": rec,
        "recommendation_reason": reason,
    }


def analyze_all_options(positions: list[dict]) -> list[dict]:
    """Analyze all open option positions."""
    results = []
    for pos in positions:
        if pos.get("position_type") != "option" or pos.get("status") != "open":
            continue
        analysis = analyze_option(
            pos["ticker"], pos["strike"], pos["expiry"],
            pos.get("option_type", "put"),
        )
        if "error" not in analysis:
            results.append(analysis)
    return results
