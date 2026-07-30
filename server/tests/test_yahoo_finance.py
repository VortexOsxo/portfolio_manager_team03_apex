import unittest
from unittest.mock import patch

import pandas as pd

from flaskr.yahoo_finance import YahooFinanceStock


class YahooFinanceBatchTests(unittest.TestCase):
    @patch("flaskr.yahoo_finance.yf.download")
    def test_fetches_multiple_tickers_in_one_download(self, download):
        index = pd.to_datetime(["2026-01-02", "2026-01-05"])
        columns = pd.MultiIndex.from_tuples([
            ("AAPL", "Close"),
            ("MSFT", "Close"),
        ])
        download.return_value = pd.DataFrame(
            [[100.0, 200.0], [105.0, 210.0]],
            index=index,
            columns=columns,
        )

        result = YahooFinanceStock.get_daily_values_for_tickers(
            ["AAPL", "MSFT"],
            "2026-01-01",
            "2026-01-05",
        )

        self.assertEqual(result, {
            "AAPL": {"2026-01-02": 100.0, "2026-01-05": 105.0},
            "MSFT": {"2026-01-02": 200.0, "2026-01-05": 210.0},
        })
        download.assert_called_once()


if __name__ == "__main__":
    unittest.main()
