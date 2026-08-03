from flask import Blueprint, jsonify, request

from flaskr.services.database import get_transactions

transactions_bp = Blueprint("transactions", __name__, url_prefix="/transactions")


@transactions_bp.get("/")
def get_transactions_route():
    ticker = request.args.get("ticker")
    try:
        transactions = get_transactions(ticker)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(transactions), 200
