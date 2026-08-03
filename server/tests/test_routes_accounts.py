from unittest.mock import patch


class TestSignupValidation:
    def test_rejects_short_username(self, client):
        response = client.post("/accounts/signup", json={"username": "e", "password": "longenough123"})

        assert response.status_code == 400
        assert "3 characters" in response.get_json()["error"]

    def test_rejects_short_password(self, client):
        response = client.post("/accounts/signup", json={"username": "validuser", "password": "abc"})

        assert response.status_code == 400
        assert "8 characters" in response.get_json()["error"]

    def test_rejects_empty_username(self, client):
        response = client.post("/accounts/signup", json={"username": "", "password": "longenough123"})

        assert response.status_code == 400
        assert "required" in response.get_json()["error"]

    @patch("flaskr.blueprints.accounts_bp.create_user")
    @patch("flaskr.blueprints.accounts_bp.get_user")
    def test_accepts_valid_credentials(self, mock_get_user, mock_create_user, client):
        mock_create_user.return_value = True
        mock_get_user.return_value = {"id": 1, "username": "validuser"}

        response = client.post("/accounts/signup", json={"username": "validuser", "password": "longenough123"})

        assert response.status_code == 201
        assert response.get_json()["username"] == "validuser"


class TestLoginValidation:
    def test_rejects_empty_credentials(self, client):
        response = client.post("/accounts/login", json={"username": "", "password": ""})

        assert response.status_code == 400
        assert "required" in response.get_json()["error"]
