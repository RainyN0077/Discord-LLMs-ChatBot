import pytest


@pytest.mark.integration
class TestConfigRoutes:
    async def test_get_config_returns_data(self, app_client):
        response = await app_client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "api_secret_key" in data
        assert "system_prompt" in data

    async def test_get_config_no_auth_required(self, app_client):
        response = await app_client.get("/api/config")
        assert response.status_code == 200

    async def test_post_config_requires_auth(self, app_client):
        response = await app_client.post("/api/config", json={})
        assert response.status_code in (401, 403)

    async def test_post_config_with_auth_invalid_body(self, app_client, auth_headers):
        response = await app_client.post("/api/config", json={"invalid": "body"}, headers=auth_headers)
        assert response.status_code == 422

    async def test_post_config_with_wrong_api_key(self, app_client, bad_auth_headers):
        response = await app_client.post("/api/config", json={}, headers=bad_auth_headers)
        assert response.status_code == 403
