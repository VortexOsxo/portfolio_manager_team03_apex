from decimal import Decimal
from unittest.mock import patch

import pytest

ACCOUNT_ID = 1
VALID_SIGNUP_FIELDS = {"first_name": "Jane", "last_name": "Doe"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def auth_client(app):
    """Test client that automatically attaches a valid JWT for ACCOUNT_ID."""
    from flask_jwt_extended import create_access_token

    with app.app_context():
        token = create_access_token(identity=str(ACCOUNT_ID))

    test_client = app.test_client()
    _orig_open = test_client.open

    def open_with_jwt(*args, **kwargs):
        headers = kwargs.pop("headers", {})
        if isinstance(headers, dict):
            headers = {**headers, "Authorization": f"Bearer {token}"}
        return _orig_open(*args, headers=headers, **kwargs)

    test_client.open = open_with_jwt
    return test_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSignupRoute:
    @patch("flaskr.blueprints.accounts_bp.get_user")
    @patch("flaskr.blueprints.accounts_bp.create_user")
    def test_happy_path_creates_the_user_and_returns_a_token(self, mock_create_user, mock_get_user, client):
        mock_create_user.return_value = True
        mock_get_user.return_value = {
            "id": ACCOUNT_ID,
            "username": "alice",
            "password": "hashed",
            "first_name": "Jane",
            "last_name": "Doe",
            "balance": 0,
        }

        response = client.post(
            "/accounts/signup",
            json={"username": "alice", "password": "hunter22", **VALID_SIGNUP_FIELDS},
        )

        assert response.status_code == 201
        body = response.get_json()
        assert body["username"] == "alice"
        assert "access_token" in body

    def test_missing_username_or_password_returns_400(self, client):
        response = client.post("/accounts/signup", json={"username": "alice", **VALID_SIGNUP_FIELDS})

        assert response.status_code == 400
        assert response.get_json() == {"error": "Username, password, first name, and last name required"}

    def test_no_body_returns_400(self, client):
        response = client.post("/accounts/signup", json={})

        assert response.status_code == 400
        assert response.get_json() == {"error": "Username and password required"}

    @patch("flaskr.blueprints.accounts_bp.create_user")
    def test_duplicate_username_returns_409(self, mock_create_user, client):
        mock_create_user.return_value = False

        response = client.post(
            "/accounts/signup",
            json={"username": "alice", "password": "hunter22", **VALID_SIGNUP_FIELDS},
        )

        assert response.status_code == 409
        assert response.get_json() == {"error": "Username already taken"}

    def test_rejects_short_username(self, client):
        response = client.post(
            "/accounts/signup",
            json={"username": "e", "password": "longenough123", **VALID_SIGNUP_FIELDS},
        )

        assert response.status_code == 400
        assert "3 characters" in response.get_json()["error"]

    def test_rejects_short_password(self, client):
        response = client.post(
            "/accounts/signup",
            json={"username": "validuser", "password": "abc", **VALID_SIGNUP_FIELDS},
        )

        assert response.status_code == 400
        assert "8 characters" in response.get_json()["error"]

    def test_rejects_empty_username(self, client):
        response = client.post(
            "/accounts/signup",
            json={"username": "", "password": "longenough123", **VALID_SIGNUP_FIELDS},
        )

        assert response.status_code == 400
        assert "required" in response.get_json()["error"]

    def test_rejects_missing_name(self, client):
        response = client.post(
            "/accounts/signup",
            json={"username": "validuser", "password": "longenough123", "first_name": "Jane"},
        )

        assert response.status_code == 400
        assert "required" in response.get_json()["error"]

    @patch("flaskr.blueprints.accounts_bp.create_user")
    @patch("flaskr.blueprints.accounts_bp.get_user")
    def test_accepts_valid_credentials(self, mock_get_user, mock_create_user, client):
        mock_create_user.return_value = True
        mock_get_user.return_value = {
            "id": 1,
            "username": "validuser",
            "first_name": "Jane",
            "last_name": "Doe",
        }

        response = client.post(
            "/accounts/signup",
            json={"username": "validuser", "password": "longenough123", **VALID_SIGNUP_FIELDS},
        )

        assert response.status_code == 201
        body = response.get_json()
        assert body["username"] == "validuser"
        assert body["first_name"] == "Jane"
        assert body["last_name"] == "Doe"


class TestLoginRoute:
    @patch("flaskr.blueprints.accounts_bp.get_user")
    @patch("flaskr.blueprints.accounts_bp.check_password_hash")
    def test_happy_path_returns_a_token(self, mock_check_hash, mock_get_user, client):
        mock_get_user.return_value = {
            "id": ACCOUNT_ID,
            "username": "alice",
            "password": "hashed",
            "first_name": "Jane",
            "last_name": "Doe",
            "balance": 0,
        }
        mock_check_hash.return_value = True

        response = client.post("/accounts/login", json={"username": "alice", "password": "hunter22"})

        assert response.status_code == 200
        body = response.get_json()
        assert body["username"] == "alice"
        assert "access_token" in body

    def test_missing_username_or_password_returns_400(self, client):
        response = client.post("/accounts/login", json={"username": "alice"})

        assert response.status_code == 400
        assert response.get_json() == {"error": "Username and password required"}

    def test_no_body_returns_400(self, client):
        response = client.post("/accounts/login", json={})

        assert response.status_code == 400
        assert response.get_json() == {"error": "Username and password required"}

    def test_rejects_empty_credentials(self, client):
        response = client.post("/accounts/login", json={"username": "", "password": ""})

        assert response.status_code == 400
        assert "required" in response.get_json()["error"]

    @patch("flaskr.blueprints.accounts_bp.get_user")
    def test_unknown_username_returns_401(self, mock_get_user, client):
        mock_get_user.return_value = None

        response = client.post("/accounts/login", json={"username": "nobody", "password": "hunter22"})

        assert response.status_code == 401
        assert response.get_json() == {"error": "Invalid username or password"}

    @patch("flaskr.blueprints.accounts_bp.get_user")
    @patch("flaskr.blueprints.accounts_bp.check_password_hash")
    def test_wrong_password_returns_401(self, mock_check_hash, mock_get_user, client):
        mock_get_user.return_value = {"id": ACCOUNT_ID, "username": "alice", "password": "hashed", "balance": 0}
        mock_check_hash.return_value = False

        response = client.post("/accounts/login", json={"username": "alice", "password": "wrong123"})

        assert response.status_code == 401
        assert response.get_json() == {"error": "Invalid username or password"}


class TestUpdateName:
    def test_requires_auth(self, client):
        response = client.patch("/accounts/name", json={"first_name": "Jane", "last_name": "Doe"})

        assert response.status_code == 401

    def test_rejects_missing_fields(self, auth_client):
        response = auth_client.patch("/accounts/name", json={"first_name": "Jane"})

        assert response.status_code == 400
        assert "required" in response.get_json()["error"]

    @patch("flaskr.blueprints.accounts_bp.update_account_name")
    def test_accepts_valid_name(self, mock_update_account_name, auth_client):
        response = auth_client.patch("/accounts/name", json={"first_name": "Jane", "last_name": "Doe"})

        assert response.status_code == 200
        body = response.get_json()
        assert body["first_name"] == "Jane"
        assert body["last_name"] == "Doe"
        mock_update_account_name.assert_called_once_with(ACCOUNT_ID, "Jane", "Doe")


class TestGetBalanceRoute:
    @patch("flaskr.blueprints.accounts_bp.get_account_balance")
    def test_returns_balance(self, mock_get_balance, auth_client):
        mock_get_balance.return_value = Decimal("25000.00")

        response = auth_client.get("/accounts/balance")

        assert response.status_code == 200
        assert response.get_json() == {"account_id": ACCOUNT_ID, "balance": 25000.0}
        mock_get_balance.assert_called_once_with(ACCOUNT_ID)

    @patch("flaskr.blueprints.accounts_bp.get_account_balance")
    def test_missing_account_returns_400_with_json_error(self, mock_get_balance, auth_client):
        mock_get_balance.side_effect = ValueError(f"Account {ACCOUNT_ID} not found")

        response = auth_client.get("/accounts/balance")

        assert response.status_code == 400
        assert response.get_json() == {"error": f"Account {ACCOUNT_ID} not found"}


class TestGetCashTransactionsRoute:
    @patch("flaskr.blueprints.accounts_bp.get_transactions")
    def test_returns_only_deposit_and_withdrawal_transactions(self, mock_get_transactions, auth_client):
        mock_get_transactions.return_value = [
            {"tr_id": 1, "type": "buy", "ticker": "AAPL", "amount": 10, "cost_basis": 100.0, "transaction_date": "2026-01-01"},
            {"tr_id": 2, "type": "deposit", "ticker": None, "amount": 500, "cost_basis": None, "transaction_date": "2026-01-02"},
            {"tr_id": 3, "type": "withdrawal", "ticker": None, "amount": -200, "cost_basis": None, "transaction_date": "2026-01-03"},
        ]

        response = auth_client.get("/accounts/transactions")

        assert response.status_code == 200
        assert [tx["tr_id"] for tx in response.get_json()] == [2, 3]
        mock_get_transactions.assert_called_once_with(ACCOUNT_ID, include_cash_transactions=True)

    @patch("flaskr.blueprints.accounts_bp.get_transactions")
    def test_db_failure_returns_500_with_json_error(self, mock_get_transactions, auth_client):
        mock_get_transactions.side_effect = Exception("db connection lost")

        response = auth_client.get("/accounts/transactions")

        assert response.status_code == 500
        assert response.get_json() == {"error": "db connection lost"}


class TestDepositRoute:
    @patch("flaskr.blueprints.accounts_bp.deposit_cash")
    @patch("flaskr.blueprints.accounts_bp.get_account_balance")
    def test_happy_path_credits_the_account(self, mock_get_balance, mock_deposit, auth_client):
        mock_get_balance.return_value = Decimal("25100.00")

        response = auth_client.post("/accounts/deposit", json={"amount": 100})

        assert response.status_code == 201
        assert response.get_json() == {"account_id": ACCOUNT_ID, "balance": 25100.0}
        mock_deposit.assert_called_once_with(ACCOUNT_ID, Decimal("100"))

    def test_no_body_returns_400_with_json_error(self, auth_client):
        # deposit/withdraw use get_json(silent=True), unlike buy/sell -- a
        # missing/malformed body degrades to a clean 400 here instead of 415.
        response = auth_client.post("/accounts/deposit")

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount is required"}

    def test_null_amount_returns_400(self, auth_client):
        response = auth_client.post("/accounts/deposit", json={"amount": None})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be a number"}

    def test_zero_amount_returns_400(self, auth_client):
        response = auth_client.post("/accounts/deposit", json={"amount": 0})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be greater than zero"}

    def test_negative_amount_returns_400(self, auth_client):
        response = auth_client.post("/accounts/deposit", json={"amount": -5})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be greater than zero"}

    def test_non_numeric_amount_returns_400(self, auth_client):
        response = auth_client.post("/accounts/deposit", json={"amount": "abc"})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be a number"}

    def test_nan_amount_returns_400(self, auth_client):
        response = auth_client.post("/accounts/deposit", json={"amount": "NaN"})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be a number"}

    def test_infinity_amount_returns_400(self, auth_client):
        response = auth_client.post("/accounts/deposit", json={"amount": "Infinity"})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be a finite number"}

    def test_amount_finer_than_cents_returns_400(self, auth_client):
        response = auth_client.post("/accounts/deposit", json={"amount": 0.001})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount cannot have more than 2 decimal places"}


class TestWithdrawRoute:
    @patch("flaskr.blueprints.accounts_bp.withdraw_cash")
    @patch("flaskr.blueprints.accounts_bp.get_account_balance")
    def test_happy_path_debits_the_account(self, mock_get_balance, mock_withdraw, auth_client):
        mock_get_balance.return_value = Decimal("24900.00")

        response = auth_client.post("/accounts/withdraw", json={"amount": 100})

        assert response.status_code == 201
        assert response.get_json() == {"account_id": ACCOUNT_ID, "balance": 24900.0}
        mock_withdraw.assert_called_once_with(ACCOUNT_ID, Decimal("100"))

    @patch("flaskr.blueprints.accounts_bp.withdraw_cash")
    def test_withdrawing_more_than_balance_returns_400(self, mock_withdraw, auth_client):
        mock_withdraw.side_effect = ValueError(
            "Insufficient funds: withdrawal of 100.01 exceeds available balance of 100.00"
        )

        response = auth_client.post("/accounts/withdraw", json={"amount": 100.01})

        assert response.status_code == 400
        assert response.get_json() == {
            "error": "Insufficient funds: withdrawal of 100.01 exceeds available balance of 100.00"
        }
