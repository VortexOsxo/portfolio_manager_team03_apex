from decimal import Decimal
from unittest.mock import patch

import mysql.connector.errors
import pandas as pd
import pytest

from flaskr.services import database


@pytest.fixture(autouse=True)
def clear_performance_cache():
    # _PERFORMANCE_CACHE is module-level and keyed by (start_date, end_date);
    # tests in this file reuse the same date strings, so a hit from one test
    # would otherwise be served to the next.
    database.clear_performance_cache()
    yield
    database.clear_performance_cache()


class TestSearchRoute:
    @patch("flaskr.blueprints.stocks_bp.search_stocks")
    def test_returns_search_results(self, mock_search, client):
        mock_search.return_value = [{"ticker": "AAPL", "name": "Apple Inc."}]

        response = client.get("/stocks/search?q=apple")

        assert response.status_code == 200
        assert response.get_json() == [{"ticker": "AAPL", "name": "Apple Inc."}]
        mock_search.assert_called_once_with("apple")


class TestGetHoldingsRoute:
    @patch("flaskr.blueprints.stocks_bp.get_transactions")
    def test_returns_holdings_enriched_with_live_price(self, mock_get_transactions, client, mock_yahoo):
        mock_get_transactions.return_value = [
            {"tr_id": 1, "ticker": "AAPL", "amount": 10, "cost_basis": 100.0, "transaction_date": "2026-01-01"},
        ]

        response = client.get("/stocks/")

        assert response.status_code == 200
        body = response.get_json()
        assert body["AAPL"]["amount"] == 10
        assert body["AAPL"]["current_price"] == 150.0  # mock_yahoo's default

    @patch("flaskr.blueprints.stocks_bp.get_transactions")
    def test_no_transactions_returns_empty_object(self, mock_get_transactions, client):
        mock_get_transactions.return_value = []

        response = client.get("/stocks/")

        assert response.status_code == 200
        assert response.get_json() == {}

    @patch("flaskr.blueprints.stocks_bp.get_transactions")
    def test_yahoo_failure_returns_500_with_json_error(
        self, mock_get_transactions, client, mock_yahoo
    ):
        mock_get_transactions.return_value = [
            {"tr_id": 1, "ticker": "AAPL", "amount": 10, "cost_basis": 100.0, "transaction_date": "2026-01-01"},
        ]
        mock_yahoo.return_value.get_info.side_effect = RuntimeError("yahoo down")

        response = client.get("/stocks/")

        assert response.status_code == 500
        assert response.get_json() == {"error": "yahoo down"}


class TestGetQuoteRoute:
    def test_returns_the_quote_for_any_ticker(self, client, mock_yahoo):
        response = client.get("/stocks/quote/AAPL")

        assert response.status_code == 200
        assert response.get_json()["company_name"] == "Apple Inc."

    def test_unknown_ticker_returns_404(self, client, mock_yahoo):
        mock_yahoo.return_value.get_info.return_value = {
            "stock_ticker": "NOTREAL",
            "company_name": None,
            "current_price": None,
            "day_change": None,
            "day_change_pct": None,
        }

        response = client.get("/stocks/quote/NOTREAL")

        assert response.status_code == 404
        assert response.get_json() == {"error": 'No quote found for "NOTREAL"'}

    def test_yahoo_failure_returns_500_with_json_error(self, client, mock_yahoo):
        mock_yahoo.return_value.get_info.side_effect = RuntimeError("yahoo down")

        response = client.get("/stocks/quote/AAPL")

        assert response.status_code == 500
        assert response.get_json() == {"error": "yahoo down"}


class TestGetSummaryRoute:
    @patch("flaskr.blueprints.stocks_bp.get_account_balance")
    @patch("flaskr.blueprints.stocks_bp.get_transactions")
    def test_returns_aggregated_totals(self, mock_get_transactions, mock_get_balance, client, mock_yahoo):
        mock_get_transactions.return_value = [
            {"tr_id": 1, "ticker": "AAPL", "amount": 10, "cost_basis": 100.0, "transaction_date": "2026-01-01"},
        ]
        mock_get_balance.return_value = Decimal("29000.00")

        response = client.get("/stocks/summary")

        assert response.status_code == 200
        body = response.get_json()
        assert body["cash_balance"] == 29000.0
        assert body["net_worth"] == pytest.approx(29000.0 + 10 * 150.0)

    @patch("flaskr.blueprints.stocks_bp.get_account_balance")
    @patch("flaskr.blueprints.stocks_bp.get_transactions")
    def test_missing_account_returns_500_with_json_error(
        self, mock_get_transactions, mock_get_balance, client
    ):
        mock_get_transactions.return_value = []
        mock_get_balance.side_effect = ValueError("Account 1 not found")

        response = client.get("/stocks/summary")

        assert response.status_code == 500
        assert response.get_json() == {"error": "Account 1 not found"}


