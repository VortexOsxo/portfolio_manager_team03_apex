from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from flaskr.services import database

ACCOUNT_ID = 1


class TestGetTransactions:
    @patch("flaskr.services.database.read_query")
    def test_maps_rows_without_ticker_filter(self, mock_read_query):
        mock_read_query.return_value = [
            (1, "buy", "AAPL", 10, 100.0, date(2024, 1, 1)),
            (2, "buy", "MSFT", 5, 200.0, date(2024, 1, 2)),
        ]

        transactions = database.get_transactions(ACCOUNT_ID)

        assert transactions == [
            {"tr_id": 1, "type": "buy", "ticker": "AAPL", "amount": 10, "cost_basis": 100.0, "transaction_date": date(2024, 1, 1)},
            {"tr_id": 2, "type": "buy", "ticker": "MSFT", "amount": 5, "cost_basis": 200.0, "transaction_date": date(2024, 1, 2)},
        ]
        query, params = mock_read_query.call_args.args
        assert "ticker = %s" not in query
        assert params == (ACCOUNT_ID,)

    @patch("flaskr.services.database.read_query")
    def test_filters_by_ticker(self, mock_read_query):
        mock_read_query.return_value = [(1, "buy", "AAPL", 10, 100.0, date(2024, 1, 1))]

        transactions = database.get_transactions(ACCOUNT_ID, ticker="AAPL")

        assert len(transactions) == 1
        query, params = mock_read_query.call_args.args
        assert "AND ticker = %s" in query
        assert params == (ACCOUNT_ID, "AAPL")


class TestBuyHolding:
    @patch("flaskr.services.database.get_db_connection")
    def test_uses_explicit_cost_basis_and_date(self, mock_get_db_connection):
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)

        database.buy_holding(ACCOUNT_ID, "AAPL", 10, cost_basis=150.0, transaction_date=date(2024, 1, 1))

        # call_args_list[0] = SELECT FOR UPDATE, [1] = INSERT, [2] = UPDATE balance
        insert_params = mock_cursor.execute.call_args_list[1][0][1]
        assert insert_params == (ACCOUNT_ID, "AAPL", 10, 150.0, date(2024, 1, 1))
        assert mock_cursor.execute.call_args_list[2][0][0].startswith("UPDATE accounts SET balance")

    @patch("flaskr.services.database.YahooFinanceStock")
    @patch("flaskr.services.database.get_db_connection")
    def test_looks_up_price_when_cost_basis_omitted(self, mock_get_db_connection, mock_stock_cls):
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)
        mock_stock_cls.return_value.get_price_on_date.return_value = 175.0

        database.buy_holding(ACCOUNT_ID, "AAPL", 10, transaction_date=date(2024, 1, 1))

        mock_stock_cls.return_value.get_price_on_date.assert_called_once_with(date(2024, 1, 1))
        insert_params = mock_cursor.execute.call_args_list[1][0][1]
        assert insert_params == (ACCOUNT_ID, "AAPL", 10, 175.0, date(2024, 1, 1))

    @patch("flaskr.services.database.get_db_connection")
    def test_negative_amount_is_stored_as_positive(self, mock_get_db_connection):
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)

        database.buy_holding(ACCOUNT_ID, "AAPL", -10, cost_basis=150.0, transaction_date=date(2024, 1, 1))

        # amount is at index 2 in the INSERT params (account_id, ticker, amount, ...)
        insert_params = mock_cursor.execute.call_args_list[1][0][1]
        assert insert_params[2] == 10

    @patch("flaskr.services.database.YahooFinanceStock")
    @patch("flaskr.services.database.get_db_connection")
    def test_defaults_transaction_date_to_now_utc(self, mock_get_db_connection, mock_stock_cls):
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)
        mock_stock_cls.return_value.get_price_on_date.return_value = 100.0

        before = datetime.now(timezone.utc).replace(tzinfo=None)
        database.buy_holding(ACCOUNT_ID, "AAPL", 10)
        after = datetime.now(timezone.utc).replace(tzinfo=None)

        # date is at index 4 in params (account_id, ticker, amount, cost_basis, date)
        stored_date = mock_cursor.execute.call_args_list[1][0][1][4]
        assert before <= stored_date <= after

    @patch("flaskr.services.database.get_db_connection")
    def test_raises_when_cash_balance_is_insufficient(self, mock_get_db_connection):
        mock_conn = mock_get_db_connection.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("100.00"),)

        with pytest.raises(ValueError, match="Insufficient cash"):
            database.buy_holding(ACCOUNT_ID, "AAPL", 10, cost_basis=150.0, transaction_date=date(2024, 1, 1))

        mock_cursor.execute.assert_called_once()  # only the balance check, no INSERT
        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()

    @patch("flaskr.services.database.get_db_connection")
    def test_accepts_a_future_transaction_date_without_restriction(self, mock_get_db_connection):
        # Documents current behavior: neither the app nor the schema rejects
        # a transaction_date in the future.
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)
        future_date = date(2099, 1, 1)

        database.buy_holding(ACCOUNT_ID, "AAPL", 1, cost_basis=100, transaction_date=future_date)

        inserted_params = mock_cursor.execute.call_args_list[1][0][1]
        assert inserted_params[4] == future_date

    @patch("flaskr.services.database.get_db_connection")
    def test_identical_transactions_can_be_inserted_twice(self, mock_get_db_connection):
        # No uniqueness constraint on (ticker, amount, cost_basis, date) --
        # documents that duplicate buys are silently allowed.
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)

        database.buy_holding(ACCOUNT_ID, "AAPL", 1, cost_basis=100, transaction_date=date(2024, 1, 1))
        database.buy_holding(ACCOUNT_ID, "AAPL", 1, cost_basis=100, transaction_date=date(2024, 1, 1))

        insert_calls = [
            call for call in mock_cursor.execute.call_args_list
            if call.args[0].startswith("INSERT INTO transactions")
        ]
        assert len(insert_calls) == 2
        assert insert_calls[0].args[1] == insert_calls[1].args[1]


