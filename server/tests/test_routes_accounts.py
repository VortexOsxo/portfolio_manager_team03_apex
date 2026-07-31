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
    @patch("flaskr.blueprints.accounts_bp.update_account_balance")
    @patch("flaskr.blueprints.accounts_bp.get_account_balance")
    def test_happy_path_credits_the_account(self, mock_get_balance, mock_update, client):
        mock_get_balance.return_value = Decimal("25100.00")

        response = client.post("/accounts/deposit", json={"amount": 100})

        assert response.status_code == 201
        assert response.get_json() == {"account_id": 1, "balance": 25100.0}
        mock_update.assert_called_once_with(Decimal("100"), account_id=1)

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
    @patch("flaskr.blueprints.accounts_bp.update_account_balance")
    @patch("flaskr.blueprints.accounts_bp.get_account_balance")
    def test_happy_path_debits_the_account(self, mock_get_balance, mock_update, client):
        mock_get_balance.return_value = Decimal("24900.00")

        response = client.post("/accounts/withdraw", json={"amount": 100})

        assert response.status_code == 201
        mock_update.assert_called_once_with(Decimal("-100"), account_id=1)

    @patch("flaskr.blueprints.accounts_bp.update_account_balance")
    @patch("flaskr.blueprints.accounts_bp.get_account_balance")
    def test_withdrawing_more_than_balance_returns_400(self, mock_get_balance, mock_update, client):
        mock_get_balance.return_value = Decimal("100.00")

        response = client.post("/accounts/withdraw", json={"amount": 100.01})

        assert response.status_code == 400
        assert response.get_json() == {"error": "Insufficient funds"}
        mock_update.assert_not_called()

    @patch("flaskr.blueprints.accounts_bp.update_account_balance")
    @patch("flaskr.blueprints.accounts_bp.get_account_balance")
    def test_withdrawing_exactly_the_full_balance_is_allowed(self, mock_get_balance, mock_update, client):
        mock_get_balance.return_value = Decimal("100.00")

        response = client.post("/accounts/withdraw", json={"amount": 100.00})

        assert response.status_code == 201
        mock_update.assert_called_once_with(Decimal("-100.0"), account_id=1)

    @patch("flaskr.blueprints.accounts_bp.update_account_balance")
    @patch("flaskr.blueprints.accounts_bp.get_account_balance")
    def test_two_withdrawals_against_a_stale_balance_both_succeed(
        self, mock_get_balance, mock_update, client
    ):
        # Documents the TOCTOU gap: the balance read and the write are two
        # separate, unlocked statements. Here get_account_balance keeps
        # returning the same starting balance regardless of the first
        # withdrawal's update call (nothing decrements it), so a second
        # concurrent-in-spirit withdrawal for the same amount also passes
        # the check -- in a real unlocked DB, both could succeed and overdraw.
        mock_get_balance.return_value = Decimal("100.00")

        first = client.post("/accounts/withdraw", json={"amount": 60})
        second = client.post("/accounts/withdraw", json={"amount": 60})

        assert first.status_code == 201
        assert second.status_code == 201
        assert mock_update.call_count == 2
