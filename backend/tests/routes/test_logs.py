import pytest


@pytest.mark.integration
class TestLogsRoutes:
    async def test_get_logs_requires_auth(self, app_client):
        response = await app_client.get("/api/logs")
        assert response.status_code in (401, 403)

    async def test_get_logs_returns_response(self, app_client, auth_headers):
        response = await app_client.get("/api/logs", headers=auth_headers)
        assert response.status_code == 200
