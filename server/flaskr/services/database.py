import mysql.connector
from datetime import datetime


from flaskr.config import DB_CONFIG
from flaskr.services.yahoo_api_service import YahooApiService

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
    query = "SELECT ticker, amount, cost_basis, transaction_date FROM transactions;"

    map_holdings = []
    holdings = read_query(query)
    for holding in holdings:
        ticker, amount, cost_basis, transaction_date = holding
        name = YahooApiService.get_stock_name(ticker)

        map_holdings.append({
            'ticker': ticker, 
            'name': name,
            'amount': amount,
            'cost_basis': cost_basis,
            'transaction_date': transaction_date
        })
    return map_holdings

def buy_holding(ticker, amount, cost_basis=None, transaction_date=None):
    amount = abs(amount)
    if transaction_date is None:
        transaction_date = datetime.now().date()

    if cost_basis is None:
        cost_basis = YahooApiService.get_stock_price(ticker, transaction_date)
    
    write_query(
        "INSERT INTO transactions (ticker, amount, cost_basis, transaction_date) VALUES (%s, %s, %s, %s);",
        (ticker, amount, cost_basis, transaction_date)
    )

def sell_holding(ticker, amount, cost_basis=None, transaction_date=None):
    amount = -abs(amount)
    if transaction_date is None:
        transaction_date = datetime.now().date()

    if cost_basis is None:
        cost_basis = YahooApiService.get_stock_price(ticker, transaction_date)

    write_query(
        "INSERT INTO transactions (ticker, amount, cost_basis, transaction_date) VALUES (%s, %s, %s, %s);",
        (ticker, amount, 0, transaction_date)
    )