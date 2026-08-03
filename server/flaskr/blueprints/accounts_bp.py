from flask import Blueprint, jsonify, request

from flaskr.services.database import get_account_balance, deposit_cash, withdraw_cash, get_transactions
from flaskr.services.validation import parse_positive_amount

accounts_bp = Blueprint("accounts", __name__, url_prefix="/accounts")


def _parse_amount(data):
    if not data or "amount" not in data:
        return None, "amount is required"

    return parse_positive_amount(data["amount"])


@accounts_bp.get("/balance")
def get_balance():
    try:
        balance = get_account_balance(1)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"account_id": 1, "balance": float(balance)}), 200


@accounts_bp.get("/transactions")
def get_cash_transactions_route():
    try:
        transactions = get_transactions(include_cash_transactions=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    cash_transactions = [tx for tx in transactions if tx['type'] in ('deposit', 'withdrawal')]
    return jsonify(cash_transactions), 200


@accounts_bp.post("/deposit")
def deposit():
    data = request.get_json(silent=True)
    amount, error = _parse_amount(data)
    if error:
        return jsonify({"error": error}), 400

    deposit_cash(amount)
    balance = get_account_balance(1)
    return jsonify({"account_id": 1, "balance": float(balance)}), 201


@accounts_bp.post("/withdraw")
def withdraw():
    data = request.get_json(silent=True)
    amount, error = _parse_amount(data)
    if error:
        return jsonify({"error": error}), 400

    try:
        withdraw_cash(amount)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    balance = get_account_balance(1)
    return jsonify({"account_id": 1, "balance": float(balance)}), 201
