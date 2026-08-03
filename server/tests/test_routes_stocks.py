from decimal import Decimal
from unittest.mock import patch

import mysql.connector.errors
import pandas as pd
import pytest

from flaskr.services import database

ACCOUNT_ID = 1


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_performance_cache():
    # _PERFORMANCE_CACHE is module-level and keyed by (account_id, start_date, end_date);
    # tests in this file reuse the same date strings, so a hit from one test
    # would otherwise be served to the next.
    database.clear_performance_cache(ACCOUNT_ID)
    yield
    database.clear_performance_cache(ACCOUNT_ID)


@pytest.fixture()
def client(app):
    """Test client that automatically attaches a valid JWT for ACCOUNT_ID."""
    from flask_jwt_extended import create_access_token

    with app.app_context():
        token = create_access_token(identity=str(ACCOUNT_ID))

    test_client = app.test_client()
    # Wrap the standard request methods to inject the Authorization header.
    _orig_open = test_client.open

    def open_with_jwt(*args, **kwargs):
        headers = kwargs.pop("headers", {})
        if isinstance(headers, dict):
            headers = {**headers, "Authorization": f"Bearer {token}"}
        return _orig_open(*args, headers=headers, **kwargs)

    test_client.open = open_with_jwt
    return test_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

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
        mock_get_transactions.assert_called_once_with(ACCOUNT_ID)

    @patch("flaskr.blueprints.stocks_bp.get_transactions")
    def test_no_transactions_returns_empty_object(self, mock_get_transactions, client):
        mock_get_transactions.return_value = []

        response = client.get("/stocks/")

        assert response.status_code == 200
        assert response.get_json() == {}

    @patch("flaskr.blueprints.stocks_bp.get_transactions")
    def test_yahoo_failure_surfaces_as_a_bare_500_not_a_json_error(
        self, mock_get_transactions, client, mock_yahoo
    ):
        # _build_holdings has no try/except around the Yahoo call, unlike the
        # JSON-error pattern used by /stocks/performance. Documents current
        # behavior, doesn't fix it.
        mock_get_transactions.return_value = [
            {"tr_id": 1, "ticker": "AAPL", "amount": 10, "cost_basis": 100.0, "transaction_date": "2026-01-01"},
        ]
        mock_yahoo.return_value.get_info.side_effect = RuntimeError("yahoo down")

        response = client.get("/stocks/")

        assert response.status_code == 500
        assert response.get_json() is None  # HTML error page, not a JSON envelope


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
        mock_get_balance.assert_called_once_with(ACCOUNT_ID)

    @patch("flaskr.blueprints.stocks_bp.get_account_balance")
    @patch("flaskr.blueprints.stocks_bp.get_transactions")
    def test_missing_account_surfaces_as_a_bare_500_not_a_json_error(
        self, mock_get_transactions, mock_get_balance, client
    ):
        # Same gap as GET /stocks/: no try/except around get_account_balance,
        # unlike /stocks/buy and /sell, which do catch ValueError cleanly.
        mock_get_transactions.return_value = []
        mock_get_balance.side_effect = ValueError(f"Account {ACCOUNT_ID} not found")

        response = client.get("/stocks/summary")

        assert response.status_code == 500
        assert response.get_json() is None


