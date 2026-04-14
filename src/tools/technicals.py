"""Technical analysis — RSI, MACD, SMA, Bollinger, support/resistance."""

import numpy as np

from tools.prices import fetch_price_history
from shared.math_utils import (
    calc_rsi,
    calc_sma,
    calc_macd,
    calc_bollinger,
    calc_support_resistance,
    overall_technical_signal,
)


def analyze_technicals(ticker: str) -> dict:
    """Run full technical analysis on a ticker."""
    history = fetch_price_history(ticker, period="6mo")
    closes = np.array(history["closes"])
    volumes = np.array(history["volumes"])

    if len(closes) < 26:
        return {"ticker": ticker, "error": "Insufficient price history."}

    price = round(float(closes[-1]), 2)
    rsi = calc_rsi(closes, 14)
    macd = calc_macd(closes)
    sma_50 = calc_sma(closes, 50)
    sma_200 = calc_sma(closes, 200)
    bb = calc_bollinger(closes, 20)
    sr = calc_support_resistance(closes, 20)
    avg_volume = round(float(np.mean(volumes[-20:])), 0) if len(volumes) >= 20 else round(float(np.mean(volumes)), 0)
    current_volume = float(volumes[-1]) if len(volumes) > 0 else 0

    signal = overall_technical_signal(rsi, macd["histogram"], price, sma_50, sma_200)

    return {
        "ticker": ticker,
        "price": price,
        "rsi_14": rsi,
        "macd_line": macd["macd_line"],
        "macd_signal": macd["signal"],
        "macd_histogram": macd["histogram"],
        "sma_50": sma_50,
        "sma_200": sma_200,
        "bb_upper": bb["upper"],
        "bb_middle": bb["middle"],
        "bb_lower": bb["lower"],
        "support": sr["support"],
        "resistance": sr["resistance"],
        "avg_volume": avg_volume,
        "current_volume": current_volume,
        "overall_signal": signal,
    }


def get_technical_flags(tickers: list[str]) -> list[dict]:
    """Scan tickers for technical extremes."""
    flags = []
    for ticker in tickers:
        t = analyze_technicals(ticker)
        if "error" in t:
            continue
        reasons = []
        if t["rsi_14"] < 30:
            reasons.append(f"RSI {t['rsi_14']:.0f} (oversold)")
        elif t["rsi_14"] > 70:
            reasons.append(f"RSI {t['rsi_14']:.0f} (overbought)")
        if t["macd_histogram"] > 0 and t["macd_line"] > t["macd_signal"]:
            reasons.append("MACD bullish crossover")
        elif t["macd_histogram"] < 0 and t["macd_line"] < t["macd_signal"]:
            reasons.append("MACD bearish crossover")
        if t["price"] < t["sma_200"]:
            reasons.append("Below 200-SMA")
        if t["price"] > t["sma_50"] and t["sma_50"] > t["sma_200"]:
            reasons.append("Golden cross zone")

        if reasons:
            flags.append({"ticker": ticker, "signal": t["overall_signal"], "reasons": reasons, "data": t})
    return flags
