import json
import math
from datetime import date, datetime
from typing import Optional
import numpy as np
import yfinance as yf
from scipy.stats import norm
from strands import tool


def _black_scholes_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "put",
) -> dict:
    """Compute Black-Scholes price and Greeks for a European option."""
    if T <= 0 or sigma <= 0:
        # At/past expiry
        intrinsic = max(K - S, 0) if option_type == "put" else max(S - K, 0)
        return {
            "price": intrinsic,
            "delta": -1.0 if (option_type == "put" and S < K) else 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "intrinsic": intrinsic,
            "extrinsic": 0.0,
        }

    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "put":
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1  # negative for puts
    else:
        price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)

    gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
    # Theta per calendar day (annualized / 365)
    theta = (
        -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
        - r * K * math.exp(-r * T) * (norm.cdf(-d2) if option_type == "put" else norm.cdf(d2))
    ) / 365
    vega = S * norm.pdf(d1) * math.sqrt(T) / 100  # per 1% move in IV

    intrinsic = max(K - S, 0) if option_type == "put" else max(S - K, 0)
    extrinsic = max(price - intrinsic, 0)

    return {
        "price": round(price, 4),
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
        "intrinsic": round(intrinsic, 4),
        "extrinsic": round(extrinsic, 4),
    }


def _find_nearest_expiry(option_chain_dates: list[str], target_expiry: str) -> str:
    """Return the expiry date string from available dates closest to target."""
    target = datetime.strptime(target_expiry, "%Y-%m-%d").date()
    best = min(
        option_chain_dates,
        key=lambda d: abs((datetime.strptime(d, "%Y-%m-%d").date() - target).days),
    )
    return best


@tool
def get_options_analysis(
    ticker: str,
    strike: float,
    expiry: str,
    option_type: str = "put",
    risk_free_rate: float = 0.045,
) -> str:
    """
    Analyzes an options position using live market data and Black-Scholes Greeks.

    Fetches the live option chain from yfinance, finds the contract matching the
    given strike and expiry (or nearest available), and computes:
    - Bid / Ask / Mid price
    - Implied Volatility (IV)
    - Days to Expiry (DTE)
    - Intrinsic and extrinsic value
    - Delta, Gamma, Theta, Vega
    - Recommendation: roll / close / hold / let_expire with rationale

    Parameters:
    - ticker: Stock ticker symbol (e.g. "AMD")
    - strike: Option strike price (e.g. 230.0)
    - expiry: Option expiry date as YYYY-MM-DD (e.g. "2026-02-27")
    - option_type: "put" or "call" (default: "put")
    - risk_free_rate: Annual risk-free rate for Black-Scholes (default: 0.045)

    Returns a JSON string with full option analysis and recommendation.
    """
    tkr = yf.Ticker(ticker)
    info = tkr.fast_info
    try:
        S = float(info.last_price)
    except Exception:
        hist = tkr.history(period="1d")
        S = float(hist["Close"].iloc[-1])

    # Get available expiry dates
    try:
        available_dates = list(tkr.options)
    except Exception:
        return json.dumps({"error": f"Could not fetch options chain for {ticker}."})

    if not available_dates:
        return json.dumps({"error": f"No options available for {ticker}."})

    # Match or find nearest expiry
    if expiry in available_dates:
        use_expiry = expiry
    else:
        use_expiry = _find_nearest_expiry(available_dates, expiry)

    # Fetch option chain for that expiry
    chain = tkr.option_chain(use_expiry)
    df = chain.puts if option_type == "put" else chain.calls

    # Find row closest to target strike
    df = df.copy()
    df["strike_diff"] = (df["strike"] - strike).abs()
    row = df.sort_values("strike_diff").iloc[0]

    actual_strike = float(row["strike"])
    bid = float(row.get("bid", 0) or 0)
    ask = float(row.get("ask", 0) or 0)
    mid = round((bid + ask) / 2, 4)
    iv = float(row.get("impliedVolatility", 0) or 0)
    volume = int(row.get("volume", 0) or 0)
    open_interest = int(row.get("openInterest", 0) or 0)

    # DTE
    today = date.today()
    expiry_date = datetime.strptime(use_expiry, "%Y-%m-%d").date()
    dte = (expiry_date - today).days

    # Black-Scholes Greeks (use market IV if available, else 0.30 fallback)
    sigma = iv if iv > 0.01 else 0.30
    T = max(dte / 365, 0)
    greeks = _black_scholes_greeks(S, actual_strike, T, risk_free_rate, sigma, option_type)

    # Recommendation logic
    itm = (S < actual_strike) if option_type == "put" else (S > actual_strike)
    moneyness = round((S - actual_strike) / actual_strike * 100, 2)  # positive = OTM for put
    extrinsic = greeks["extrinsic"]
    delta = greeks["delta"]

    if dte <= 0:
        rec = "expired"
        reason = "Option has expired."
    elif dte <= 2:
        if itm:
            rec = "close_or_roll"
            reason = (
                f"ITM with {dte} DTE — high assignment risk. "
                f"Close now or roll to avoid forced assignment."
            )
        else:
            rec = "let_expire"
            reason = (
                f"OTM with {dte} DTE and minimal extrinsic (${extrinsic:.4f}). "
                f"Let expire worthless unless IV spikes."
            )
    elif dte <= 7:
        if itm:
            rec = "roll_or_close"
            reason = (
                f"ITM ${abs(moneyness):.1f}% with only {dte} DTE. "
                f"Roll out and/or down to avoid assignment, or close to cap loss."
            )
        elif extrinsic < 0.10:
            rec = "let_expire"
            reason = (
                f"OTM with {dte} DTE, only ${extrinsic:.2f} extrinsic remaining. "
                f"Not worth rolling — let expire worthless."
            )
        else:
            rec = "hold_or_close"
            reason = (
                f"OTM with {dte} DTE and ${extrinsic:.2f} extrinsic. "
                f"Theta decay accelerating — monitor closely."
            )
    else:
        if abs(delta) > 0.60:
            rec = "roll_or_close"
            reason = f"High delta ({delta:.2f}) — deep ITM risk. Consider rolling down/out."
        else:
            rec = "hold"
            reason = f"Manageable delta ({delta:.2f}) with {dte} DTE. Hold and monitor."

    result = {
        "ticker": ticker,
        "option_type": option_type,
        "requested_strike": strike,
        "actual_strike": actual_strike,
        "requested_expiry": expiry,
        "actual_expiry": use_expiry,
        "underlying_price": round(S, 2),
        "dte": dte,
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "implied_volatility_pct": round(iv * 100, 2),
        "volume": volume,
        "open_interest": open_interest,
        "greeks": {
            "delta": greeks["delta"],
            "gamma": greeks["gamma"],
            "theta_per_day": greeks["theta"],
            "vega_per_1pct_iv": greeks["vega"],
        },
        "intrinsic_value": greeks["intrinsic"],
        "extrinsic_value": extrinsic,
        "itm": itm,
        "moneyness_pct": moneyness,
        "recommendation": rec,
        "recommendation_reason": reason,
    }

    return json.dumps(result, indent=2)
