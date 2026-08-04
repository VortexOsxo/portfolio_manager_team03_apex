from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from flaskr.services.database import get_account_balance, deposit_cash, withdraw_cash, get_user, create_user, update_account_name, get_transactions
from flaskr.services.validation import parse_positive_amount
from werkzeug.security import check_password_hash, generate_password_hash

accounts_bp = Blueprint("accounts", __name__, url_prefix="/accounts")

MIN_USERNAME_LENGTH = 3
MIN_PASSWORD_LENGTH = 8


@accounts_bp.post("/signup")
def signup():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Username and password required"}), 400

    username = body.get('username')
    password = body.get('password')
    first_name = body.get('first_name')
    last_name = body.get('last_name')
    if not username or not password or not first_name or not last_name:
        return jsonify({"error": "Username, password, first name, and last name required"}), 400
    if len(username) < MIN_USERNAME_LENGTH:
        return jsonify({"error": f"Choose a username with at least {MIN_USERNAME_LENGTH} characters."}), 400
    if len(password) < MIN_PASSWORD_LENGTH:
        return jsonify({"error": f"Choose a password with at least {MIN_PASSWORD_LENGTH} characters to help keep your account secure."}), 400

    result = create_user(
        username=username,
        password=generate_password_hash(password),
        first_name=first_name,
        last_name=last_name,
    )
    if not result:
        return jsonify({"error": "Username already taken"}), 409

    user = get_user(username)
    access_token = create_access_token(identity=str(user['id']))
    return jsonify({
        "access_token": access_token,
        "username": user['username'],
        "first_name": user['first_name'],
        "last_name": user['last_name'],
    }), 201


@accounts_bp.post("/login")
def login():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Username and password required"}), 400

    username = body.get('username')
    password = body.get('password')
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    user = get_user(username)
    if user is None or not check_password_hash(user.get('password'), password):
        return jsonify({"error": "Invalid username or password"}), 401

    access_token = create_access_token(identity=str(user['id']))
    return jsonify({
        "access_token": access_token,
        "username": user['username'],
        "first_name": user['first_name'],
        "last_name": user['last_name'],
    }), 200


@accounts_bp.patch("/name")
@jwt_required()
def update_name():
    account_id = int(get_jwt_identity())
    body = request.get_json()
    first_name = body.get('first_name')
    last_name = body.get('last_name')
    if not first_name or not last_name:
        return jsonify({"error": "First name and last name required"}), 400

    update_account_name(account_id, first_name, last_name)
    return jsonify({"first_name": first_name, "last_name": last_name}), 200


@accounts_bp.get("/balance")
@jwt_required()
def get_balance():
    account_id = int(get_jwt_identity())
    try:
        balance = get_account_balance(account_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"account_id": account_id, "balance": float(balance)}), 200


@accounts_bp.get("/transactions")
@jwt_required()
def get_cash_transactions_route():
    account_id = int(get_jwt_identity())
    try:
        transactions = get_transactions(account_id, include_cash_transactions=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    cash_transactions = [tx for tx in transactions if tx['type'] in ('deposit', 'withdrawal')]
    return jsonify(cash_transactions), 200


@accounts_bp.post("/deposit")
@jwt_required()
def deposit():
    account_id = int(get_jwt_identity())
    data = request.get_json(silent=True)
    amount, error = _parse_amount(data)
    if error:
        return jsonify({"error": error}), 400

    deposit_cash(account_id, amount)
    balance = get_account_balance(account_id)
    return jsonify({"account_id": account_id, "balance": float(balance)}), 201


@accounts_bp.post("/withdraw")
@jwt_required()
def withdraw():
    account_id = int(get_jwt_identity())
    data = request.get_json(silent=True)
    amount, error = _parse_amount(data)
    if error:
        return jsonify({"error": error}), 400

    try:
        withdraw_cash(account_id, amount)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    balance = get_account_balance(account_id)
    return jsonify({"account_id": account_id, "balance": float(balance)}), 201


def _parse_amount(data):
    if not data or "amount" not in data:
        return None, "amount is required"

    return parse_positive_amount(data["amount"])