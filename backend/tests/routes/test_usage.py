import pytest


@pytest.mark.integration
class TestUsageRoutes:
    async def test_get_usage_requires_auth(self, app_client):
        response = await app_client.get("/api/usage/stats")
        assert response.status_code in (401, 403)

    async def test_get_usage_stats_today(self, app_client, auth_headers):
        response = await app_client.get("/api/usage/stats?period=today&view=user", headers=auth_headers)
        assert response.status_code == 200

    async def test_get_pricing_requires_auth(self, app_client):
        response = await app_client.get("/api/usage/pricing")
        assert response.status_code in (401, 403)

    async def test_get_pricing_empty(self, app_client, auth_headers):
        response = await app_client.get("/api/usage/pricing", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "pricing" in data

    async def test_post_pricing_requires_auth(self, app_client):
        response = await app_client.post("/api/usage/pricing", json={})
        assert response.status_code in (401, 403)

    async def test_post_pricing_success(self, app_client, auth_headers):
        response = await app_client.post("/api/usage/pricing", json={"model": "gpt-4o", "price": 0.01}, headers=auth_headers)
        assert response.status_code == 200
        assert "Pricing updated" in response.json()["message"]
