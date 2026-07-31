from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from flaskr.services import database


class TestGetTransactions:
    @patch("flaskr.services.database.read_query")
    def test_maps_rows_without_ticker_filter(self, mock_read_query):
        mock_read_query.return_value = [
            (1, "AAPL", 10, 100.0, date(2024, 1, 1)),
            (2, "MSFT", 5, 200.0, date(2024, 1, 2)),
        ]

        transactions = database.get_transactions()

        assert transactions == [
            {"tr_id": 1, "ticker": "AAPL", "amount": 10, "cost_basis": 100.0, "transaction_date": date(2024, 1, 1)},
            {"tr_id": 2, "ticker": "MSFT", "amount": 5, "cost_basis": 200.0, "transaction_date": date(2024, 1, 2)},
        ]
        query, params = mock_read_query.call_args.args
        assert "ticker = %s" not in query
        assert params == ()

    @patch("flaskr.services.database.read_query")
    def test_filters_by_ticker(self, mock_read_query):
        mock_read_query.return_value = [(1, "AAPL", 10, 100.0, date(2024, 1, 1))]

        transactions = database.get_transactions("AAPL")

        assert len(transactions) == 1
        query, params = mock_read_query.call_args.args
        assert "AND ticker = %s" in query
        assert params == ("AAPL",)


class TestBuyHolding:
    @patch("flaskr.services.database.get_db_connection")
    def test_uses_explicit_cost_basis_and_date(self, mock_get_db_connection):
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)

        database.buy_holding("AAPL", 10, cost_basis=150.0, transaction_date=date(2024, 1, 1))

        assert mock_cursor.execute.call_args_list[1][0][1] == ("AAPL", 10, 150.0, date(2024, 1, 1))
        assert mock_cursor.execute.call_args_list[2][0][0].startswith("UPDATE accounts SET balance")

    @patch("flaskr.services.database.YahooFinanceStock")
    @patch("flaskr.services.database.get_db_connection")
    def test_looks_up_price_when_cost_basis_omitted(self, mock_get_db_connection, mock_stock_cls):
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)
        mock_stock_cls.return_value.get_price_on_date.return_value = 175.0

        database.buy_holding("AAPL", 10, transaction_date=date(2024, 1, 1))

        mock_stock_cls.return_value.get_price_on_date.assert_called_once_with(date(2024, 1, 1))
        assert mock_cursor.execute.call_args_list[1][0][1] == ("AAPL", 10, 175.0, date(2024, 1, 1))

    @patch("flaskr.services.database.get_db_connection")
    def test_negative_amount_is_stored_as_positive(self, mock_get_db_connection):
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)

        database.buy_holding("AAPL", -10, cost_basis=150.0, transaction_date=date(2024, 1, 1))

        assert mock_cursor.execute.call_args_list[1][0][1][1] == 10

    @patch("flaskr.services.database.YahooFinanceStock")
    @patch("flaskr.services.database.get_db_connection")
    def test_defaults_transaction_date_to_now_utc(self, mock_get_db_connection, mock_stock_cls):
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)
        mock_stock_cls.return_value.get_price_on_date.return_value = 100.0

        before = datetime.now(timezone.utc).replace(tzinfo=None)
        database.buy_holding("AAPL", 10)
        after = datetime.now(timezone.utc).replace(tzinfo=None)

        stored_date = mock_cursor.execute.call_args_list[1][0][1][3]
        assert before <= stored_date <= after

    @patch("flaskr.services.database.get_db_connection")
    def test_raises_when_cash_balance_is_insufficient(self, mock_get_db_connection):
        mock_conn = mock_get_db_connection.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("100.00"),)

        with pytest.raises(ValueError, match="Insufficient cash"):
            database.buy_holding("AAPL", 10, cost_basis=150.0, transaction_date=date(2024, 1, 1))

        mock_cursor.execute.assert_called_once()  # only the balance check, no INSERT
        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()


class TestGetCashBalance:
    @patch("flaskr.services.database.read_query")
    def test_reads_account_balance(self, mock_read_query):
        mock_read_query.return_value = [(Decimal("25000.00"),)]

        assert database.get_account_balance() == Decimal("25000.00")
        mock_read_query.assert_called_once_with("SELECT balance FROM accounts WHERE id = %s;", (1,))


class TestSellHolding:
    @patch("flaskr.services.database.get_db_connection")
    @patch("flaskr.services.database.get_holding_amount")
    def test_uses_explicit_cost_basis_and_stores_negative_amount(self, mock_get_amount, mock_get_db_connection):
        mock_get_amount.return_value = 10
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)

        database.sell_holding("AAPL", 5, cost_basis=160.0, transaction_date=date(2024, 1, 3))

        assert mock_cursor.execute.call_args_list[0][0][1] == ("AAPL", -5, 160.0, date(2024, 1, 3))
        assert mock_cursor.execute.call_args_list[1][0][0].startswith("UPDATE accounts SET balance")

    @patch("flaskr.services.database.get_holding_amount")
    def test_raises_when_selling_more_than_owned(self, mock_get_amount):
        mock_get_amount.return_value = 3

        with pytest.raises(ValueError, match="only 3 available"):
            database.sell_holding("AAPL", 5, cost_basis=160.0, transaction_date=date(2024, 1, 3))

    @patch("flaskr.services.database.get_db_connection")
    @patch("flaskr.services.database.get_holding_amount")
    def test_selling_exact_amount_owned_is_allowed(self, mock_get_amount, mock_get_db_connection):
        mock_get_amount.return_value = 5

        database.sell_holding("AAPL", 5, cost_basis=160.0, transaction_date=date(2024, 1, 3))

        mock_get_db_connection.return_value.cursor.return_value.execute.assert_called()

    @patch("flaskr.services.database.YahooFinanceStock")
    @patch("flaskr.services.database.get_db_connection")
    @patch("flaskr.services.database.get_holding_amount")
    def test_looks_up_price_when_cost_basis_omitted(self, mock_get_amount, mock_get_db_connection, mock_stock_cls):
        mock_get_amount.return_value = 10
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)
        mock_stock_cls.return_value.get_price_on_date.return_value = 180.0

        database.sell_holding("AAPL", 5, transaction_date=date(2024, 1, 3))

        mock_stock_cls.return_value.get_price_on_date.assert_called_once_with(date(2024, 1, 3))
        assert mock_cursor.execute.call_args_list[0][0][1] == ("AAPL", -5, 180.0, date(2024, 1, 3))
