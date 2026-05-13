import pytest


@pytest.mark.integration
class TestMemoryRoutes:
    async def test_get_memory_requires_auth(self, app_client):
        response = await app_client.get("/api/memory")
        assert response.status_code == 401

    async def test_get_memory_empty_list(self, app_client, auth_headers):
        response = await app_client.get("/api/memory", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_add_memory_requires_auth(self, app_client):
        response = await app_client.post("/api/memory", json={"content": "test"})
        assert response.status_code == 401

    async def test_add_memory_success(self, app_client, auth_headers):
        payload = {
            "content": "Test memory from integration test",
            "user_name": "TestUser",
            "source": "integration_test",
        }
        response = await app_client.post("/api/memory", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == payload["content"]
        assert "id" in data

    async def test_add_memory_same_base_content(self, app_client, auth_headers):
        payload = {"content": "Same base content duplicate test", "user_name": "Tester", "source": "test"}
        r1 = await app_client.post("/api/memory", json=payload, headers=auth_headers)
        assert r1.status_code == 200

        r2 = await app_client.post("/api/memory", json=payload, headers=auth_headers)
        assert r2.status_code == 200

    async def test_delete_memory_not_found(self, app_client, auth_headers):
        response = await app_client.delete("/api/memory/99999", headers=auth_headers)
        assert response.status_code == 404

    async def test_delete_memory_success(self, app_client, auth_headers):
        payload = {"content": "Memory to delete", "user_name": "Tester", "source": "test"}
        r = await app_client.post("/api/memory", json=payload, headers=auth_headers)
        memory_id = r.json()["id"]

        response = await app_client.delete(f"/api/memory/{memory_id}", headers=auth_headers)
        assert response.status_code == 204

    async def test_update_memory_not_found(self, app_client, auth_headers):
        response = await app_client.put("/api/memory/99999", json={"content": "updated"}, headers=auth_headers)
        assert response.status_code == 404

    async def test_update_memory_success(self, app_client, auth_headers):
        payload = {"content": "Memory to update", "user_name": "Tester", "source": "test"}
        r = await app_client.post("/api/memory", json=payload, headers=auth_headers)
        memory_id = r.json()["id"]

        response = await app_client.put(f"/api/memory/{memory_id}", json={"content": "Updated content"}, headers=auth_headers)
        assert response.status_code == 204

    async def test_clear_memory_requires_auth(self, app_client):
        response = await app_client.post("/api/memory/clear", json={"channel_id": "12345"})
        assert response.status_code == 401

    async def test_clear_memory_success(self, app_client, auth_headers):
        response = await app_client.post("/api/memory/clear", json={"channel_id": "12345"}, headers=auth_headers)
        assert response.status_code == 200
        assert "Memory for channel" in response.json()["message"]


@pytest.mark.integration
class TestWorldBookRoutes:
    async def test_get_worldbook_requires_auth(self, app_client):
        response = await app_client.get("/api/worldbook")
        assert response.status_code == 401

    async def test_get_worldbook_empty(self, app_client, auth_headers):
        response = await app_client.get("/api/worldbook", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_add_worldbook_requires_auth(self, app_client):
        response = await app_client.post("/api/worldbook", json={"keywords": "test", "content": "test"})
        assert response.status_code == 401

    async def test_add_worldbook_success(self, app_client, auth_headers):
        payload = {"keywords": "lore, test", "content": "A world book entry for testing"}
        response = await app_client.post("/api/worldbook", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["keywords"] == payload["keywords"]
        assert data["content"] == payload["content"]
        assert "id" in data

    async def test_update_worldbook_not_found(self, app_client, auth_headers):
        payload = {"keywords": "test", "content": "test", "enabled": True}
        response = await app_client.put("/api/worldbook/99999", json=payload, headers=auth_headers)
        assert response.status_code == 404

    async def test_update_worldbook_success(self, app_client, auth_headers):
        r = await app_client.post("/api/worldbook", json={"keywords": "old", "content": "Old content"}, headers=auth_headers)
        entry_id = r.json()["id"]

        response = await app_client.put(f"/api/worldbook/{entry_id}", json={"keywords": "new", "content": "New content", "enabled": True}, headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["content"] == "New content"

    async def test_delete_worldbook_not_found(self, app_client, auth_headers):
        response = await app_client.delete("/api/worldbook/99999", headers=auth_headers)
        assert response.status_code == 404

    async def test_delete_worldbook_success(self, app_client, auth_headers):
        r = await app_client.post("/api/worldbook", json={"keywords": "temp", "content": "To delete"}, headers=auth_headers)
        entry_id = r.json()["id"]

        response = await app_client.delete(f"/api/worldbook/{entry_id}", headers=auth_headers)
        assert response.status_code == 204


@pytest.mark.integration
class TestMemoryCandidatesRoutes:
    async def test_get_candidates_requires_auth(self, app_client):
        response = await app_client.get("/api/memory/candidates")
        assert response.status_code == 401

    async def test_get_candidates_empty(self, app_client, auth_headers):
        response = await app_client.get("/api/memory/candidates", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_promote_candidate_not_found(self, app_client, auth_headers):
        response = await app_client.post("/api/memory/candidates/99999/promote", headers=auth_headers)
        assert response.status_code == 404

    async def test_delete_candidate_not_found(self, app_client, auth_headers):
        response = await app_client.delete("/api/memory/candidates/99999", headers=auth_headers)
        assert response.status_code == 404
