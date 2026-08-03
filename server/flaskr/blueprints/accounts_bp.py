from decimal import Decimal

from flask import Blueprint, jsonify, request

from flaskr.services.database import get_account_balance, deposit_cash, withdraw_cash, get_user, create_user
from werkzeug.security import check_password_hash, generate_password_hash

accounts_bp = Blueprint("accounts", __name__, url_prefix="/accounts")



@accounts_bp.post("/signup")
def signup():
    body = request.get_json()
    username = body.get('username')
    password = body.get('password')
    if username is None or password is None:
        return "Username and password required", 400
    
    result = create_user(username=username, password=generate_password_hash(password))
    if result:
        return "", 201

    return "Username must be unique", 400


@accounts_bp.post("/login")
def login():
    body = request.get_json()
    username = body.get('username')
    password = body.get('password')

    user = get_user(username)
    if user is None:
        return "", 400

    if not check_password_hash(user.get('password'), password):
        return "", 400

    return jsonify(user), 200

@accounts_bp.get("/balance")
def get_balance():
    balance = get_account_balance(1)
    return jsonify({"account_id": 1, "balance": float(balance)}), 200


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

def _parse_amount(data):
    if not data or "amount" not in data:
        return None, "amount is required"

    try:
        amount = Decimal(str(data["amount"]))
    except Exception:
        return None, "amount must be a number"

    if amount <= 0:
        return None, "amount must be greater than zero"

    return amount, None