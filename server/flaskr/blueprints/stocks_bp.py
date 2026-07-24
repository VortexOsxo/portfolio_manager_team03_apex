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
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT holding_id, ticker, amount, cost_basis, purchase_date
        FROM holdings
        """
    )
    holdings = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(holdings)

@stocks_bp.post("")
def add_stock():
    data = request.get_json()
    ticker = data.get("ticker")
    amount = data.get("amount")
    cost_basis = data.get("cost_basis")
    purchase_date = data.get("purchase_date")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO holdings (ticker, amount, cost_basis, purchase_date)
        VALUES (%s, %s, %s, %s)
        """,
        (ticker, amount, cost_basis, purchase_date)
    )
    conn.commit()
    holding_id = cursor.lastrowid
    cursor.close()
    conn.close()

    return jsonify(
        {
            "holding_id": holding_id,
            "ticker": ticker,
            "amount": amount,
            "cost_basis": cost_basis,
            "purchase_date": purchase_date,
        }
    ), 201
