import pytest


@pytest.mark.integration
class TestChatRoutes:
    async def test_direct_chat_requires_auth(self, app_client):
        response = await app_client.post("/api/chat/direct", json={
            "messages": [{"role": "user", "content": "Hello"}],
        })
        assert response.status_code == 403

    async def test_direct_chat_empty_messages(self, app_client, auth_headers):
        response = await app_client.post("/api/chat/direct", json={
            "messages": [],
        }, headers=auth_headers)
        assert response.status_code == 400

    async def test_direct_chat_without_messages_field(self, app_client, auth_headers):
        response = await app_client.post("/api/chat/direct", json={}, headers=auth_headers)
        assert response.status_code == 400
