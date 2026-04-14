"""Unusual options activity detection.

Scans yfinance options chains for anomalies: volume/OI spikes, large premium
concentration, and put/call ratio extremes. No AI — pure math.
"""

import math

import yfinance as yf

from shared.math_utils import is_unusual_flow, calc_premium, put_call_ratio
from shared.config import UNUSUAL_FLOW_VOLUME_RATIO, LARGE_FLOW_PREMIUM
from shared.log import get_logger

logger = get_logger(__name__)


def scan_options_flow(ticker: str) -> dict:
    """Scan all expiries for unusual options activity on a single ticker.

    Returns:
        dict with alerts, put_call_ratio, net_premium, and summary
    """
    logger.info("Scanning options flow", ticker=ticker)
    tkr = yf.Ticker(ticker)
    try:
        expiries = list(tkr.options)
    except Exception:
        logger.error("Failed to fetch options chain", ticker=ticker, exc_info=True)
        return {"ticker": ticker, "error": "Could not fetch options chain."}

    if not expiries:
        return {"ticker": ticker, "alerts": [], "put_call_ratio": 1.0, "net_premium": {"bullish": 0, "bearish": 0}}

    alerts = []
    total_call_vol = 0
    total_put_vol = 0
    bullish_premium = 0.0
    bearish_premium = 0.0

    for exp in expiries[:6]:  # limit to nearest 6 expiries for speed
        try:
            chain = tkr.option_chain(exp)
        except Exception:
            continue

        for opt_type, df in [("call", chain.calls), ("put", chain.puts)]:
            for _, row in df.iterrows():
                _vol = row.get("volume", 0)
                vol = 0 if (_vol is None or (isinstance(_vol, float) and math.isnan(_vol))) else int(_vol)
                _oi = row.get("openInterest", 0)
                oi = 0 if (_oi is None or (isinstance(_oi, float) and math.isnan(_oi))) else int(_oi)
                _bid = row.get("bid", 0)
                bid = 0.0 if (_bid is None or (isinstance(_bid, float) and math.isnan(_bid))) else float(_bid)
                _ask = row.get("ask", 0)
                ask = 0.0 if (_ask is None or (isinstance(_ask, float) and math.isnan(_ask))) else float(_ask)
                mid = (bid + ask) / 2
                strike = float(row["strike"])

                if opt_type == "call":
                    total_call_vol += vol
                else:
                    total_put_vol += vol

                if vol == 0:
                    continue

                premium = calc_premium(mid, vol)

                # Track premium direction
                if opt_type == "call":
                    bullish_premium += premium
                else:
                    bearish_premium += premium

                # Check for unusual activity
                ratio = vol / oi if oi > 0 else float(vol) if vol > 100 else 0
                if is_unusual_flow(vol, oi, UNUSUAL_FLOW_VOLUME_RATIO) or premium >= LARGE_FLOW_PREMIUM:
                    direction = "bullish" if opt_type == "call" else "bearish"
                    alerts.append({
                        "ticker": ticker,
                        "strike": strike,
                        "expiry": exp,
                        "option_type": opt_type,
                        "volume": vol,
                        "open_interest": oi,
                        "volume_oi_ratio": round(ratio, 1),
                        "premium": premium,
                        "direction": direction,
                        "bid": bid,
                        "ask": ask,
                    })

    # Sort by premium descending
    alerts.sort(key=lambda x: x["premium"], reverse=True)

    pcr = put_call_ratio(total_put_vol, total_call_vol)

    return {
        "ticker": ticker,
        "alerts": alerts[:10],  # top 10
        "put_call_ratio": pcr,
        "net_premium": {
            "bullish": round(bullish_premium, 0),
            "bearish": round(bearish_premium, 0),
        },
        "total_call_volume": total_call_vol,
        "total_put_volume": total_put_vol,
        "unusual_count": len(alerts),
    }


def scan_flow_multiple(tickers: list[str]) -> list[dict]:
    """Scan multiple tickers and return only those with unusual activity."""
    results = []
    for ticker in tickers:
        flow = scan_options_flow(ticker)
        if flow.get("alerts"):
            results.append(flow)
    results.sort(key=lambda x: x.get("unusual_count", 0), reverse=True)
    return results
