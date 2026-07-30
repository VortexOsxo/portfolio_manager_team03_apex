import mysql.connector
from datetime import datetime, timezone
from decimal import Decimal


from flaskr.config import DB_CONFIG
from flaskr.yahoo_finance import YahooFinanceStock

def get_db_connection():
    return mysql.connector.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
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
    amount = abs(amount)

    if cost_basis is None:
        # Price lookup needs the local trading day, not a UTC-shifted one --
        # near UTC rollover, "now" in UTC can already read as "tomorrow", a
        # day that hasn't traded yet.
        price_lookup_date = transaction_date if transaction_date is not None else datetime.now().date()
        cost_basis = YahooFinanceStock(ticker).get_price_on_date(price_lookup_date)

    if transaction_date is None:
        transaction_date = datetime.now(timezone.utc).replace(tzinfo=None)

    write_query(
        "INSERT INTO transactions (ticker, amount, cost_basis, transaction_date) VALUES (%s, %s, %s, %s);",
        (ticker, amount, cost_basis, transaction_date)
    )

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

def get_traded_tickers():
    query = "SELECT DISTINCT ticker FROM transactions;"
    result = read_query(query)
    return [row[0] for row in result]

def get_portfolio_performance(start_date, end_date):
    tickers = get_traded_tickers()
    if not tickers:
        return [], []

    dates = YahooFinanceStock.get_market_trading_days(start_date, end_date)
    ticker_values = {
        ticker: YahooFinanceStock(ticker).get_daily_values(start_date, end_date)
        for ticker in tickers
    }

    performances = []
    for date in dates:
        holdings = {
            ticker: get_holding_amount(ticker, date)
            for ticker in tickers
        }
        date_value = 0
        for ticker, amount in holdings.items():
            if amount == 0: continue
            date_value += ticker_values.get(ticker).get(date) * float(amount)
        performances.append(date_value)

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
