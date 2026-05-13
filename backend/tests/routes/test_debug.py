import pytest


@pytest.mark.integration
class TestDebugRoutes:
    async def test_simulate_requires_auth(self, app_client):
        response = await app_client.post("/api/debug/simulate", json={
            "user_id": "123",
            "channel_id": "456",
            "message_content": "test",
        })
        assert response.status_code == 401

    async def test_get_captures_requires_auth(self, app_client):
        response = await app_client.get("/api/debug/captures")
        assert response.status_code == 401

    async def test_get_captures_empty(self, app_client, auth_headers):
        response = await app_client.get("/api/debug/captures", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_capture_detail_not_found(self, app_client, auth_headers):
        response = await app_client.get("/api/debug/captures/nonexistent_id", headers=auth_headers)
        assert response.status_code in (200, 404)

    async def test_sanitize_requires_auth(self, app_client):
        response = await app_client.post("/api/debug/sanitize", json={"text": "test"})
        assert response.status_code == 401

    async def test_sanitize_success(self, app_client, auth_headers):
        response = await app_client.post("/api/debug/sanitize", json={"text": "<dsml|>some thinking</dsml|> actual text"}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "sanitized_text" in data
        assert "original_text" in data