class TestPerformanceRoute:
    def test_requires_both_dates(self, client):
        response = client.get("/stocks/performance?start_date=2026-01-01")

        assert response.status_code == 400
        assert "required" in response.get_json()["error"]

    @patch("flaskr.services.database.get_account_balance")
    @patch("flaskr.services.database.YahooFinanceStock.get_daily_values_for_tickers")
    @patch("flaskr.services.database.get_transactions")
    def test_returns_dates_and_performances(self, mock_get_transactions, mock_get_daily_values, mock_get_account_balance, client):
        mock_get_account_balance.return_value = Decimal("30000.00")
        mock_get_transactions.return_value = [
            {"tr_id": 1, "type": "buy", "ticker": "AAPL", "amount": 2, "cost_basis": 100.0, "transaction_date": "2026-01-02"},
        ]
        mock_get_daily_values.return_value = {
            "AAPL": {"2026-01-02": 100.0},
            "^GSPC": {"2026-01-02": 1.0},
        }

        response = client.get("/stocks/performance?start_date=2026-01-01&end_date=2026-01-05")

        assert response.status_code == 200
        assert response.get_json()["dates"] == ["2026-01-02"]
        assert response.get_json()["equity"] == [200.0]
        assert "cash" in response.get_json()

    def test_malformed_date_returns_400(self, client):
        # _parse_date_range now rejects this before get_portfolio_performance
        # is ever called, instead of letting a strptime failure deep inside
        # YahooFinanceStock surface as a 500.
        response = client.get("/stocks/performance?start_date=2026-01-01&end_date=not-a-date")

        assert response.status_code == 400
        assert response.get_json() == {"error": "start_date and end_date must be in YYYY-MM-DD format"}


class TestSingleTickerPerformanceRoute:
    def test_requires_both_dates(self, client):
        response = client.get("/stocks/performance/AAPL?start_date=2026-01-01")

        assert response.status_code == 400
        assert "required" in response.get_json()["error"]

    @patch("flaskr.services.database.YahooFinanceStock")
    def test_returns_dates_and_performances(self, mock_stock_cls, client):
        mock_stock_cls.get_market_trading_days.return_value = ["2026-01-02"]
        mock_stock_cls.return_value.get_daily_values.return_value = {"2026-01-02": 150.0}

        response = client.get("/stocks/performance/AAPL?start_date=2026-01-01&end_date=2026-01-05")

        assert response.status_code == 200
        assert response.get_json() == {"dates": ["2026-01-02"], "equity": [150.0]}

    def test_malformed_date_returns_400(self, client):
        response = client.get("/stocks/performance/AAPL?start_date=2026-01-01&end_date=not-a-date")

        assert response.status_code == 400
        assert response.get_json() == {"error": "start_date and end_date must be in YYYY-MM-DD format"}

    @patch("flaskr.yahoo_finance.yf.Ticker")
    def test_reversed_range_crashes_on_a_non_datetime_index(self, mock_ticker_cls, client):
        # Real yfinance rejects start > end and comes back with an empty
        # DataFrame carrying a plain Index rather than a DatetimeIndex, so
        # `.strftime()` in get_market_trading_days blows up. Reproduced here
        # without hitting the network by mocking yf.Ticker directly.
        mock_ticker_cls.return_value.history.return_value = pd.DataFrame({"Close": []})

        response = client.get("/stocks/performance/AAPL?start_date=2026-01-10&end_date=2026-01-01")

        assert response.status_code == 500
        assert "has no attribute 'strftime'" in response.get_json()["error"]


