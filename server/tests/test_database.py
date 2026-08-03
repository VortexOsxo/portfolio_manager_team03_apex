from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from flaskr.services import database


class TestGetTransactions:
    @patch("flaskr.services.database.read_query")
    def test_maps_rows_without_ticker_filter(self, mock_read_query):
        mock_read_query.return_value = [
            (1, "buy", "AAPL", 10, 100.0, date(2024, 1, 1)),
            (2, "buy", "MSFT", 5, 200.0, date(2024, 1, 2)),
        ]

        transactions = database.get_transactions()

        assert transactions == [
            {"tr_id": 1, "type": "buy", "ticker": "AAPL", "amount": 10, "cost_basis": 100.0, "transaction_date": date(2024, 1, 1)},
            {"tr_id": 2, "type": "buy", "ticker": "MSFT", "amount": 5, "cost_basis": 200.0, "transaction_date": date(2024, 1, 2)},
        ]
        query, params = mock_read_query.call_args.args
        assert "ticker = %s" not in query
        assert params == ()

    @patch("flaskr.services.database.read_query")
    def test_filters_by_ticker(self, mock_read_query):
        mock_read_query.return_value = [(1, "buy", "AAPL", 10, 100.0, date(2024, 1, 1))]

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

    @patch("flaskr.services.database.get_db_connection")
    def test_accepts_a_future_transaction_date_without_restriction(self, mock_get_db_connection):
        # Documents current behavior: neither the app nor the schema rejects
        # a transaction_date in the future.
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)
        future_date = date(2099, 1, 1)

        database.buy_holding("AAPL", 1, cost_basis=100, transaction_date=future_date)

        inserted_params = mock_cursor.execute.call_args_list[1][0][1]
        assert inserted_params[3] == future_date

    @patch("flaskr.services.database.get_db_connection")
    def test_identical_transactions_can_be_inserted_twice(self, mock_get_db_connection):
        # No uniqueness constraint on (ticker, amount, cost_basis, date) --
        # documents that duplicate buys are silently allowed.
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)

        database.buy_holding("AAPL", 1, cost_basis=100, transaction_date=date(2024, 1, 1))
        database.buy_holding("AAPL", 1, cost_basis=100, transaction_date=date(2024, 1, 1))

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

        assert database.get_account_balance() == Decimal("25000.00")
        mock_read_query.assert_called_once_with("SELECT balance FROM accounts WHERE id = %s;", (1,))

    @patch("flaskr.services.database.read_query")
    def test_raises_when_account_does_not_exist(self, mock_read_query):
        mock_read_query.return_value = []

        with pytest.raises(ValueError, match="Account 1 not found"):
            database.get_account_balance()


class TestUpdateAccountBalance:
    def test_uses_caller_supplied_cursor_instead_of_a_new_connection(self):
        mock_cursor = MagicMock()

        with patch("flaskr.services.database.write_query") as mock_write_query:
            database.update_account_balance(Decimal("50.00"), account_id=1, cursor=mock_cursor)

        mock_cursor.execute.assert_called_once_with(
            "UPDATE accounts SET balance = balance + %s WHERE id = %s;",
            (Decimal("50.00"), 1),
        )
        mock_write_query.assert_not_called()

    @patch("flaskr.services.database.write_query")
    def test_opens_its_own_connection_when_no_cursor_given(self, mock_write_query):
        # Every current caller (buy/sell_holding, deposit_cash,
        # withdraw_cash) passes its own locked cursor; this covers the
        # standalone branch as a unit even though nothing exercises it
        # in production right now.
        database.update_account_balance(Decimal("50.00"), account_id=1)

        mock_write_query.assert_called_once_with(
            "UPDATE accounts SET balance = balance + %s WHERE id = %s;",
            (Decimal("50.00"), 1),
        )


class TestDepositCash:
    @patch("flaskr.services.database.get_db_connection")
    def test_credits_the_account_and_logs_a_deposit_transaction(self, mock_get_db_connection):
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value

        database.deposit_cash(100, transaction_date=date(2024, 1, 1))

        insert_query, insert_params = mock_cursor.execute.call_args_list[0][0]
        assert "'deposit'" in insert_query
        assert insert_params == (Decimal("100"), date(2024, 1, 1))
        assert mock_cursor.execute.call_args_list[1][0][0].startswith("UPDATE accounts SET balance")
        mock_get_db_connection.return_value.commit.assert_called_once()

    @patch("flaskr.services.database.get_db_connection")
    def test_takes_no_row_lock_since_a_credit_cannot_overdraw(self, mock_get_db_connection):
        # Unlike withdraw_cash, deposit_cash never branches on the current
        # balance, so there's nothing for a lock to protect here.
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value

        database.deposit_cash(100, transaction_date=date(2024, 1, 1))

        executed_queries = [call.args[0] for call in mock_cursor.execute.call_args_list]
        assert not any("FOR UPDATE" in query for query in executed_queries)


