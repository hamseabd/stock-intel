"""Tests for scanners — alert generation and thresholds."""

import pytest
from unittest.mock import patch, MagicMock


class TestPriceScanner:
    @patch("scanners.price_scanner.queue_alert")
    @patch("scanners.price_scanner.update_dashboard")
    @patch("scanners.price_scanner.calculate_movers")
    @patch("scanners.price_scanner.get_positions")
    @patch("scanners.price_scanner.fetch_prices")
    @patch("scanners.price_scanner.get_price_alerts")
    def test_threshold_alert_triggered(self, mock_alerts, mock_prices, mock_pos,
                                       mock_movers, mock_dash, mock_queue):
        from scanners.price_scanner import run_price_scan

        mock_alerts.return_value = [
            {"ticker": "AMZN", "direction": "above", "target_price": 200.0}
        ]
        mock_prices.return_value = {"AMZN": 205.0}
        mock_pos.return_value = []
        mock_movers.return_value = []

        result = run_price_scan()
        assert result["alerts_sent"] >= 1
        mock_queue.assert_called()

    @patch("scanners.price_scanner.queue_alert")
    @patch("scanners.price_scanner.update_dashboard")
    @patch("scanners.price_scanner.calculate_movers")
    @patch("scanners.price_scanner.get_positions")
    @patch("scanners.price_scanner.fetch_prices")
    @patch("scanners.price_scanner.get_price_alerts")
    def test_threshold_not_triggered(self, mock_alerts, mock_prices, mock_pos,
                                      mock_movers, mock_dash, mock_queue):
        from scanners.price_scanner import run_price_scan

        mock_alerts.return_value = [
            {"ticker": "AMZN", "direction": "above", "target_price": 200.0}
        ]
        mock_prices.return_value = {"AMZN": 195.0}
        mock_pos.return_value = []
        mock_movers.return_value = []

        result = run_price_scan()
        assert result["alerts_sent"] == 0

    @patch("scanners.price_scanner.queue_alert")
    @patch("scanners.price_scanner.update_dashboard")
    @patch("scanners.price_scanner.calculate_movers")
    @patch("scanners.price_scanner.get_positions")
    @patch("scanners.price_scanner.fetch_prices")
    @patch("scanners.price_scanner.get_price_alerts")
    def test_big_mover_alert(self, mock_alerts, mock_prices, mock_pos,
                              mock_movers, mock_dash, mock_queue):
        from scanners.price_scanner import run_price_scan

        mock_alerts.return_value = []
        mock_pos.return_value = [{"position_type": "shares", "ticker": "AMD", "shares": 200, "cost_basis": 222}]
        mock_movers.return_value = [{"ticker": "AMD", "price": 155.0, "change_pct": -5.2}]

        result = run_price_scan()
        assert result["alerts_sent"] >= 1


class TestEarningsScanner:
    @patch("scanners.earnings_scanner.queue_alert")
    @patch("scanners.earnings_scanner.fetch_earnings")
    @patch("scanners.earnings_scanner.get_all_scan_tickers")
    def test_alerts_on_key_days(self, mock_tickers, mock_earnings, mock_queue):
        from scanners.earnings_scanner import run_earnings_scan

        mock_tickers.return_value = ["AMD"]
        mock_earnings.return_value = [{"ticker": "AMD", "days_away": 7, "next_earnings_date": "2026-04-21"}]

        result = run_earnings_scan()
        assert result["alerts_sent"] == 1
        mock_queue.assert_called_once()

    @patch("scanners.earnings_scanner.queue_alert")
    @patch("scanners.earnings_scanner.fetch_earnings")
    @patch("scanners.earnings_scanner.get_all_scan_tickers")
    def test_no_alert_on_non_key_days(self, mock_tickers, mock_earnings, mock_queue):
        from scanners.earnings_scanner import run_earnings_scan

        mock_tickers.return_value = ["AMD"]
        mock_earnings.return_value = [{"ticker": "AMD", "days_away": 10, "next_earnings_date": "2026-04-24"}]

        result = run_earnings_scan()
        assert result["alerts_sent"] == 0

    @patch("scanners.earnings_scanner.queue_alert")
    @patch("scanners.earnings_scanner.fetch_earnings")
    @patch("scanners.earnings_scanner.get_all_scan_tickers")
    def test_no_tickers(self, mock_tickers, mock_earnings, mock_queue):
        from scanners.earnings_scanner import run_earnings_scan
        mock_tickers.return_value = []
        result = run_earnings_scan()
        assert result["alerts_sent"] == 0