class TestPerformanceRoute:
    def test_requires_both_dates(self, client):
        response = client.get("/stocks/performance?start_date=2026-01-01")

        assert response.status_code == 400
        assert "required" in response.get_json()["error"]

    @patch("flaskr.services.database.YahooFinanceStock.get_daily_values_for_tickers")
    @patch("flaskr.services.database.get_transactions")
    def test_returns_dates_and_performances(self, mock_get_transactions, mock_get_daily_values, client):
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

    @patch("flaskr.services.database.get_transactions")
    def test_malformed_date_returns_500_with_a_json_error(self, mock_get_transactions, client):
        # No date-format validation before the string reaches
        # datetime.strptime deep inside YahooFinanceStock -- it raises, and
        # the route's blanket except turns it into a 500 (not a 400).
        mock_get_transactions.return_value = [
            {"tr_id": 1, "type": "buy", "ticker": "AAPL", "amount": 2, "cost_basis": 100.0, "transaction_date": "2026-01-02"},
        ]

        response = client.get("/stocks/performance?start_date=2026-01-01&end_date=not-a-date")

        assert response.status_code == 500
        assert "does not match format" in response.get_json()["error"]


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

    def test_malformed_date_returns_500_with_a_json_error(self, client):
        # Unlike the portfolio-wide route, this one has a doubled/nested
        # try/except -- but the inner except still catches this and returns
        # the same 500 + JSON error shape, not the outer bare "" 400.
        response = client.get("/stocks/performance/AAPL?start_date=2026-01-01&end_date=not-a-date")

        assert response.status_code == 500
        assert "does not match format" in response.get_json()["error"]

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
        mock_buy.assert_called_once_with(ACCOUNT_ID, "AAPL", 10, 150.0, "2026-01-01")

    def test_missing_ticker_or_amount_returns_400(self, client):
        response = client.post("/stocks/buy", json={"ticker": "AAPL"})

        assert response.status_code == 400

    def test_no_body_returns_415(self, client):
        # request.get_json() with no Content-Type raises UnsupportedMediaType
        # in this Flask version -- not the AttributeError one might expect
        # from calling .get() on None.
        response = client.post("/stocks/buy")

        assert response.status_code == 415

    def test_non_numeric_amount_crashes_with_500(self, client, mock_db_conn):
        # decimal.InvalidOperation from Decimal(str("abc")) isn't caught by
        # the route's except IntegrityError / except ValueError.
        response = client.post(
            "/stocks/buy", json={"ticker": "AAPL", "amount": "abc", "cost_basis": 100}
        )

        assert response.status_code == 500

    def test_zero_amount_is_silently_accepted(self, client, mock_db_conn):
        mock_db_conn.return_value.cursor.return_value.fetchone.return_value = (Decimal("30000.00"),)

        response = client.post("/stocks/buy", json={"ticker": "AAPL", "amount": 0, "cost_basis": 100})

        assert response.status_code == 201

    def test_negative_cost_basis_is_silently_accepted(self, client, mock_db_conn):
        mock_db_conn.return_value.cursor.return_value.fetchone.return_value = (Decimal("30000.00"),)

        response = client.post("/stocks/buy", json={"ticker": "AAPL", "amount": 1, "cost_basis": -50})

        assert response.status_code == 201

    def test_ticker_longer_than_ten_chars_is_not_rejected_at_the_app_layer(self, client, mock_db_conn):
        # The `transactions.ticker` column is VARCHAR(10); the app never
        # checks length before inserting. Whether this actually errors
        # depends on the real DB/SQL mode, which a mocked connection can't
        # show -- this only documents that nothing stops it at this layer.
        mock_db_conn.return_value.cursor.return_value.fetchone.return_value = (Decimal("30000.00"),)

        response = client.post(
            "/stocks/buy", json={"ticker": "WAYTOOLONGTICKER", "amount": 1, "cost_basis": 50}
        )

        assert response.status_code == 201

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
        mock_sell.assert_called_once_with(ACCOUNT_ID, "AAPL", 5, 160.0, "2026-01-03")

    def test_missing_ticker_or_amount_returns_400(self, client):
        response = client.post("/stocks/sell", json={"amount": 5})

        assert response.status_code == 400

    def test_no_body_returns_415(self, client):
        response = client.post("/stocks/sell")

        assert response.status_code == 415

    @patch("flaskr.blueprints.stocks_bp.sell_holding")
    def test_selling_more_than_owned_returns_400_with_json_error(self, mock_sell, client):
        mock_sell.side_effect = ValueError("Cannot sell 5 shares of AAPL; only 3 available")

        response = client.post(
            "/stocks/sell", json={"ticker": "AAPL", "amount": 5, "cost_basis": 160.0}
        )

        assert response.status_code == 400
        assert "only 3 available" in response.get_json()["error"]

    def test_non_numeric_amount_crashes_with_500(self, client):
        # Decimal(str("abc")) raises decimal.InvalidOperation before
        # sell_holding ever touches the DB, same gap as the buy route.
        response = client.post(
            "/stocks/sell", json={"ticker": "AAPL", "amount": "abc", "cost_basis": 100}
        )

        assert response.status_code == 500
