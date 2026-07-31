class TestFixturesSmokeTest:
    def test_client_hits_unknown_route_and_gets_404(self, client):
        response = client.get("/this-route-does-not-exist")

        assert response.status_code == 404

    def test_app_is_in_testing_mode(self, app):
        assert app.config["TESTING"] is True
