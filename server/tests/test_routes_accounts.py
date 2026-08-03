from decimal import Decimal
from unittest.mock import patch


class TestGetBalanceRoute:
    @patch("flaskr.blueprints.accounts_bp.get_account_balance")
    def test_returns_balance(self, mock_get_balance, client):
        mock_get_balance.return_value = Decimal("25000.00")

        response = client.get("/accounts/balance")

        assert response.status_code == 200
        assert response.get_json() == {"account_id": 1, "balance": 25000.0}

    @patch("flaskr.blueprints.accounts_bp.get_account_balance")
    def test_missing_account_surfaces_as_a_bare_500_not_a_json_error(self, mock_get_balance, client):
        # No try/except around get_account_balance here either, unlike
        # /accounts/deposit and /withdraw's clean 400 JSON errors.
        mock_get_balance.side_effect = ValueError("Account 1 not found")

        response = client.get("/accounts/balance")

        assert response.status_code == 500
        assert response.get_json() is None


class TestDepositRoute:
    @patch("flaskr.blueprints.accounts_bp.deposit_cash")
    @patch("flaskr.blueprints.accounts_bp.get_account_balance")
    def test_happy_path_credits_the_account(self, mock_get_balance, mock_deposit, client):
        mock_get_balance.return_value = Decimal("25100.00")

        response = client.post("/accounts/deposit", json={"amount": 100})

        assert response.status_code == 201
        assert response.get_json() == {"account_id": 1, "balance": 25100.0}
        mock_deposit.assert_called_once_with(Decimal("100"))

    def test_no_body_returns_400_with_json_error(self, client):
        # deposit/withdraw use get_json(silent=True), unlike buy/sell -- a
        # missing/malformed body degrades to a clean 400 here instead of 415.
        response = client.post("/accounts/deposit")

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount is required"}

    def test_null_amount_returns_400(self, client):
        # "amount" is present (key exists, value None) so this skips the
        # "amount is required" branch and fails Decimal(str(None)) instead.
        response = client.post("/accounts/deposit", json={"amount": None})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be a number"}

    def test_zero_amount_returns_400(self, client):
        response = client.post("/accounts/deposit", json={"amount": 0})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be greater than zero"}

    def test_negative_amount_returns_400(self, client):
        response = client.post("/accounts/deposit", json={"amount": -5})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be greater than zero"}

    def test_non_numeric_amount_returns_400(self, client):
        response = client.post("/accounts/deposit", json={"amount": "abc"})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be a number"}

    def test_nan_amount_returns_400(self, client):
        # parse_positive_amount checks is_nan() before ever comparing with
        # <= 0, so this is now a clean rejection instead of a crash.
        response = client.post("/accounts/deposit", json={"amount": "NaN"})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be a number"}

    def test_infinity_amount_returns_400(self, client):
        # parse_positive_amount now checks is_infinite() explicitly, since
        # Decimal("Infinity") <= 0 is False and would otherwise pass through.
        response = client.post("/accounts/deposit", json={"amount": "Infinity"})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount must be a finite number"}

    def test_amount_finer_than_cents_returns_400(self, client):
        # The accounts.balance column is decimal(15,2); parse_positive_amount
        # now rejects anything with more than 2 fractional digits.
        response = client.post("/accounts/deposit", json={"amount": 0.001})

        assert response.status_code == 400
        assert response.get_json() == {"error": "amount cannot have more than 2 decimal places"}


class TestWithdrawRoute:
    # The balance check and the lock now both live inside withdraw_cash
    # (see TestWithdrawCash in test_database.py for the "insufficient
    # funds" and "exactly the full balance" boundary cases, and for the
    # FOR UPDATE lock that closes the race the old route-level check used
    # to leave open) -- these route tests just cover request wiring.
    @patch("flaskr.blueprints.accounts_bp.withdraw_cash")
    @patch("flaskr.blueprints.accounts_bp.get_account_balance")
    def test_happy_path_debits_the_account(self, mock_get_balance, mock_withdraw, client):
        mock_get_balance.return_value = Decimal("24900.00")

        response = client.post("/accounts/withdraw", json={"amount": 100})

        assert response.status_code == 201
        assert response.get_json() == {"account_id": 1, "balance": 24900.0}
        mock_withdraw.assert_called_once_with(Decimal("100"))

    @patch("flaskr.blueprints.accounts_bp.withdraw_cash")
    def test_withdrawing_more_than_balance_returns_400(self, mock_withdraw, client):
        mock_withdraw.side_effect = ValueError(
            "Insufficient funds: withdrawal of 100.01 exceeds available balance of 100.00"
        )

        response = client.post("/accounts/withdraw", json={"amount": 100.01})

        assert response.status_code == 400
        assert response.get_json() == {
            "error": "Insufficient funds: withdrawal of 100.01 exceeds available balance of 100.00"
        }
