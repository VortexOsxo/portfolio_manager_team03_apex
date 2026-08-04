from unittest.mock import patch

import pytest

ACCOUNT_ID = 1


@pytest.fixture()
def client(app):
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


class TestGetTransactionsRoute:
    @patch("flaskr.blueprints.transactions_bp.get_transactions")
    def test_returns_all_transactions_when_no_ticker_filter_given(self, mock_get_transactions, client):
        mock_get_transactions.return_value = [
            {"tr_id": 1, "ticker": "AAPL", "amount": 10, "cost_basis": 100.0, "transaction_date": "2026-01-01"},
            {"tr_id": 2, "ticker": "MSFT", "amount": 5, "cost_basis": 200.0, "transaction_date": "2026-01-02"},
        ]

        response = client.get("/transactions/")

        assert response.status_code == 200
        assert len(response.get_json()) == 2
        mock_get_transactions.assert_called_once_with(ACCOUNT_ID, ticker=None)

    @patch("flaskr.blueprints.transactions_bp.get_transactions")
    def test_filters_by_ticker_query_param(self, mock_get_transactions, client):
        mock_get_transactions.return_value = [
            {"tr_id": 1, "ticker": "AAPL", "amount": 10, "cost_basis": 100.0, "transaction_date": "2026-01-01"},
        ]

        response = client.get("/transactions/?ticker=AAPL")

        assert response.status_code == 200
        assert response.get_json()[0]["ticker"] == "AAPL"
        mock_get_transactions.assert_called_once_with(ACCOUNT_ID, ticker="AAPL")

    @patch("flaskr.blueprints.transactions_bp.get_transactions")
    def test_db_failure_returns_500_with_json_error(self, mock_get_transactions, client):
        mock_get_transactions.side_effect = Exception("db connection lost")

        response = client.get("/transactions/")

        assert response.status_code == 500
        assert response.get_json() == {"error": "db connection lost"}
