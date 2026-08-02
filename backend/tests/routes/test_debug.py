import pytest


@pytest.mark.integration
class TestDebugRoutes:
    async def test_simulate_requires_auth(self, app_client):
        response = await app_client.post("/api/debug/simulate", json={
            "user_id": "123",
            "channel_id": "456",
            "message_content": "test",
        })
        assert response.status_code in (401, 403)

    async def test_get_captures_requires_auth(self, app_client):
        response = await app_client.get("/api/debug/captures")
        assert response.status_code in (401, 403)

    async def test_get_captures_empty(self, app_client, auth_headers):
        response = await app_client.get("/api/debug/captures", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_capture_detail_not_found(self, app_client, auth_headers):
        response = await app_client.get("/api/debug/captures/nonexistent_id", headers=auth_headers)
        assert response.status_code == 404

    async def test_sanitize_requires_auth(self, app_client):
        response = await app_client.post("/api/debug/sanitize", json={"text": "test"})
        assert response.status_code in (401, 403)

    async def test_sanitize_success(self, app_client, auth_headers):
        response = await app_client.post("/api/debug/sanitize", json={"text": "<dsml|>some thinking</dsml|> actual text"}, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "sanitized_text" in data
        assert "original_text" in data

    # --- S0: DELETE 端点（M3：conftest 不清 debug_capture_store 模块级全局，用例内显式清空隔离） ---

    async def test_delete_capture_requires_auth(self, app_client):
        response = await app_client.delete("/api/debug/captures/some-id")
        assert response.status_code in (401, 403)

    async def test_delete_capture_not_found(self, app_client, auth_headers):
        from app import debug_capture_store
        debug_capture_store._captures.clear()
        response = await app_client.delete("/api/debug/captures/nonexistent_id", headers=auth_headers)
        assert response.status_code == 404
        assert response.json() == {"detail": "Capture not found."}

    async def test_delete_capture_success(self, app_client, auth_headers):
        from app import debug_capture_store
        debug_capture_store._captures.clear()
        item = await debug_capture_store.add_capture({"message": "hello"})
        response = await app_client.delete(f"/api/debug/captures/{item['id']}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"message": f"Capture '{item['id']}' deleted."}
        assert await debug_capture_store.get_capture(item["id"]) is None

    async def test_clear_captures_success(self, app_client, auth_headers):
        from app import debug_capture_store
        debug_capture_store._captures.clear()
        await debug_capture_store.add_capture({"n": 1})
        await debug_capture_store.add_capture({"n": 2})
        response = await app_client.delete("/api/debug/captures", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"message": "All debug captures cleared (2)."}
        list_response = await app_client.get("/api/debug/captures", headers=auth_headers)
        assert list_response.status_code == 200
        assert list_response.json() == []
