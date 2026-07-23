from datetime import datetime, timedelta

import yfinance as yf


class YahooFinanceStock:
    def __init__(self, ticker):
        self.ticker = ticker
        self._stock = yf.Ticker(ticker)
        self._info = None

    @property
    def info(self):
        """Raw Yahoo Finance info dict, fetched once and cached per instance."""
        if self._info is None:
            self._info = self._stock.info
        return self._info

    def get_field(self, *keys, default=None):
        """First present value among keys, e.g. get_field("currentPrice", "regularMarketPrice")."""
        for key in keys:
            value = self.info.get(key)
            if value is not None:
                return value
        return default

    def get_info(self):
        """Company name and current price, straight from Yahoo Finance.

        Add more fields here as new features need them, e.g.:
        "sector": self.get_field("sector"),
        """
        return {
            "stock_ticker": self.ticker,
            "company_name": self.get_field("longName", "shortName"),
            "current_price": self.get_field("currentPrice", "regularMarketPrice"),
        }

    def get_price_on_date(self, date):
        """Closing price on a given date ("YYYY-MM-DD" string or datetime.date)."""
        start = datetime.strptime(date, "%Y-%m-%d") if isinstance(date, str) else date
        end = start + timedelta(days=1)

        history = self._stock.history(start=start, end=end)
        if history.empty:
            return None

        return history["Close"].iloc[0]
