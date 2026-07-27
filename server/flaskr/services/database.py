import mysql.connector
from datetime import datetime


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

def get_transactions():
    query = (
        "SELECT tr_id, ticker, amount, cost_basis, transaction_date "
        "FROM transactions ORDER BY transaction_date, tr_id;"
    )

    return [
        {
            'tr_id': tr_id,
            'ticker': ticker,
            'amount': amount,
            'cost_basis': cost_basis,
            'transaction_date': transaction_date,
        }
        for tr_id, ticker, amount, cost_basis, transaction_date in read_query(query)
    ]

def buy_holding(ticker, amount, cost_basis=None, transaction_date=None):
    amount = abs(amount)
    if transaction_date is None:
        transaction_date = datetime.now().date()

    if cost_basis is None:
        cost_basis = YahooFinanceStock(ticker).get_price_on_date(transaction_date)

    write_query(
        "INSERT INTO transactions (ticker, amount, cost_basis, transaction_date) VALUES (%s, %s, %s, %s);",
        (ticker, amount, cost_basis, transaction_date)
    )

def get_holding_amount(ticker):
    query = "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE ticker = %s;"
    result = read_query(query, (ticker,))
    return result[0][0]

def sell_holding(ticker, amount, cost_basis=None, transaction_date=None):
    amount = abs(amount)
    current_amount = get_holding_amount(ticker)
    if amount > current_amount:
        raise ValueError(f"Cannot sell {amount} shares of {ticker}; only {current_amount} available")

    if transaction_date is None:
        transaction_date = datetime.now().date()

    if cost_basis is None:
        cost_basis = YahooFinanceStock(ticker).get_price_on_date(transaction_date)

    write_query(
        "INSERT INTO transactions (ticker, amount, cost_basis, transaction_date) VALUES (%s, %s, %s, %s);",
        (ticker, -amount, cost_basis, transaction_date)
    )