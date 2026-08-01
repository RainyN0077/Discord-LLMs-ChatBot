"""Tests for interactions routes.

Covers:
  - Authentication protection on all endpoints
  - reconstruct_context endpoint (C1 fix: correct parameter passing)
  - Basic CRUD: list tree, members, messages, images, usage, delete, prune
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True)
def _mock_interaction_recorder(monkeypatch):
    """Replace get_interaction_recorder with a mock for all interaction tests."""
    mock_recorder = MagicMock()
    mock_recorder.list_tree = AsyncMock(return_value=[])
    mock_recorder.list_members = AsyncMock(return_value=[])
    mock_recorder.read_messages = AsyncMock(return_value=[])
    mock_recorder.get_disk_usage = AsyncMock(return_value=1024)
    mock_recorder.delete_records = AsyncMock(return_value=5)
    mock_recorder.prune_oldest = AsyncMock(return_value=3)

    import app.routers.interactions as interactions_mod
    monkeypatch.setattr(interactions_mod, "get_interaction_recorder", lambda: mock_recorder)
    return mock_recorder


class TestInteractionsAuth:
    """All interaction endpoints should require authentication."""

    async def test_tree_requires_auth(self, app_client):
        response = await app_client.get("/api/interactions/test-bot/tree")
        assert response.status_code in (401, 403)

    async def test_members_requires_auth(self, app_client):
        response = await app_client.get("/api/interactions/test-bot/members?guild_id=123")
        assert response.status_code in (401, 403)

    async def test_messages_requires_auth(self, app_client):
        url = "/api/interactions/test-bot/messages?guild_id=1&role_id=2&channel_id=3&member_id=4&date=2025-01-01"
        response = await app_client.get(url)
        assert response.status_code in (401, 403)

    async def test_images_requires_auth(self, app_client):
        url = "/api/interactions/test-bot/images?guild_id=1&role_id=2&channel_id=3&member_id=4&date=2025-01-01"
        response = await app_client.get(url)
        assert response.status_code in (401, 403)

    async def test_image_file_requires_auth(self, app_client):
        url = "/api/interactions/test-bot/image-file?guild_id=1&role_id=2&channel_id=3&member_id=4&date=2025-01-01&filename=test.png"
        response = await app_client.get(url)
        assert response.status_code in (401, 403)

    async def test_usage_requires_auth(self, app_client):
        response = await app_client.get("/api/interactions/test-bot/usage")
        assert response.status_code in (401, 403)

    async def test_delete_requires_auth(self, app_client):
        response = await app_client.delete("/api/interactions/test-bot/delete")
        assert response.status_code in (401, 403)

    async def test_prune_requires_auth(self, app_client):
        response = await app_client.post("/api/interactions/test-bot/prune")
        assert response.status_code in (401, 403)

    async def test_context_requires_auth(self, app_client):
        url = "/api/interactions/test-bot/context?guild_id=1&role_id=2&channel_id=3&member_id=4&date=2025-01-01"
        response = await app_client.post(url)
        assert response.status_code in (401, 403)


class TestInteractionsEndpoints:
    """Interaction endpoints should return expected responses when authenticated."""

    async def test_get_tree_returns_items(self, app_client, auth_headers):
        response = await app_client.get("/api/interactions/test-bot/tree", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    async def test_get_tree_with_filters(self, app_client, auth_headers):
        response = await app_client.get(
            "/api/interactions/test-bot/tree?guild_id=111",
            headers=auth_headers,
        )
        assert response.status_code == 200

    async def test_get_members_returns_list(self, app_client, auth_headers):
        response = await app_client.get(
            "/api/interactions/test-bot/members?guild_id=111",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "members" in data

    async def test_get_messages_returns_list(self, app_client, auth_headers):
        response = await app_client.get(
            "/api/interactions/test-bot/messages?guild_id=1&role_id=2&channel_id=3&member_id=4&date=2025-01-01",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data

    async def test_get_images_returns_list(self, app_client, auth_headers):
        response = await app_client.get(
            "/api/interactions/test-bot/images?guild_id=1&role_id=2&channel_id=3&member_id=4&date=2025-01-01",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "images" in data

    async def test_usage_returns_stats(self, app_client, auth_headers):
        response = await app_client.get("/api/interactions/test-bot/usage", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "used_bytes" in data
        assert "max_bytes" in data
        assert "percent" in data

    async def test_delete_returns_count(self, app_client, auth_headers):
        response = await app_client.delete("/api/interactions/test-bot/delete", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "deleted" in data
        assert data["deleted"] == 5

    async def test_delete_with_filters(self, app_client, auth_headers):
        response = await app_client.delete(
            "/api/interactions/test-bot/delete?guild_id=111",
            headers=auth_headers,
        )
        assert response.status_code == 200

    async def test_prune_returns_count(self, app_client, auth_headers):
        response = await app_client.post("/api/interactions/test-bot/prune", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "pruned" in data
        assert data["pruned"] == 3


class TestInteractionsReconstructContext:
    """reconstruct_context endpoint should work with valid parameters."""

    async def test_reconstruct_context_no_messages(self, app_client, auth_headers, _mock_interaction_recorder):
        """When no messages found, should return context: None."""
        _mock_interaction_recorder.read_messages.return_value = []

        response = await app_client.post(
            "/api/interactions/test-bot/context"
            "?guild_id=111&role_id=222&channel_id=333&member_id=444&date=2025-01-01",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["context"] is None
        assert "No messages found" in data.get("message", "")

    async def test_reconstruct_context_with_messages(self, app_client, auth_headers, _mock_interaction_recorder):
        """When messages exist, should return system_prompt and formatted_messages."""
        _mock_interaction_recorder.read_messages.return_value = [
            {
                "timestamp": "2025-01-01T12:00:00",
                "author_id": "444",
                "author_name": "TestUser",
                "content": "Hello bot!",
                "attachments": [],
            }
        ]

        response = await app_client.post(
            "/api/interactions/test-bot/context"
            "?guild_id=111&role_id=222&channel_id=333&member_id=444&date=2025-01-01",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "system_prompt" in data
        assert "messages" in data
        assert len(data["messages"]) >= 1

    async def test_reconstruct_context_passes_correct_params(self, app_client, auth_headers, _mock_interaction_recorder):
        """Verify that gid/rid/cid/mid/date are correctly passed to read_messages."""
        _mock_interaction_recorder.read_messages.return_value = []

        await app_client.post(
            "/api/interactions/test-bot/context"
            "?guild_id=111&role_id=222&channel_id=333&member_id=444&date=2025-01-01",
            headers=auth_headers,
        )

        _mock_interaction_recorder.read_messages.assert_called_once_with(
            "test-bot", "111", "222", "333", "444", "2025-01-01",
        )

    async def test_reconstruct_context_bad_auth(self, app_client):
        """reconstruct_context should be protected by auth."""
        response = await app_client.post(
            "/api/interactions/test-bot/context"
            "?guild_id=111&role_id=222&channel_id=333&member_id=444&date=2025-01-01",
        )
        assert response.status_code in (401, 403)
