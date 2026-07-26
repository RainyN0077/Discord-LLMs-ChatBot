import pytest


@pytest.mark.integration
class TestModelsRoutes:
    async def test_list_models_requires_auth(self, app_client):
        response = await app_client.post("/api/models/list", json={"provider": "openai", "api_key": "sk-test", "task": "chat"})
        assert response.status_code == 403

    async def test_test_model_requires_auth(self, app_client):
        response = await app_client.post("/api/models/test", json={"provider": "openai", "api_key": "sk-test", "model_name": "gpt-4o"})
        assert response.status_code == 403

    async def test_list_models_invalid_provider(self, app_client, auth_headers):
        response = await app_client.post("/api/models/list", json={"provider": "invalid_provider", "api_key": "sk-test", "task": "chat"}, headers=auth_headers)
        assert response.status_code == 400
