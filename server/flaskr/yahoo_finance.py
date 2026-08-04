import time
from datetime import datetime, timedelta

import yfinance as yf

# get_info() is called once per held ticker for both /stocks and /stocks/summary
# on every page load 
_INFO_CACHE = {}
_INFO_CACHE_TTL_SECONDS = 30


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
        """Company name, current price and today's change, straight from Yahoo Finance."""
        cached = _INFO_CACHE.get(self.ticker)
        if cached is not None and time.time() - cached[1] < _INFO_CACHE_TTL_SECONDS:
            return cached[0]

        info = {
            "stock_ticker": self.ticker,
            "company_name": self.get_field("longName", "shortName"),
            "current_price": self.get_field("currentPrice", "regularMarketPrice"),
            "day_change": self.get_field("regularMarketChange"),
            "day_change_pct": self.get_field("regularMarketChangePercent"),
        }
        _INFO_CACHE[self.ticker] = (info, time.time())
        return info

    def get_price_on_date(self, date):
        """Closing price on a given date ("YYYY-MM-DD" string or datetime.date)."""
        start = self._get_date(date)
        end = start + timedelta(days=1)

        history = self._stock.history(start=start, end=end)
        if history.empty:
            return None

        return history["Close"].iloc[0]

    def get_daily_values(self, start_date, end_date):
        start = self._get_date(start_date)
        end = self._get_date(end_date)

        history = self._stock.history(start=start, end=end + timedelta(days=1), interval="1d")
        if history.empty:
            return {}

        dates = [dt.strftime("%Y-%m-%d") for dt in history.index.to_pydatetime()]
        prices = history["Close"].tolist()
        return dict(zip(dates, prices))

    @staticmethod
    def get_daily_values_for_tickers(tickers, start_date, end_date):
        """Fetch daily closing prices for several tickers in one Yahoo request."""
        tickers = list(dict.fromkeys(tickers))
        if not tickers:
            return {}

        start = YahooFinanceStock._get_date(start_date)
        end = YahooFinanceStock._get_date(end_date)
        history = yf.download(
            tickers=tickers,
            start=start,
            end=end + timedelta(days=1),
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        if history.empty:
            return {ticker: {} for ticker in tickers}

        result = {}
        column_levels = getattr(history.columns, "nlevels", 1)
        first_level = set(history.columns.get_level_values(0)) if column_levels > 1 else set()

        for ticker in tickers:
            try:
                if ticker in first_level:
                    close_prices = history[ticker]["Close"]
                elif "Close" in first_level:
                    close_prices = history["Close"][ticker]
                else:
                    close_prices = history["Close"]
                    if hasattr(close_prices, "columns"):
                        close_prices = close_prices[ticker]
            except (KeyError, TypeError):
                result[ticker] = {}
                continue

            close_prices = close_prices.dropna()
            result[ticker] = {
                date.strftime("%Y-%m-%d"): float(price)
                for date, price in close_prices.items()
            }

        return result

    @staticmethod
    def _get_date(date):
        return datetime.strptime(date, "%Y-%m-%d") if isinstance(date, str) else date

    @staticmethod
    def get_market_trading_days(start_date, end_date, market_ticker="^GSPC"):
        """Return trading days for a broad US market index rather than a single stock."""
        start = YahooFinanceStock._get_date(start_date)
        end = YahooFinanceStock._get_date(end_date)

        history = yf.Ticker(market_ticker).history(
            start=start,
            end=end + timedelta(days=1),
            interval="1d"
        )
        return history.index.strftime("%Y-%m-%d").tolist()


def search_stocks(query, limit=8):
    # Search for stocks by query string 
    query = (query or "").strip()
    if not query:
        return []

    try:
        quotes = yf.Search(query, max_results=limit).quotes
    except Exception:
        return []

    return [
        {
            "ticker": quote["symbol"],
            "name": quote.get("shortname") or quote.get("longname") or quote["symbol"],
        }
        for quote in quotes
        if quote.get("quoteType") == "EQUITY"
    ]