class TestWithdrawCash:
    @patch("flaskr.services.database.get_db_connection")
    def test_debits_the_account_and_logs_a_withdrawal_transaction(self, mock_get_db_connection):
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)

        database.withdraw_cash(100, transaction_date=date(2024, 1, 1))

        insert_query, insert_params = mock_cursor.execute.call_args_list[1][0]
        assert "'withdrawal'" in insert_query
        assert insert_params == (Decimal("100"), date(2024, 1, 1))
        assert mock_cursor.execute.call_args_list[2][0][0].startswith("UPDATE accounts SET balance")

    @patch("flaskr.services.database.get_db_connection")
    def test_locks_the_account_row_before_checking_the_balance(self, mock_get_db_connection):
        # Unlike sell_holding's shares check, withdraw_cash reads the
        # balance with SELECT ... FOR UPDATE, so two concurrent withdrawals
        # can't both read the same starting balance and jointly overdraw --
        # the second blocks until the first's transaction commits.
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("100.00"),)

        database.withdraw_cash(60, transaction_date=date(2024, 1, 1))

        first_query = mock_cursor.execute.call_args_list[0][0][0]
        assert "FOR UPDATE" in first_query

    @patch("flaskr.services.database.get_db_connection")
    def test_withdrawing_more_than_balance_raises_and_rolls_back(self, mock_get_db_connection):
        mock_conn = mock_get_db_connection.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("100.00"),)

        with pytest.raises(ValueError, match="Insufficient funds"):
            database.withdraw_cash(100.01, transaction_date=date(2024, 1, 1))

        mock_cursor.execute.assert_called_once()  # only the balance check, no INSERT
        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()

    @patch("flaskr.services.database.get_db_connection")
    def test_withdrawing_exactly_the_full_balance_is_allowed(self, mock_get_db_connection):
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value
        mock_cursor.fetchone.return_value = (Decimal("100.00"),)

        database.withdraw_cash(100.00, transaction_date=date(2024, 1, 1))

        insert_calls = [
            call for call in mock_cursor.execute.call_args_list
            if call.args[0].startswith("INSERT INTO transactions")
        ]
        assert len(insert_calls) == 1


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
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)

        database.sell_holding("AAPL", 5, cost_basis=160.0, transaction_date=date(2024, 1, 3))

        assert mock_cursor.execute.call_args_list[1][0][1] == ("AAPL", -5, 160.0, date(2024, 1, 3))
        assert mock_cursor.execute.call_args_list[2][0][0].startswith("UPDATE accounts SET balance")

    @patch("flaskr.services.database.get_db_connection")
    @patch("flaskr.services.database.get_holding_amount")
    def test_raises_when_selling_more_than_owned(self, mock_get_amount, mock_get_db_connection):
        mock_get_amount.return_value = 3

        with pytest.raises(ValueError, match="only 3 available"):
            database.sell_holding("AAPL", 5, cost_basis=160.0, transaction_date=date(2024, 1, 3))

        mock_get_db_connection.return_value.rollback.assert_called_once()

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
        assert mock_cursor.execute.call_args_list[1][0][1] == ("AAPL", -5, 180.0, date(2024, 1, 3))

    @patch("flaskr.services.database.get_db_connection")
    @patch("flaskr.services.database.get_holding_amount")
    def test_locks_the_accounts_row_before_checking_shares_owned(self, mock_get_amount, mock_get_db_connection):
        # buy_holding and withdraw_cash both lock the accounts row before
        # their balance checks; sell_holding now takes the same lock before
        # calling get_holding_amount, so two concurrent sells of the same
        # ticker can no longer both read the same current_amount and
        # jointly oversell the position -- the second blocks until the
        # first's transaction commits.
        mock_get_amount.return_value = 10
        mock_cursor = mock_get_db_connection.return_value.cursor.return_value

        database.sell_holding("AAPL", 5, cost_basis=100, transaction_date=date(2024, 1, 1))

        first_query = mock_cursor.execute.call_args_list[0][0][0]
        assert "FOR UPDATE" in first_query
        # get_holding_amount is called only after the lock is acquired.
        mock_get_amount.assert_called_once_with("AAPL")
