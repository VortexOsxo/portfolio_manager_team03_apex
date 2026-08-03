import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from flaskr.services import database


class PortfolioPerformanceCacheTests(unittest.TestCase):
    def setUp(self):
        database.clear_performance_cache()

    def tearDown(self):
        database.clear_performance_cache()

    @patch("flaskr.services.database.get_account_balance")
    @patch("flaskr.services.database.YahooFinanceStock.get_daily_values_for_tickers")
    @patch("flaskr.services.database.get_transactions")
    def test_reuses_a_cached_range(self, get_transactions, get_daily_values, get_account_balance):
        get_account_balance.return_value = Decimal("30000.00")
        get_transactions.return_value = [
            {
                "tr_id": 1,
                "type": "buy",
                "ticker": "AAPL",
                "amount": 2,
                "cost_basis": 100.0,
                "transaction_date": "2026-01-02",
            },
        ]
        get_daily_values.return_value = {
            "AAPL": {"2026-01-02": 100, "2026-01-05": 105},
            "^GSPC": {"2026-01-02": 1, "2026-01-05": 1},
        }

        first_result = database.get_portfolio_performance("2026-01-01", "2026-01-05")
        second_result = database.get_portfolio_performance("2026-01-01", "2026-01-05")

        dates, equity, cash = first_result
        self.assertEqual(dates, ["2026-01-02", "2026-01-05"])
        self.assertEqual(equity, [200.0, 210.0])
        self.assertIsInstance(cash, list)
        self.assertEqual(second_result, first_result)
        self.assertEqual(get_transactions.call_count, 2)
        get_daily_values.assert_called_once_with(
            ["AAPL", "^GSPC"],
            "2026-01-01",
            "2026-01-05",
        )

    @patch("flaskr.services.database.get_db_connection")
    def test_buy_invalidates_cached_ranges(self, get_db_connection):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (Decimal("30000.00"),)
        get_db_connection.return_value.cursor.return_value = mock_cursor

        database._PERFORMANCE_CACHE[("start", "end")] = {
            "created_at": 0,
            "dates": [],
            "equity": [],
            "cash": [],
        }

        database.buy_holding("AAPL", 1, cost_basis=100, transaction_date="2026-01-02")

        self.assertEqual(database._PERFORMANCE_CACHE, {})
        mock_cursor.execute.assert_any_call(
            "INSERT INTO transactions (type, ticker, amount, cost_basis, transaction_date) "
            "VALUES ('buy', %s, %s, %s, %s)",
            ("AAPL", Decimal("1"), 100, "2026-01-02"),
        )

    @patch("flaskr.services.database.get_holding_amount")
    @patch("flaskr.services.database.get_db_connection")
    def test_sell_invalidates_cached_ranges(self, get_db_connection, get_holding_amount):
        # The source calls clear_performance_cache() in both buy_holding and
        # sell_holding, but only the buy path had a regression test.
        get_holding_amount.return_value = 5
        mock_cursor = MagicMock()
        get_db_connection.return_value.cursor.return_value = mock_cursor

        database._PERFORMANCE_CACHE[("start", "end")] = {
            "created_at": 0,
            "dates": [],
            "equity": [],
            "cash": [],
        }

        database.sell_holding("AAPL", 1, cost_basis=100, transaction_date="2026-01-02")

        self.assertEqual(database._PERFORMANCE_CACHE, {})
        mock_cursor.execute.assert_any_call(
            "INSERT INTO transactions (type, ticker, amount, cost_basis, transaction_date) "
            "VALUES ('sell', %s, %s, %s, %s)",
            ("AAPL", Decimal("-1"), 100, "2026-01-02"),
        )

    @patch("flaskr.services.database.get_account_balance")
    @patch("flaskr.services.database.YahooFinanceStock.get_daily_values_for_tickers")
    @patch("flaskr.services.database.get_transactions")
    def test_expired_cache_entry_is_refetched(self, get_transactions, get_daily_values, get_account_balance):
        get_account_balance.return_value = Decimal("30000.00")
        get_transactions.return_value = [
            {
                "tr_id": 1,
                "type": "buy",
                "ticker": "AAPL",
                "amount": 2,
                "cost_basis": 100.0,
                "transaction_date": "2026-01-02",
            },
        ]
        get_daily_values.return_value = {
            "AAPL": {"2026-01-02": 100, "2026-01-05": 105},
            "^GSPC": {"2026-01-02": 1, "2026-01-05": 1},
        }

        database.get_portfolio_performance("2026-01-01", "2026-01-05")

        # Force the cached entry to look older than the TTL, rather than
        # sleeping 300+ seconds in the test.
        cache_key = ("2026-01-01", "2026-01-05")
        database._PERFORMANCE_CACHE[cache_key]["created_at"] -= (
            database._PERFORMANCE_CACHE_TTL_SECONDS + 1
        )

        database.get_portfolio_performance("2026-01-01", "2026-01-05")

        self.assertEqual(get_transactions.call_count, 4)
        self.assertEqual(get_daily_values.call_count, 2)


if __name__ == "__main__":
    unittest.main()
