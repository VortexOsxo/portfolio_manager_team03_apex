from unittest.mock import patch

import pytest

VALID_SIGNUP_FIELDS = {"first_name": "Jane", "last_name": "Doe"}


@pytest.fixture()
def auth_client(app):
    """Test client that automatically attaches a valid JWT for account id 1."""
    from flask_jwt_extended import create_access_token

    with app.app_context():
        token = create_access_token(identity="1")

    test_client = app.test_client()
    _orig_open = test_client.open

    def open_with_jwt(*args, **kwargs):
        headers = kwargs.pop("headers", {})
        if isinstance(headers, dict):
            headers = {**headers, "Authorization": f"Bearer {token}"}
        return _orig_open(*args, headers=headers, **kwargs)

    test_client.open = open_with_jwt
    return test_client


class TestSignupValidation:
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


class TestLoginValidation:
    def test_rejects_empty_credentials(self, client):
        response = client.post("/accounts/login", json={"username": "", "password": ""})

        assert response.status_code == 400
        assert "required" in response.get_json()["error"]


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
        mock_update_account_name.assert_called_once_with(1, "Jane", "Doe")
