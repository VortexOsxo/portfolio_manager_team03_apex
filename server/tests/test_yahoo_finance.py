from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from flaskr import yahoo_finance
from flaskr.yahoo_finance import YahooFinanceStock, search_stocks


@pytest.fixture(autouse=True)
def clear_info_cache():
    # _INFO_CACHE is module-level and keyed by ticker, so a cached value from
    # one test would otherwise leak into the next test that uses the same ticker.
    yahoo_finance._INFO_CACHE.clear()
    yield
    yahoo_finance._INFO_CACHE.clear()


class TestGetInfo:
    @patch("flaskr.yahoo_finance.yf.Ticker")
    def test_maps_yahoo_fields(self, mock_ticker_cls):
        mock_ticker_cls.return_value.info = {
            "longName": "Apple Inc.",
            "currentPrice": 150.0,
            "regularMarketChange": 2.5,
            "regularMarketChangePercent": 1.7,
        }

        info = YahooFinanceStock("AAPL").get_info()

        assert info == {
            "stock_ticker": "AAPL",
            "company_name": "Apple Inc.",
            "current_price": 150.0,
            "day_change": 2.5,
            "day_change_pct": 1.7,
        }

    @patch("flaskr.yahoo_finance.yf.Ticker")
    def test_falls_back_to_short_name_and_regular_market_price(self, mock_ticker_cls):
        mock_ticker_cls.return_value.info = {
            "shortName": "Apple",
            "regularMarketPrice": 149.0,
        }

        info = YahooFinanceStock("AAPL").get_info()

        assert info["company_name"] == "Apple"
        assert info["current_price"] == 149.0

    @patch("flaskr.yahoo_finance.yf.Ticker")
    def test_second_call_within_ttl_is_served_from_cache(self, mock_ticker_cls):
        mock_ticker_cls.return_value.info = {"currentPrice": 100.0}
        YahooFinanceStock("AAPL").get_info()

        # A later instance for the same ticker would normally see this new price,
        # but the cache should still hold the previous value within the TTL.
        mock_ticker_cls.return_value.info = {"currentPrice": 200.0}
        info = YahooFinanceStock("AAPL").get_info()

        assert info["current_price"] == 100.0

    @patch("flaskr.yahoo_finance.yf.Ticker")
    def test_expired_cache_entry_is_refetched(self, mock_ticker_cls):
        mock_ticker_cls.return_value.info = {"currentPrice": 100.0}
        stock = YahooFinanceStock("AAPL")
        stock.get_info()

        # Force the cached entry to look expired.
        cached_info, _ = yahoo_finance._INFO_CACHE["AAPL"]
        yahoo_finance._INFO_CACHE["AAPL"] = (cached_info, 0)

        mock_ticker_cls.return_value.info = {"currentPrice": 200.0}
        info = YahooFinanceStock("AAPL").get_info()

        assert info["current_price"] == 200.0


class TestGetPriceOnDate:
    @patch("flaskr.yahoo_finance.yf.Ticker")
    def test_returns_close_price_for_string_date(self, mock_ticker_cls):
        mock_ticker_cls.return_value.history.return_value = pd.DataFrame({"Close": [123.45]})

        price = YahooFinanceStock("AAPL").get_price_on_date("2024-01-02")

        assert price == 123.45
        called_start = mock_ticker_cls.return_value.history.call_args.kwargs["start"]
        assert called_start == datetime(2024, 1, 2)

    @patch("flaskr.yahoo_finance.yf.Ticker")
    def test_returns_none_when_market_was_closed(self, mock_ticker_cls):
        mock_ticker_cls.return_value.history.return_value = pd.DataFrame({"Close": []})

        price = YahooFinanceStock("AAPL").get_price_on_date("2024-01-06")  # a Saturday

        assert price is None


class TestSearchStocks:
    @patch("flaskr.yahoo_finance.yf.Search")
    def test_filters_to_equities_and_maps_fields(self, mock_search_cls):
        mock_search_cls.return_value.quotes = [
            {"symbol": "AAPL", "shortname": "Apple Inc.", "quoteType": "EQUITY"},
            {"symbol": "AAPLW", "shortname": "Apple Warrant", "quoteType": "OPTION"},
        ]

        results = search_stocks("apple")

        assert results == [{"ticker": "AAPL", "name": "Apple Inc."}]

    def test_blank_query_returns_empty_without_calling_yahoo(self):
        assert search_stocks("   ") == []

    @patch("flaskr.yahoo_finance.yf.Search")
    def test_yahoo_error_returns_empty_list(self, mock_search_cls):
        mock_search_cls.side_effect = RuntimeError("network down")

        assert search_stocks("apple") == []

    @patch("flaskr.yahoo_finance.yf.Search")
    def test_falls_back_to_symbol_when_no_name_present(self, mock_search_cls):
        mock_search_cls.return_value.quotes = [{"symbol": "AAPL", "quoteType": "EQUITY"}]

        results = search_stocks("aapl")

        assert results == [{"ticker": "AAPL", "name": "AAPL"}]