class TestGetCashBalance:
    @patch("flaskr.services.database.read_query")
    def test_reads_account_balance(self, mock_read_query):
        mock_read_query.return_value = [(Decimal("25000.00"),)]

        assert database.get_account_balance(ACCOUNT_ID) == Decimal("25000.00")
        mock_read_query.assert_called_once_with("SELECT balance FROM accounts WHERE id = %s;", (ACCOUNT_ID,))

    @patch("flaskr.services.database.read_query")
    def test_raises_when_account_does_not_exist(self, mock_read_query):
        mock_read_query.return_value = []

        with pytest.raises(ValueError, match=f"Account {ACCOUNT_ID} not found"):
            database.get_account_balance(ACCOUNT_ID)


class TestUpdateAccountBalance:
    def test_uses_caller_supplied_cursor_instead_of_a_new_connection(self):
        mock_cursor = MagicMock()

        with patch("flaskr.services.database.write_query") as mock_write_query:
            database.update_account_balance(Decimal("50.00"), account_id=ACCOUNT_ID, cursor=mock_cursor)

        mock_cursor.execute.assert_called_once_with(
            "UPDATE accounts SET balance = balance + %s WHERE id = %s;",
            (Decimal("50.00"), ACCOUNT_ID),
        )
        mock_write_query.assert_not_called()

    @patch("flaskr.services.database.write_query")
    def test_opens_its_own_connection_when_no_cursor_given(self, mock_write_query):
        # This is the path accounts_bp's deposit/withdraw routes use -- each
        # call is its own standalone transaction, not covered by any lock.
        database.update_account_balance(Decimal("50.00"), account_id=ACCOUNT_ID)

        mock_write_query.assert_called_once_with(
            "UPDATE accounts SET balance = balance + %s WHERE id = %s;",
            (Decimal("50.00"), ACCOUNT_ID),
        )