class TestBuyRoute:
    @patch("flaskr.blueprints.stocks_bp.buy_holding")
    def test_happy_path_calls_service_and_returns_201(self, mock_buy, client):
        response = client.post(
            "/stocks/buy",
            json={"ticker": "AAPL", "amount": 10, "cost_basis": 150.0, "transaction_date": "2026-01-01"},
        )

        assert response.status_code == 201
        mock_buy.assert_called_once_with("AAPL", 10, 150.0, "2026-01-01")

    def test_missing_ticker_or_amount_returns_400(self, client):
        response = client.post("/stocks/buy", json={"ticker": "AAPL"})

        assert response.status_code == 400

    def test_no_body_returns_415(self, client):
        # request.get_json() with no Content-Type raises UnsupportedMediaType
        # in this Flask version -- not the AttributeError one might expect
        # from calling .get() on None.
        response = client.post("/stocks/buy")

        assert response.status_code == 415

    def test_non_numeric_amount_returns_400(self, client):
        # decimal.InvalidOperation from Decimal(str("abc")) is now caught and
        # translated to a clean 400 instead of crashing.
        response = client.post(
            "/stocks/buy", json={"ticker": "AAPL", "amount": "abc", "cost_basis": 100}
        )

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be a number"}

    def test_zero_amount_returns_400(self, client):
        response = client.post("/stocks/buy", json={"ticker": "AAPL", "amount": 0, "cost_basis": 100})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be greater than zero"}

    def test_negative_cost_basis_returns_400(self, client):
        response = client.post("/stocks/buy", json={"ticker": "AAPL", "amount": 1, "cost_basis": -50})

        assert response.status_code == 400
        assert response.get_json() == {"error": "cost_basis must be greater than zero"}

    def test_ticker_longer_than_ten_chars_returns_400(self, client):
        # The `transactions.ticker` column is VARCHAR(10).
        response = client.post(
            "/stocks/buy", json={"ticker": "WAYTOOLONGTICKER", "amount": 1, "cost_basis": 50}
        )

        assert response.status_code == 400
        assert "10 characters" in response.get_json()["error"]

    @patch("flaskr.blueprints.stocks_bp.buy_holding")
    def test_integrity_error_returns_400_with_empty_body(self, mock_buy, client):
        mock_buy.side_effect = mysql.connector.errors.IntegrityError("duplicate")

        response = client.post(
            "/stocks/buy", json={"ticker": "AAPL", "amount": 1, "cost_basis": 100}
        )

        assert response.status_code == 400
        assert response.get_data(as_text=True) == ""

    @patch("flaskr.blueprints.stocks_bp.buy_holding")
    def test_insufficient_cash_returns_400_with_json_error(self, mock_buy, client):
        mock_buy.side_effect = ValueError("Insufficient cash: ...")

        response = client.post(
            "/stocks/buy", json={"ticker": "AAPL", "amount": 1000, "cost_basis": 100}
        )

        assert response.status_code == 400
        assert "Insufficient cash" in response.get_json()["error"]


class TestSellRoute:
    @patch("flaskr.blueprints.stocks_bp.sell_holding")
    def test_happy_path_calls_service_and_returns_201(self, mock_sell, client):
        response = client.post(
            "/stocks/sell",
            json={"ticker": "AAPL", "amount": 5, "cost_basis": 160.0, "transaction_date": "2026-01-03"},
        )

        assert response.status_code == 201
        mock_sell.assert_called_once_with("AAPL", 5, 160.0, "2026-01-03")

    def test_missing_ticker_or_amount_returns_400(self, client):
        response = client.post("/stocks/sell", json={"amount": 5})

        assert response.status_code == 400

    def test_no_body_returns_415(self, client):
        response = client.post("/stocks/sell")

        assert response.status_code == 415

    def test_zero_amount_returns_400(self, client):
        # Checked before the holdings lookup, so no DB access happens.
        response = client.post("/stocks/sell", json={"ticker": "AAPL", "amount": 0, "cost_basis": 100})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be greater than zero"}

    def test_ticker_longer_than_ten_chars_returns_400(self, client):
        response = client.post(
            "/stocks/sell", json={"ticker": "WAYTOOLONGTICKER", "amount": 1, "cost_basis": 50}
        )

        assert response.status_code == 400
        assert "10 characters" in response.get_json()["error"]

    @patch("flaskr.services.database.get_holding_amount")
    def test_negative_cost_basis_returns_400(self, mock_get_amount, client):
        mock_get_amount.return_value = 10

        response = client.post("/stocks/sell", json={"ticker": "AAPL", "amount": 1, "cost_basis": -50})

        assert response.status_code == 400
        assert response.get_json() == {"error": "cost_basis must be greater than zero"}

    @patch("flaskr.blueprints.stocks_bp.sell_holding")
    def test_selling_more_than_owned_returns_400_with_json_error(self, mock_sell, client):
        mock_sell.side_effect = ValueError("Cannot sell 5 shares of AAPL; only 3 available")

        response = client.post(
            "/stocks/sell", json={"ticker": "AAPL", "amount": 5, "cost_basis": 160.0}
        )

        assert response.status_code == 400
        assert "only 3 available" in response.get_json()["error"]

    def test_non_numeric_amount_returns_400(self, client):
        # decimal.InvalidOperation from Decimal(str("abc")) is now caught and
        # translated to a clean 400 instead of crashing, same as the buy route.
        response = client.post(
            "/stocks/sell", json={"ticker": "AAPL", "amount": "abc", "cost_basis": 100}
        )

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be a number"}
