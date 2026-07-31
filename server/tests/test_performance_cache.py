import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from flaskr.services import database


class PortfolioPerformanceCacheTests(unittest.TestCase):
    def setUp(self):
        database.clear_performance_cache()

    def tearDown(self):
        database.clear_performance_cache()

    @patch("flaskr.services.database.YahooFinanceStock.get_daily_values_for_tickers")
    @patch("flaskr.services.database.get_transactions")
    def test_reuses_a_cached_range(self, get_transactions, get_daily_values):
        get_transactions.return_value = [
            {
                "tr_id": 1,
                "ticker": "AAPL",
                "amount": 2,
                "transaction_date": "2026-01-02",
            },
        ]
        get_daily_values.return_value = {
            "AAPL": {"2026-01-02": 100, "2026-01-05": 105},
            "^GSPC": {"2026-01-02": 1, "2026-01-05": 1},
        }

        first_result = database.get_portfolio_performance("2026-01-01", "2026-01-05")
        second_result = database.get_portfolio_performance("2026-01-01", "2026-01-05")

        self.assertEqual(first_result, (["2026-01-02", "2026-01-05"], [200.0, 210.0]))
        self.assertEqual(second_result, first_result)
        get_transactions.assert_called_once_with()
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
            "performances": [],
        }

        database.buy_holding("AAPL", 1, cost_basis=100, transaction_date="2026-01-02")

        self.assertEqual(database._PERFORMANCE_CACHE, {})
        mock_cursor.execute.assert_any_call(
            "INSERT INTO transactions (ticker, amount, cost_basis, transaction_date) VALUES (%s, %s, %s, %s)",
            ("AAPL", Decimal("1"), 100, "2026-01-02"),
        )


if __name__ == "__main__":
    unittest.main()
