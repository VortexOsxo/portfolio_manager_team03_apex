from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from flaskr.services.database import get_transactions

transactions_bp = Blueprint("transactions", __name__, url_prefix="/transactions")


@transactions_bp.get("/")
@jwt_required()
def get_transactions_route():
    account_id = int(get_jwt_identity())
    ticker = request.args.get("ticker")
    try:
        transactions = get_transactions(account_id, ticker=ticker)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(transactions), 200
