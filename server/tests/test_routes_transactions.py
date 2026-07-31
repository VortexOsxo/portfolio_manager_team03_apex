from unittest.mock import patch


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
        mock_get_transactions.assert_called_once_with(None)

    @patch("flaskr.blueprints.transactions_bp.get_transactions")
    def test_filters_by_ticker_query_param(self, mock_get_transactions, client):
        mock_get_transactions.return_value = [
            {"tr_id": 1, "ticker": "AAPL", "amount": 10, "cost_basis": 100.0, "transaction_date": "2026-01-01"},
        ]

        response = client.get("/transactions/?ticker=AAPL")

        assert response.status_code == 200
        assert response.get_json()[0]["ticker"] == "AAPL"
        mock_get_transactions.assert_called_once_with("AAPL")
