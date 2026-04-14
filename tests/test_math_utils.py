"""Tests for shared/math_utils.py — pure math, no mocks needed."""

import math
import numpy as np
import pytest

from shared.math_utils import (
    calc_pnl,
    weighted_avg_cost,
    black_scholes,
    days_to_expiry,
    option_recommendation,
    calc_rsi,
    calc_sma,
    calc_ema,
    calc_macd,
    calc_bollinger,
    calc_support_resistance,
    overall_technical_signal,
    is_unusual_flow,
    calc_premium,
    put_call_ratio,
)


# ── P&L ────────────────────────────────────────────────────────────────────

class TestCalcPnl:
    def test_profit(self):
        result = calc_pnl(100, 200.0, 250.0)
        assert result["total_cost"] == 20000.0
        assert result["market_value"] == 25000.0
        assert result["dollar_pnl"] == 5000.0
        assert result["pct_pnl"] == 25.0

    def test_loss(self):
        result = calc_pnl(100, 250.0, 200.0)
        assert result["dollar_pnl"] == -5000.0
        assert result["pct_pnl"] == -20.0

    def test_breakeven(self):
        result = calc_pnl(50, 100.0, 100.0)
        assert result["dollar_pnl"] == 0.0
        assert result["pct_pnl"] == 0.0

    def test_zero_cost_basis(self):
        result = calc_pnl(100, 0.0, 50.0)
        assert result["pct_pnl"] == 0.0  # avoid division by zero

    def test_fractional_shares(self):
        result = calc_pnl(0.5, 100.0, 200.0)
        assert result["total_cost"] == 50.0
        assert result["market_value"] == 100.0


class TestWeightedAvgCost:
    def test_basic(self):
        assert weighted_avg_cost(100, 200.0, 100, 300.0) == 250.0

    def test_add_to_zero(self):
        assert weighted_avg_cost(0, 0.0, 50, 100.0) == 100.0

    def test_zero_new_shares(self):
        assert weighted_avg_cost(100, 200.0, 0, 0.0) == 200.0

    def test_all_zero(self):
        assert weighted_avg_cost(0, 0.0, 0, 0.0) == 0.0


# ── Black-Scholes ──────────────────────────────────────────────────────────

class TestBlackScholes:
    def test_put_price_positive(self):
        result = black_scholes(S=200, K=210, T=0.5, r=0.045, sigma=0.30, option_type="put")
        assert result["price"] > 0
        assert result["delta"] < 0  # puts have negative delta
        assert result["gamma"] > 0
        assert result["vega"] > 0

    def test_call_price_positive(self):
        result = black_scholes(S=200, K=190, T=0.5, r=0.045, sigma=0.30, option_type="call")
        assert result["price"] > 0
        assert result["delta"] > 0  # calls have positive delta

    def test_at_expiry(self):
        # ITM put at expiry
        result = black_scholes(S=190, K=200, T=0, r=0.045, sigma=0.30, option_type="put")
        assert result["price"] == 10  # intrinsic value
        assert result["extrinsic"] == 0.0

    def test_zero_vol(self):
        result = black_scholes(S=190, K=200, T=0.5, r=0.045, sigma=0, option_type="put")
        assert result["price"] == 10  # just intrinsic

    def test_deep_otm_put(self):
        result = black_scholes(S=300, K=200, T=0.1, r=0.045, sigma=0.20, option_type="put")
        assert result["price"] < 1.0  # nearly worthless
        assert abs(result["delta"]) < 0.1

    def test_deep_itm_call(self):
        result = black_scholes(S=300, K=200, T=0.5, r=0.045, sigma=0.20, option_type="call")
        assert result["delta"] > 0.9
        assert result["intrinsic"] == 100.0

    def test_put_call_parity_approx(self):
        """Put-call parity: C - P ≈ S - K*e^(-rT)"""
        S, K, T, r, sigma = 200, 200, 0.5, 0.045, 0.30
        call = black_scholes(S, K, T, r, sigma, "call")
        put = black_scholes(S, K, T, r, sigma, "put")
        lhs = call["price"] - put["price"]
        rhs = S - K * math.exp(-r * T)
        assert abs(lhs - rhs) < 0.01


class TestDaysToExpiry:
    def test_future_date(self):
        # Use a date far enough in the future
        dte = days_to_expiry("2030-12-31")
        assert dte > 0

    def test_past_date(self):
        dte = days_to_expiry("2020-01-01")
        assert dte < 0


class TestOptionRecommendation:
    def test_expired(self):
        rec, reason = option_recommendation(0, True, -0.5, 0.0, -5.0)
        assert rec == "expired"

    def test_itm_2dte(self):
        rec, reason = option_recommendation(2, True, -0.7, 0.50, -5.0)
        assert rec == "close_or_roll"

    def test_otm_2dte(self):
        rec, reason = option_recommendation(2, False, -0.2, 0.05, 5.0)
        assert rec == "let_expire"

    def test_itm_5dte(self):
        rec, reason = option_recommendation(5, True, -0.6, 1.50, -3.0)
        assert rec == "roll_or_close"

    def test_otm_low_extrinsic_5dte(self):
        rec, reason = option_recommendation(5, False, -0.1, 0.05, 8.0)
        assert rec == "let_expire"

    def test_otm_5dte_has_extrinsic(self):
        rec, reason = option_recommendation(5, False, -0.3, 0.50, 5.0)
        assert rec == "hold_or_close"

    def test_high_delta_30dte(self):
        rec, reason = option_recommendation(30, True, -0.65, 3.0, -5.0)
        assert rec == "roll_or_close"

    def test_safe_30dte(self):
        rec, reason = option_recommendation(30, False, -0.2, 2.0, 10.0)
        assert rec == "hold"


