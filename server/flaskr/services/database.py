import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from threading import Lock

import mysql.connector

from flaskr.services import performance
from flaskr.yahoo_finance import YahooFinanceStock

INITIAL_CASH = Decimal(str(os.getenv("INITIAL_CASH", "30000.00")))

_PERFORMANCE_CACHE = {}
_PERFORMANCE_CACHE_LOCK = Lock()
_PERFORMANCE_CACHE_TTL_SECONDS = 300
_MARKET_TICKER = "^GSPC"


def clear_performance_cache():
    with _PERFORMANCE_CACHE_LOCK:
        _PERFORMANCE_CACHE.clear()

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


def write_query(query, params=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    cursor.close()
    conn.close()

def read_query(query, params=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result

def get_transactions(ticker = None, start_date = None, end_date = None):
    query = (
        "SELECT tr_id, ticker, amount, cost_basis, transaction_date "
        "FROM transactions WHERE 1=1"
    )
    params = ()
    if ticker:
        query += " AND ticker = %s"
        params += (ticker,)
    if start_date is not None:
        query += " AND transaction_date >= %s"
        params += (start_date,)
    if end_date is not None:
        query += " AND transaction_date <= %s"
        params += (end_date,)
    query += " ORDER BY transaction_date, tr_id;"

    return [
        {
            'tr_id': tr_id,
            'ticker': tx_ticker,
            'amount': amount,
            'cost_basis': cost_basis,
            'transaction_date': transaction_date,
        }
        for tr_id, tx_ticker, amount, cost_basis, transaction_date in read_query(query, params)
    ]

def buy_holding(ticker, amount, cost_basis=None, transaction_date=None):
    amount = abs(Decimal(str(amount)))

    if cost_basis is None:
        # Price lookup needs the local trading day, not a UTC-shifted one --
        # near UTC rollover, "now" in UTC can already read as "tomorrow", a
        # day that hasn't traded yet.
        price_lookup_date = transaction_date if transaction_date is not None else datetime.now().date()
        cost_basis = YahooFinanceStock(ticker).get_price_on_date(price_lookup_date)

    if cost_basis is None:
        raise ValueError(f"No price data available for {ticker} on {price_lookup_date}")

    total_cost = amount * Decimal(str(cost_basis))

    if transaction_date is None:
        transaction_date = datetime.now(timezone.utc).replace(tzinfo=None)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # FOR UPDATE locks the rows this balance is derived from, so a
        # concurrent buy blocks here instead of reading the same
        # not-yet-committed balance and also passing the check.
        cursor.execute("SELECT COALESCE(SUM(amount * cost_basis), 0) FROM transactions FOR UPDATE;")
        cash_balance = INITIAL_CASH - Decimal(str(cursor.fetchone()[0]))
        if total_cost > cash_balance:
            raise ValueError(
                f"Insufficient cash: buying {amount} shares of {ticker} at {cost_basis} "
                f"costs {total_cost:.2f}, but only {cash_balance:.2f} available"
            )

        cursor.execute(
            "INSERT INTO transactions (ticker, amount, cost_basis, transaction_date) VALUES (%s, %s, %s, %s);",
            (ticker, amount, cost_basis, transaction_date)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

    clear_performance_cache()

def get_cash_balance():
    result = read_query("SELECT COALESCE(SUM(amount * cost_basis), 0) FROM transactions;")
    return INITIAL_CASH - Decimal(str(result[0][0]))

def get_holding_amount(ticker, date=None):
    query = "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE ticker = %s" +\
    ("AND transaction_date <= %s;" if date else ";")
    params = (ticker, date) if date else (ticker,)

    result = read_query(query, params)
    return result[0][0]

def sell_holding(ticker, amount, cost_basis=None, transaction_date=None):
    amount = abs(Decimal(str(amount)))
    current_amount = Decimal(str(get_holding_amount(ticker)))
    if amount > current_amount:
        raise ValueError(f"Cannot sell {amount} shares of {ticker}; only {current_amount} available")

    if cost_basis is None:
        price_lookup_date = transaction_date if transaction_date is not None else datetime.now().date()
        cost_basis = YahooFinanceStock(ticker).get_price_on_date(price_lookup_date)

    if transaction_date is None:
        transaction_date = datetime.now(timezone.utc).replace(tzinfo=None)

    write_query(
        "INSERT INTO transactions (ticker, amount, cost_basis, transaction_date) VALUES (%s, %s, %s, %s);",
        (ticker, -amount, cost_basis, transaction_date)
    )
    clear_performance_cache()

def get_traded_tickers():
    query = "SELECT DISTINCT ticker FROM transactions;"
    result = read_query(query)
    return [row[0] for row in result]

def get_portfolio_performance(start_date, end_date):
    cache_key = (str(start_date), str(end_date))
    now = time.monotonic()
    with _PERFORMANCE_CACHE_LOCK:
        cached = _PERFORMANCE_CACHE.get(cache_key)
        if cached is not None and now - cached["created_at"] < _PERFORMANCE_CACHE_TTL_SECONDS:
            return list(cached["dates"]), list(cached["performances"])

    transactions = get_transactions()
    tickers = performance.get_tickers_for_range(start_date, end_date, transactions)
    if not tickers:
        return [], []

    all_values = YahooFinanceStock.get_daily_values_for_tickers(
        [*tickers, _MARKET_TICKER],
        start_date,
        end_date,
    )
    dates = list(all_values.get(_MARKET_TICKER, {}).keys())
    if not dates:
        return [], []

    ticker_values = {
        ticker: all_values.get(ticker, {})
        for ticker in tickers
    }
    performances = performance.compute_portfolio_values(dates, transactions, ticker_values)

    with _PERFORMANCE_CACHE_LOCK:
        _PERFORMANCE_CACHE[cache_key] = {
            "created_at": time.monotonic(),
            "dates": list(dates),
            "performances": list(performances),
        }

    return dates, performances

def get_stock_performance(ticker, start_date, end_date):
    market_dates = YahooFinanceStock.get_market_trading_days(start_date, end_date)
    ticker_values = YahooFinanceStock(ticker).get_daily_values(start_date, end_date)

    stock_dates, performances = [], []
    for date in market_dates:
        if date not in ticker_values:
            continue
        stock_dates.append(date)
        performances.append(ticker_values[date])
    return stock_dates, performances
