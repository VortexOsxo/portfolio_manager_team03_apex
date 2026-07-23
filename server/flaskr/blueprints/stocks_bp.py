from flask import Blueprint, jsonify, request

from flaskr.database import get_db_connection
from flaskr.yahoo_finance import YahooFinanceStock

stocks_bp = Blueprint("stocks", __name__, url_prefix="/stocks")


@stocks_bp.get("/test")
def test_stocks():
    return "Stocks API test is working!", 200

@stocks_bp.get("/<ticker>/info")
def get_ticker_info(ticker):
    return jsonify(YahooFinanceStock(ticker).get_info())

@stocks_bp.get("/")
def get_stocks():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT symbol FROM stocks")
    stocks = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify([stock[0] for stock in stocks])

@stocks_bp.post("")
def add_stock():
    data = request.get_json()
    symbol = data.get("symbol")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO stocks (symbol) VALUES (%s)",
        (symbol,)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Stock added successfully"}), 201

