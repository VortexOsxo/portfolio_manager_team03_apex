from flask import Blueprint, jsonify, request
import mysql

from flaskr.services.database import get_transactions, buy_holding, sell_holding

stocks_bp = Blueprint("stocks", __name__, url_prefix="/stocks")


@stocks_bp.get("/")
def get_stocks():
    transactions = get_transactions()
    stocks = {}
    for transaction in transactions:
        ticker = transaction['ticker']
        name = transaction['name']
        amount = transaction['amount']

        if ticker not in stocks:
            stocks[ticker] = {
                'ticker': ticker,
                'name': name,
                'amount': 0,
            }

        stocks[ticker]['amount'] += amount
    return jsonify(stocks), 200

@stocks_bp.post("/buy")
def buy_stock():
    data = request.get_json()
    ticker = data.get("ticker")
    amount = data.get("amount")

    if ticker is None or amount is None:
        return "", 400

    cost_basis = data.get("cost_basis")
    transaction_date = data.get("transaction_date")
    try: 
        buy_holding(ticker, amount, cost_basis, transaction_date)
    except mysql.connector.errors.IntegrityError as e:
        return "", 400

    return jsonify({"message": "Stock bought successfully"}), 201

@stocks_bp.post("/sell")
def sell_stock():
    data = request.get_json()
    ticker = data.get("ticker")
    amount = data.get("amount")

    if ticker is None or amount is None:
        return "", 400

    cost_basis = data.get("cost_basis")
    transaction_date = data.get("transaction_date")
    try: 
        sell_holding(ticker, amount, cost_basis, transaction_date)
    except mysql.connector.errors.IntegrityError as e:
        return "", 400

    return jsonify({"message": "Stock sold successfully"}), 201