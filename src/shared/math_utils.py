"""Pure math functions for technical analysis, P&L, and Black-Scholes Greeks.

No API calls, no I/O — just math. Every function takes numbers in, returns numbers out.
"""

import math
from datetime import date, datetime

import numpy as np
from scipy.stats import norm


# ── P&L ────────────────────────────────────────────────────────────────────

def calc_pnl(shares: float, cost_basis: float, current_price: float) -> dict:
    total_cost = shares * cost_basis
    market_value = shares * current_price
    dollar_pnl = market_value - total_cost
    pct_pnl = (dollar_pnl / total_cost * 100) if total_cost != 0 else 0.0
    return {
        "total_cost": round(total_cost, 2),
        "market_value": round(market_value, 2),
        "dollar_pnl": round(dollar_pnl, 2),
        "pct_pnl": round(pct_pnl, 2),
    }


def weighted_avg_cost(old_shares: float, old_basis: float, new_shares: float, new_price: float) -> float:
    total_shares = old_shares + new_shares
    if total_shares == 0:
        return 0.0
    return round((old_shares * old_basis + new_shares * new_price) / total_shares, 4)


# ── Black-Scholes Greeks ──────────────────────────────────────────────────

def black_scholes(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "put",
) -> dict:
    """Compute Black-Scholes price and Greeks for a European option.

    Args:
        S: Current underlying price
        K: Strike price
        T: Time to expiry in years
        r: Risk-free rate (annualized)
        sigma: Implied volatility (annualized)
        option_type: "put" or "call"

    Returns dict with: price, delta, gamma, theta, vega, intrinsic, extrinsic
    """
    if T <= 0 or sigma <= 0:
        intrinsic = max(K - S, 0) if option_type == "put" else max(S - K, 0)
        return {
            "price": intrinsic,
            "delta": -1.0 if (option_type == "put" and S < K) else (1.0 if option_type == "call" and S > K else 0.0),
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
        delta = norm.cdf(d1) - 1
    else:
        price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)

    gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
    common_term = -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
    if option_type == "put":
        theta = (common_term + r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365
    else:
        theta = (common_term - r * K * math.exp(-r * T) * norm.cdf(d2)) / 365
    vega = S * norm.pdf(d1) * math.sqrt(T) / 100

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


def days_to_expiry(expiry_str: str) -> int:
    expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    return (expiry - date.today()).days


def option_recommendation(
    dte: int, itm: bool, delta: float, extrinsic: float, moneyness_pct: float
) -> tuple[str, str]:
    """Return (recommendation, reason) based on option metrics."""
    if dte <= 0:
        return "expired", "Option has expired."
    if dte <= 2:
        if itm:
            return "close_or_roll", f"ITM with {dte} DTE — high assignment risk. Close or roll."
        return "let_expire", f"OTM with {dte} DTE, ${extrinsic:.2f} extrinsic. Let expire worthless."
    if dte <= 7:
        if itm:
            return "roll_or_close", f"ITM {abs(moneyness_pct):.1f}% with {dte} DTE. Roll or close."
        if extrinsic < 0.10:
            return "let_expire", f"OTM, only ${extrinsic:.2f} extrinsic left. Let expire."
        return "hold_or_close", f"OTM with {dte} DTE, ${extrinsic:.2f} extrinsic. Monitor closely."
    if abs(delta) > 0.60:
        return "roll_or_close", f"High delta ({delta:.2f}) — deep ITM risk. Roll down/out."
    return "hold", f"Manageable delta ({delta:.2f}) with {dte} DTE. Hold and monitor."


# ── Technical Indicators ──────────────────────────────────────────────────

def calc_rsi(prices: np.ndarray, period: int = 14) -> float:
    """Calculate RSI from a price series. Returns 0-100."""
    if len(prices) < period + 1:
        return 50.0  # not enough data
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calc_sma(prices: np.ndarray, period: int) -> float:
    """Simple Moving Average of the last `period` prices."""
    if len(prices) < period:
        return float(np.mean(prices))
    return round(float(np.mean(prices[-period:])), 2)


def calc_ema(prices: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average for entire series."""
    ema = np.zeros_like(prices, dtype=float)
    ema[0] = prices[0]
    multiplier = 2 / (period + 1)
    for i in range(1, len(prices)):
        ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1]
    return ema


def calc_macd(prices: np.ndarray) -> dict:
    """MACD: 12-EMA minus 26-EMA, signal = 9-EMA of MACD line."""
    if len(prices) < 26:
        return {"macd_line": 0.0, "signal": 0.0, "histogram": 0.0}
    ema12 = calc_ema(prices, 12)
    ema26 = calc_ema(prices, 26)
    macd_line = ema12 - ema26
    signal = calc_ema(macd_line, 9)
    histogram = macd_line - signal
    return {
        "macd_line": round(float(macd_line[-1]), 4),
        "signal": round(float(signal[-1]), 4),
        "histogram": round(float(histogram[-1]), 4),
    }


def calc_bollinger(prices: np.ndarray, period: int = 20, std_dev: float = 2.0) -> dict:
    """Bollinger Bands: middle = SMA, upper/lower = SMA +/- std_dev * stdev."""
    if len(prices) < period:
        mid = float(np.mean(prices))
        sd = float(np.std(prices))
        return {"upper": round(mid + std_dev * sd, 2), "middle": round(mid, 2), "lower": round(mid - std_dev * sd, 2)}
    window = prices[-period:]
    mid = float(np.mean(window))
    sd = float(np.std(window))
    return {
        "upper": round(mid + std_dev * sd, 2),
        "middle": round(mid, 2),
        "lower": round(mid - std_dev * sd, 2),
    }


def calc_support_resistance(prices: np.ndarray, window: int = 20) -> dict:
    """Simple support/resistance: min/max of recent window."""
    if len(prices) < window:
        return {"support": round(float(np.min(prices)), 2), "resistance": round(float(np.max(prices)), 2)}
    recent = prices[-window:]
    return {
        "support": round(float(np.min(recent)), 2),
        "resistance": round(float(np.max(recent)), 2),
    }


def overall_technical_signal(rsi: float, macd_hist: float, price: float, sma_50: float, sma_200: float) -> str:
    """Combine indicators into a single signal."""
    score = 0
    if rsi < 30:
        score -= 1  # oversold (could be bullish reversal, but currently bearish)
    elif rsi > 70:
        score += 1  # overbought (currently bullish, could reverse)
    elif rsi < 50:
        score -= 0.5
    else:
        score += 0.5

    if macd_hist > 0:
        score += 1
    else:
        score -= 1

    if price > sma_50:
        score += 0.5
    else:
        score -= 0.5

    if price > sma_200:
        score += 0.5
    else:
        score -= 0.5

    if score >= 1.5:
        return "bullish"
    elif score <= -1.5:
        return "bearish"
    return "neutral"


# ── Options Flow ──────────────────────────────────────────────────────────

def is_unusual_flow(volume: int, open_interest: int, ratio_threshold: float = 5.0) -> bool:
    if open_interest <= 0:
        return volume > 1000  # no OI but high volume
    return (volume / open_interest) >= ratio_threshold


def calc_premium(price: float, volume: int) -> float:
    """Estimate total premium traded: mid_price * volume * 100 (contracts)."""
    return round(price * volume * 100, 2)


def put_call_ratio(total_put_volume: int, total_call_volume: int) -> float:
    if total_call_volume == 0:
        return 999.0 if total_put_volume > 0 else 1.0
    return round(total_put_volume / total_call_volume, 2)