# ── Technical Indicators ──────────────────────────────────────────────────

class TestRSI:
    def test_uptrend_high_rsi(self):
        # Steadily rising prices
        prices = np.arange(100, 130, 0.2)
        rsi = calc_rsi(prices, 14)
        assert rsi > 70  # overbought

    def test_downtrend_low_rsi(self):
        # Steadily falling prices
        prices = np.arange(130, 100, -0.2)
        rsi = calc_rsi(prices, 14)
        assert rsi < 30  # oversold

    def test_flat_prices(self):
        prices = np.full(30, 100.0)
        rsi = calc_rsi(prices, 14)
        assert rsi == 100.0  # no losses means avg_loss=0, so RSI=100

    def test_insufficient_data(self):
        prices = np.array([100, 101, 102])
        rsi = calc_rsi(prices, 14)
        assert rsi == 50.0  # default

    def test_all_gains(self):
        prices = np.arange(1, 30)
        rsi = calc_rsi(prices.astype(float), 14)
        assert rsi == 100.0

    def test_rsi_range(self, sample_price_history):
        rsi = calc_rsi(sample_price_history, 14)
        assert 0 <= rsi <= 100


class TestSMA:
    def test_basic(self):
        prices = np.array([10, 20, 30, 40, 50])
        assert calc_sma(prices, 3) == 40.0  # mean of last 3: [30,40,50]

    def test_period_larger_than_data(self):
        prices = np.array([10, 20, 30])
        sma = calc_sma(prices, 50)
        assert sma == 20.0  # mean of all

    def test_single_price(self):
        assert calc_sma(np.array([42.0]), 1) == 42.0


class TestMACD:
    def test_returns_dict_keys(self, sample_price_history):
        result = calc_macd(sample_price_history)
        assert "macd_line" in result
        assert "signal" in result
        assert "histogram" in result

    def test_insufficient_data(self):
        result = calc_macd(np.array([100, 101, 102]))
        assert result["macd_line"] == 0.0

    def test_histogram_is_diff(self, sample_price_history):
        result = calc_macd(sample_price_history)
        expected = round(result["macd_line"] - result["signal"], 4)
        assert result["histogram"] == expected


class TestBollinger:
    def test_basic(self):
        prices = np.full(20, 100.0)  # flat
        bb = calc_bollinger(prices, 20, 2.0)
        assert bb["middle"] == 100.0
        assert bb["upper"] == 100.0  # no std dev
        assert bb["lower"] == 100.0

    def test_volatile(self):
        prices = np.array([90, 110] * 10)  # oscillating
        bb = calc_bollinger(prices, 20, 2.0)
        assert bb["upper"] > bb["middle"]
        assert bb["lower"] < bb["middle"]

    def test_short_data(self):
        prices = np.array([100, 110, 120])
        bb = calc_bollinger(prices, 20)
        assert bb["middle"] == round(np.mean(prices), 2)


class TestSupportResistance:
    def test_basic(self):
        prices = np.array([95, 100, 105, 110, 108, 102, 98])
        sr = calc_support_resistance(prices, 5)
        assert sr["support"] <= sr["resistance"]

    def test_flat(self):
        prices = np.full(20, 100.0)
        sr = calc_support_resistance(prices, 10)
        assert sr["support"] == 100.0
        assert sr["resistance"] == 100.0


class TestOverallSignal:
    def test_bullish(self):
        assert overall_technical_signal(55, 0.5, 210, 200, 190) == "bullish"

    def test_bearish(self):
        assert overall_technical_signal(25, -0.5, 180, 200, 210) == "bearish"

    def test_neutral(self):
        # RSI 50 (+0.5), MACD<0 (-1), price>sma50 (+0.5), price<sma200 (-0.5) = -0.5 → neutral
        assert overall_technical_signal(50, -0.1, 205, 200, 210) == "neutral"


# ── Options Flow ──────────────────────────────────────────────────────────

class TestUnusualFlow:
    def test_high_ratio(self):
        assert is_unusual_flow(5000, 1000, 5.0) is True

    def test_low_ratio(self):
        assert is_unusual_flow(100, 1000, 5.0) is False

    def test_zero_oi_high_volume(self):
        assert is_unusual_flow(5000, 0, 5.0) is True

    def test_zero_oi_low_volume(self):
        assert is_unusual_flow(500, 0, 5.0) is False

    def test_exact_threshold(self):
        assert is_unusual_flow(5000, 1000, 5.0) is True


class TestCalcPremium:
    def test_basic(self):
        assert calc_premium(2.50, 100) == 25000.0  # 2.50 * 100 * 100

    def test_zero_volume(self):
        assert calc_premium(5.0, 0) == 0.0


class TestPutCallRatio:
    def test_basic(self):
        assert put_call_ratio(5000, 10000) == 0.5

    def test_zero_calls(self):
        assert put_call_ratio(5000, 0) == 999.0

    def test_both_zero(self):
        assert put_call_ratio(0, 0) == 1.0

    def test_equal(self):
        assert put_call_ratio(1000, 1000) == 1.0