class TestNewsScanner:
    @patch("scanners.news_scanner.queue_alert")
    @patch("scanners.news_scanner.fetch_news_multiple")
    @patch("scanners.news_scanner.get_all_scan_tickers")
    def test_urgent_keyword_triggers_alert(self, mock_tickers, mock_news, mock_queue):
        from scanners.news_scanner import run_news_scan

        mock_tickers.return_value = ["AMZN"]
        mock_news.return_value = {
            "AMZN": [{"title": "Amazon faces SEC investigation", "published": "2026-04-14T08:00:00"}]
        }
        result = run_news_scan()
        assert result["alerts_sent"] == 1

    @patch("scanners.news_scanner.queue_alert")
    @patch("scanners.news_scanner.fetch_news_multiple")
    @patch("scanners.news_scanner.get_all_scan_tickers")
    def test_normal_headline_no_alert(self, mock_tickers, mock_news, mock_queue):
        from scanners.news_scanner import run_news_scan

        mock_tickers.return_value = ["AMZN"]
        mock_news.return_value = {
            "AMZN": [{"title": "Amazon Prime Day dates announced", "published": "2026-04-14T08:00:00"}]
        }
        result = run_news_scan()
        assert result["alerts_sent"] == 0


class TestCongressScanner:
    @patch("scanners.congress_scanner.update_dashboard")
    @patch("scanners.congress_scanner.queue_alert")
    @patch("scanners.congress_scanner.get_sector_breakdown")
    @patch("scanners.congress_scanner.detect_clusters")
    @patch("scanners.congress_scanner.store_trades")
    @patch("scanners.congress_scanner.write_raw_data")
    @patch("scanners.congress_scanner.get_positions")
    @patch("scanners.congress_scanner.scrape_capitol_trades")
    def test_alerts_on_held_ticker(self, mock_scrape, mock_pos, mock_raw,
                                    mock_store, mock_clusters, mock_sectors,
                                    mock_queue, mock_dash):
        from scanners.congress_scanner import run_congress_scan

        mock_scrape.return_value = [
            {"member": "Pelosi", "party": "D", "ticker": "AMZN", "tx_type": "Purchase",
             "amount": "$500,001 - $1,000,000", "trade_date": "2026-04-10",
             "filing_date": "2026-04-12", "signals": ["large_trade"]}
        ]
        mock_pos.return_value = [{"ticker": "AMZN", "position_type": "shares"}]
        mock_store.return_value = 1
        mock_clusters.return_value = []
        mock_sectors.return_value = {}

        result = run_congress_scan()
        assert result["alerts_sent"] >= 1

    @patch("scanners.congress_scanner.update_dashboard")
    @patch("scanners.congress_scanner.queue_alert")
    @patch("scanners.congress_scanner.get_sector_breakdown")
    @patch("scanners.congress_scanner.detect_clusters")
    @patch("scanners.congress_scanner.store_trades")
    @patch("scanners.congress_scanner.write_raw_data")
    @patch("scanners.congress_scanner.get_positions")
    @patch("scanners.congress_scanner.scrape_capitol_trades")
    def test_no_trades_scraped(self, mock_scrape, mock_pos, mock_raw,
                                mock_store, mock_clusters, mock_sectors,
                                mock_queue, mock_dash):
        from scanners.congress_scanner import run_congress_scan

        mock_scrape.return_value = []
        result = run_congress_scan()
        assert result["scraped"] == 0
        assert result["alerts_sent"] == 0
