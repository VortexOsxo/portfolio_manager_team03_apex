import unittest
from datetime import datetime

from flaskr.services.performance import compute_portfolio_values, get_tickers_for_range


class ComputePortfolioValuesTests(unittest.TestCase):
    def test_applies_transactions_once_in_chronological_order(self):
        dates = ["2026-01-02", "2026-01-05", "2026-01-06"]
        transactions = [
            {
                "tr_id": 2,
                "ticker": "AAPL",
                "amount": -2,
                "transaction_date": datetime(2026, 1, 6, 11, 0),
            },
            {
                "tr_id": 1,
                "ticker": "AAPL",
                "amount": 5,
                "transaction_date": datetime(2026, 1, 2, 9, 30),
            },
        ]
        ticker_values = {
            "AAPL": {
                "2026-01-02": 100,
                "2026-01-05": 110,
                "2026-01-06": 120,
            },
        }

        values = compute_portfolio_values(dates, transactions, ticker_values)

        self.assertEqual(values, [500.0, 550.0, 360.0])

    def test_combines_multiple_tickers_and_skips_missing_prices(self):
        dates = ["2026-02-02", "2026-02-03"]
        transactions = [
            {
                "tr_id": 1,
                "ticker": "AAPL",
                "amount": 2,
                "transaction_date": "2026-02-02",
            },
            {
                "tr_id": 2,
                "ticker": "MSFT",
                "amount": 3,
                "transaction_date": "2026-02-02",
            },
        ]
        ticker_values = {
            "AAPL": {"2026-02-02": 10, "2026-02-03": 12},
            "MSFT": {"2026-02-02": 20},
        }

        values = compute_portfolio_values(dates, transactions, ticker_values)

        self.assertEqual(values, [80.0, 24.0])

    def test_returns_zeroes_before_the_first_transaction(self):
        dates = ["2026-03-02", "2026-03-03"]
        transactions = [
            {
                "tr_id": 1,
                "ticker": "NVDA",
                "amount": 1,
                "transaction_date": "2026-03-03",
            },
        ]
        ticker_values = {
            "NVDA": {"2026-03-02": 180, "2026-03-03": 185},
        }

        values = compute_portfolio_values(dates, transactions, ticker_values)

        self.assertEqual(values, [0.0, 185.0])


class GetTickersForRangeTests(unittest.TestCase):
    def test_excludes_positions_closed_before_the_range_and_future_trades(self):
        transactions = [
            {"tr_id": 1, "ticker": "OLD", "amount": 2, "transaction_date": "2025-01-01"},
            {"tr_id": 2, "ticker": "OLD", "amount": -2, "transaction_date": "2025-02-01"},
            {"tr_id": 3, "ticker": "HELD", "amount": 1, "transaction_date": "2025-03-01"},
            {"tr_id": 4, "ticker": "TRADED", "amount": 1, "transaction_date": "2026-01-15"},
            {"tr_id": 5, "ticker": "FUTURE", "amount": 1, "transaction_date": "2027-01-01"},
        ]

        tickers = get_tickers_for_range("2026-01-01", "2026-01-31", transactions)

        self.assertEqual(tickers, ["HELD", "TRADED"])


if __name__ == "__main__":
    unittest.main()