class TestGetStockPerformance:
    @patch("flaskr.services.database.YahooFinanceStock")
    def test_returns_dates_and_prices_present_in_both_market_and_ticker_data(self, mock_stock_cls):
        mock_stock_cls.get_market_trading_days.return_value = ["2026-01-02", "2026-01-05"]
        mock_stock_cls.return_value.get_daily_values.return_value = {
            "2026-01-02": 100.0,
            "2026-01-05": 105.0,
        }

        dates, equity = database.get_stock_performance("AAPL", "2026-01-01", "2026-01-05")

        assert dates == ["2026-01-02", "2026-01-05"]
        assert equity == [100.0, 105.0]

    @patch("flaskr.services.database.YahooFinanceStock")
    def test_ticker_with_no_transactions_history_returns_empty_lists(self, mock_stock_cls):
        mock_stock_cls.get_market_trading_days.return_value = ["2026-01-02", "2026-01-05"]
        mock_stock_cls.return_value.get_daily_values.return_value = {}

        dates, equity = database.get_stock_performance("NEWTICKER", "2026-01-01", "2026-01-05")

        assert dates == []
        assert equity == []

    @patch("flaskr.services.database.YahooFinanceStock")
    def test_date_range_with_no_market_trading_days_returns_empty_lists(self, mock_stock_cls):
        mock_stock_cls.get_market_trading_days.return_value = []
        mock_stock_cls.return_value.get_daily_values.return_value = {"2026-01-03": 100.0}

        dates, equity = database.get_stock_performance("AAPL", "2026-01-03", "2026-01-04")

        assert dates == []
        assert equity == []


class TestSellHolding:
    @patch("flaskr.services.database.get_db_connection")
    @patch("flaskr.services.database.get_holding_amount")
    def test_uses_explicit_cost_basis_and_stores_negative_amount(self, mock_get_amount, mock_get_db_connection):
        mock_get_amount.return_value = 10
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value

        database.sell_holding(ACCOUNT_ID, "AAPL", 5, cost_basis=160.0, transaction_date=date(2024, 1, 3))

        insert_params = mock_cursor.execute.call_args_list[0][0][1]
        assert insert_params == (ACCOUNT_ID, "AAPL", -5, 160.0, date(2024, 1, 3))
        assert mock_cursor.execute.call_args_list[1][0][0].startswith("UPDATE accounts SET balance")

    @patch("flaskr.services.database.get_holding_amount")
    def test_raises_when_selling_more_than_owned(self, mock_get_amount):
        mock_get_amount.return_value = 3

        with pytest.raises(ValueError, match="only 3 available"):
            database.sell_holding(ACCOUNT_ID, "AAPL", 5, cost_basis=160.0, transaction_date=date(2024, 1, 3))

    @patch("flaskr.services.database.get_db_connection")
    @patch("flaskr.services.database.get_holding_amount")
    def test_selling_exact_amount_owned_is_allowed(self, mock_get_amount, mock_get_db_connection):
        mock_get_amount.return_value = 5

        database.sell_holding(ACCOUNT_ID, "AAPL", 5, cost_basis=160.0, transaction_date=date(2024, 1, 3))

        mock_get_db_connection.return_value.cursor.return_value.execute.assert_called()

    @patch("flaskr.services.database.YahooFinanceStock")
    @patch("flaskr.services.database.get_db_connection")
    @patch("flaskr.services.database.get_holding_amount")
    def test_looks_up_price_when_cost_basis_omitted(self, mock_get_amount, mock_get_db_connection, mock_stock_cls):
        mock_get_amount.return_value = 10
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_stock_cls.return_value.get_price_on_date.return_value = 180.0

        database.sell_holding(ACCOUNT_ID, "AAPL", 5, transaction_date=date(2024, 1, 3))

        mock_stock_cls.return_value.get_price_on_date.assert_called_once_with(date(2024, 1, 3))
        insert_params = mock_cursor.execute.call_args_list[0][0][1]
        assert insert_params == (ACCOUNT_ID, "AAPL", -5, 180.0, date(2024, 1, 3))

    @patch("flaskr.services.database.get_db_connection")
    @patch("flaskr.services.database.get_holding_amount")
    def test_does_not_lock_the_holdings_row_unlike_buy_holding(self, mock_get_amount, mock_get_db_connection):
        # buy_holding takes a "SELECT ... FOR UPDATE" lock before checking
        # cash balance; sell_holding has no equivalent lock on the shares
        # check, so two concurrent sells could both read the same
        # current_amount and both pass the "not selling more than owned"
        # check, overselling the position. This documents the gap rather
        # than fixing it.
        mock_get_amount.return_value = 10
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value

        database.sell_holding(ACCOUNT_ID, "AAPL", 5, cost_basis=100, transaction_date=date(2024, 1, 1))

        executed_queries = [call.args[0] for call in mock_cursor.execute.call_args_list]
        assert not any("FOR UPDATE" in query for query in executed_queries)
        # get_holding_amount runs via its own unlocked connection, entirely
        # outside the transaction that performs the insert.
        mock_get_amount.assert_called_once_with(ACCOUNT_ID, "AAPL")
