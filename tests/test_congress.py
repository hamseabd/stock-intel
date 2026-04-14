"""Tests for tools/congress.py — cluster detection, signals, sector breakdown."""

import pytest

from tools.congress import detect_clusters, get_sector_breakdown, _add_signals, AMOUNT_RANK


class TestDetectClusters:
    def test_basic_cluster(self, sample_congress_trades):
        clusters = detect_clusters(sample_congress_trades)
        # NVDA has 3 members: Pelosi, Tuberville, Crenshaw
        nvda_cluster = next((c for c in clusters if c["ticker"] == "NVDA"), None)
        assert nvda_cluster is not None
        assert len(nvda_cluster["members"]) == 3
        assert nvda_cluster["direction"] == "buying"

    def test_no_cluster_single_member(self):
        trades = [
            {"member": "John Doe", "ticker": "AAPL", "tx_type": "Purchase", "trade_date": "2026-04-01"},
        ]
        clusters = detect_clusters(trades, min_members=2)
        assert clusters == []

    def test_min_members_threshold(self, sample_congress_trades):
        # With min_members=4, NVDA (3 members) shouldn't qualify
        clusters = detect_clusters(sample_congress_trades, min_members=4)
        nvda = next((c for c in clusters if c["ticker"] == "NVDA"), None)
        assert nvda is None

    def test_selling_direction(self):
        trades = [
            {"member": "A", "ticker": "XYZ", "tx_type": "Sale", "trade_date": "2026-04-01"},
            {"member": "B", "ticker": "XYZ", "tx_type": "Sale", "trade_date": "2026-04-02"},
        ]
        clusters = detect_clusters(trades)
        assert clusters[0]["direction"] == "selling"

    def test_mixed_direction(self):
        trades = [
            {"member": "A", "ticker": "XYZ", "tx_type": "Purchase", "trade_date": "2026-04-01"},
            {"member": "B", "ticker": "XYZ", "tx_type": "Sale", "trade_date": "2026-04-02"},
        ]
        clusters = detect_clusters(trades)
        assert clusters[0]["direction"] == "mixed"

    def test_empty_trades(self):
        assert detect_clusters([]) == []


class TestAddSignals:
    def test_whale_trade(self):
        trade = {"amount": "$1,000,001 - $5,000,000", "committees": [], "ticker": "AAPL"}
        _add_signals(trade)
        assert "whale_trade" in trade["signals"]
        assert "large_trade" in trade["signals"]

    def test_large_trade(self):
        trade = {"amount": "$250,001 - $500,000", "committees": [], "ticker": "AAPL"}
        _add_signals(trade)
        assert "large_trade" in trade["signals"]
        assert "whale_trade" not in trade["signals"]

    def test_small_trade_no_signal(self):
        trade = {"amount": "$1,001 - $15,000", "committees": [], "ticker": "AAPL"}
        _add_signals(trade)
        assert trade["signals"] == []

    def test_committee_relevant(self):
        trade = {"amount": "$50,001 - $100,000", "committees": ["Armed Services"], "ticker": "LMT"}
        _add_signals(trade)
        assert any("committee_relevant" in s for s in trade["signals"])

    def test_intelligence_committee(self):
        trade = {"amount": "$50,001 - $100,000", "committees": ["Intelligence"], "ticker": "RANDOM"}
        _add_signals(trade)
        assert "intelligence_committee" in trade["signals"]

    def test_no_committee_match(self):
        trade = {"amount": "$50,001 - $100,000", "committees": ["Judiciary"], "ticker": "AAPL"}
        _add_signals(trade)
        # No committee match, no large trade
        assert trade["signals"] == []


class TestSectorBreakdown:
    def test_basic(self, sample_congress_trades):
        sectors = get_sector_breakdown(sample_congress_trades)
        assert isinstance(sectors, dict)
        # NVDA is in Commerce, MSFT is in Commerce
        assert "Commerce" in sectors or "Other" in sectors

    def test_empty(self):
        assert get_sector_breakdown([]) == {}

    def test_unknown_ticker(self):
        trades = [{"ticker": "ZZZZZ"}, {"ticker": "YYYYY"}]
        sectors = get_sector_breakdown(trades)
        assert sectors.get("Other", 0) == 2


class TestAmountRank:
    def test_ranks_ordered(self):
        ranks = list(AMOUNT_RANK.values())
        assert ranks == sorted(ranks)

    def test_known_amounts(self):
        assert AMOUNT_RANK["$1,001 - $15,000"] == 1
        assert AMOUNT_RANK["$1,000,001 - $5,000,000"] == 7
        assert AMOUNT_RANK["Over $50,000,000"] == 10
