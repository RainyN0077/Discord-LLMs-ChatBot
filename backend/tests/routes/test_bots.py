import pytest
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path

from app import state


@pytest.mark.integration
class TestBotsRoutes:
    async def test_list_bots_requires_auth(self, app_client):
        response = await app_client.get("/api/bots/")
        assert response.status_code in (401, 403)

    async def test_list_bots_empty(self, app_client, auth_headers):
        state.bot_manager.list.return_value = []
        response = await app_client.get("/api/bots/", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_bots_with_data(self, app_client, auth_headers):
        state.bot_manager.list.return_value = [
            {"bot_id": "bot1", "bot_name": "Bot 1", "status": "running"},
            {"bot_id": "bot2", "bot_name": "Bot 2", "status": "stopped"},
        ]
        response = await app_client.get("/api/bots/", headers=auth_headers)
        data = response.json()
        assert len(data) == 2
        assert data[0]["bot_id"] == "bot1"

    async def test_create_bot_success(self, app_client, auth_headers):
        state.bot_manager.create = AsyncMock(return_value="new-bot")
        response = await app_client.post(
            "/api/bots/",
            json={"bot_id": "new-bot", "bot_name": "New Bot"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["bot_id"] == "new-bot"
        state.bot_manager.create.assert_awaited_once()
        call_args = state.bot_manager.create.call_args[0][0]
        assert call_args["bot_id"] == "new-bot"
        assert call_args["bot_name"] == "New Bot"

    async def test_create_bot_invalid_id(self, app_client, auth_headers):
        response = await app_client.post(
            "/api/bots/",
            json={"bot_id": "INVALID ID!!"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_create_bot_duplicate(self, app_client, auth_headers):
        state.bot_manager.create = AsyncMock(
            side_effect=ValueError("Bot 'dup-bot' already exists")
        )
        response = await app_client.post(
            "/api/bots/",
            json={"bot_id": "dup-bot"},
            headers=auth_headers,
        )
        assert response.status_code == 409

    async def test_delete_bot_success(self, app_client, auth_headers):
        mock_instance = MagicMock()
        state.bot_manager.get.return_value = mock_instance
        state.bot_manager.delete = AsyncMock()
        response = await app_client.delete("/api/bots/test-bot", headers=auth_headers)
        assert response.status_code == 200
        state.bot_manager.delete.assert_awaited_once_with("test-bot")

    async def test_delete_bot_not_found(self, app_client, auth_headers):
        state.bot_manager.get.return_value = None
        response = await app_client.delete("/api/bots/nonexistent", headers=auth_headers)
        assert response.status_code == 404

    async def test_start_bot_success(self, app_client, auth_headers):
        mock_instance = MagicMock()
        mock_instance.is_running.return_value = False
        state.bot_manager.get.return_value = mock_instance
        state.bot_manager.start = AsyncMock()
        response = await app_client.post("/api/bots/test-bot/start", headers=auth_headers)
        assert response.status_code == 200
        state.bot_manager.start.assert_awaited_once_with("test-bot")

    async def test_stop_bot_success(self, app_client, auth_headers):
        mock_instance = MagicMock()
        mock_instance.is_running.return_value = True
        state.bot_manager.get.return_value = mock_instance
        state.bot_manager.stop = AsyncMock()
        response = await app_client.post("/api/bots/test-bot/stop", headers=auth_headers)
        assert response.status_code == 200
        state.bot_manager.stop.assert_awaited_once_with("test-bot")

    async def test_restart_bot_success(self, app_client, auth_headers):
        mock_instance = MagicMock()
        state.bot_manager.get.return_value = mock_instance
        state.bot_manager.restart = AsyncMock()
        response = await app_client.post("/api/bots/test-bot/restart", headers=auth_headers)
        assert response.status_code == 200

    async def test_get_bot_config(self, app_client, auth_headers):
        mock_instance = MagicMock()
        mock_instance.config = {"bot_name": "Test", "bot_id": "test-bot"}
        state.bot_manager.get.return_value = mock_instance
        response = await app_client.get("/api/bots/test-bot/config", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["bot_name"] == "Test"

    async def test_get_bot_config_not_found(self, app_client, auth_headers):
        state.bot_manager.get.return_value = None
        response = await app_client.get("/api/bots/nonexistent/config", headers=auth_headers)
        assert response.status_code == 404

    async def test_update_bot_config(self, app_client, auth_headers):
        mock_instance = MagicMock()
        mock_instance.config = {"enabled": True, "bot_name": "Old"}
        mock_instance.save_config = MagicMock()
        mock_instance.load_config = MagicMock()
        mock_instance.status = "running"
        state.bot_manager.get.return_value = mock_instance
        state.bot_manager.restart = AsyncMock()
        response = await app_client.put(
            "/api/bots/test-bot/config",
            json={"bot_name": "Updated"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        mock_instance.save_config.assert_called_once()
        mock_instance.load_config.assert_called_once()

    async def test_get_bot_logs_no_file(self, app_client, auth_headers, tmp_path):
        mock_instance = MagicMock()
        mock_instance.config_dir = tmp_path / "test-bot-dir"
        mock_instance.config_dir.mkdir(parents=True, exist_ok=True)
        state.bot_manager.get.return_value = mock_instance
        response = await app_client.get("/api/bots/test-bot/logs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["logs"] == []

    async def test_manager_not_initialized(self, app_client, auth_headers, monkeypatch):
        monkeypatch.setattr(state, "bot_manager", None)
        response = await app_client.get("/api/bots/", headers=auth_headers)
        assert response.status_code == 503
