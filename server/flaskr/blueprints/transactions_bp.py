from flask import Blueprint, jsonify

from flaskr.services.database import get_transactions

transactions_bp = Blueprint("transactions", __name__, url_prefix="/transactions")


@transactions_bp.get("/")
def get_transactions_route():
    transactions = get_transactions()
    return jsonify(transactions), 200
