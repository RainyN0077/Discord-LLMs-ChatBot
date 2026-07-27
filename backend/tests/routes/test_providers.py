"""Provider 管理 API 路由测试 (Wave 4, 1.3.6).

测试场景:
- GET /providers 无认证 → 401/403 (P1-3 修复)
- GET /providers 有认证 → 200 + 正确响应结构
- GET /providers 不存在的 bot_id → 404
- POST /switch 无认证 → 401/403
- POST /switch 无效 provider name → 400/422
- POST /switch API key 验证失败 → 400（不修改配置）
- POST /switch 不存在的 bot_id → 404
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app import state


@pytest.fixture
def _reset_rate_limit():
    """Cleanup _last_switch_time between tests to avoid rate limit collisions."""
    from app.routers.providers import _last_switch_time
    _last_switch_time.clear()


@pytest.mark.integration
class TestProviderList:
    """GET /api/bots/{bot_id}/providers 测试."""

    async def test_list_providers_requires_auth(self, app_client):
        """无认证 → 401/403."""
        response = await app_client.get("/api/bots/test-bot/providers/")
        assert response.status_code in (401, 403)

    async def test_list_providers_success(self, app_client, auth_headers):
        """有认证 → 200 + 正确响应结构."""
        mock_instance = MagicMock()
        mock_instance.config = {
            "llm_provider": "openai",
            "model_name": "gpt-4o",
            "api_key": "sk-test-key-12345678",
        }
        state.bot_manager.get.return_value = mock_instance

        # Mock ProviderPool.check_provider_health to avoid actual LLM calls
        with patch("app.routers.providers.get_provider_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_pool.check_provider_health = AsyncMock(
                return_value={
                    "healthy": True,
                    "latency_ms": 150.0,
                    "model": "gpt-4o",
                    "error": None,
                }
            )
            mock_get_pool.return_value = mock_pool

            response = await app_client.get(
                "/api/bots/test-bot/providers/",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert "current_provider" in data
        assert "current_model" in data
        assert "providers" in data
        assert data["current_provider"] == "openai"
        assert data["current_model"] == "gpt-4o"
        # Should contain at least our known providers
        assert len(data["providers"]) > 0
        # Find the current provider in the list
        current = [p for p in data["providers"] if p["is_current"]]
        assert len(current) == 1
        assert current[0]["name"] == "openai"

    async def test_list_providers_bot_not_found(self, app_client, auth_headers):
        """不存在的 bot_id → 404."""
        state.bot_manager.get.return_value = None
        response = await app_client.get(
            "/api/bots/nonexistent/providers/",
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_list_providers_manager_not_initialized(
        self, app_client, auth_headers, monkeypatch
    ):
        """Bot manager 未初始化 → 503."""
        monkeypatch.setattr(state, "bot_manager", None)
        response = await app_client.get(
            "/api/bots/test-bot/providers/",
            headers=auth_headers,
        )
        assert response.status_code == 503

    async def test_list_providers_health_check_timeout(
        self, app_client, auth_headers
    ):
        """健康检查超时 → healthy=False, 不抛异常."""
        mock_instance = MagicMock()
        mock_instance.config = {
            "llm_provider": "openai",
            "model_name": "gpt-4o",
            "api_key": "sk-test-key-12345678",
        }
        state.bot_manager.get.return_value = mock_instance

        with patch("app.routers.providers.get_provider_pool") as mock_get_pool:
            mock_pool = MagicMock()
            # Simulate timeout
            mock_pool.check_provider_health = AsyncMock(
                side_effect=TimeoutError("Simulated timeout")
            )
            mock_get_pool.return_value = mock_pool

            response = await app_client.get(
                "/api/bots/test-bot/providers/",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        # Providers list should still be returned, with healthy=False for any that timed out
        assert len(data["providers"]) > 0

    async def test_list_providers_no_api_key(
        self, app_client, auth_headers
    ):
        """无 API key → configured=False, healthy=None."""
        mock_instance = MagicMock()
        mock_instance.config = {
            "llm_provider": "openai",
            "model_name": "gpt-4o",
            "api_key": "",  # Empty API key
        }
        state.bot_manager.get.return_value = mock_instance

        response = await app_client.get(
            "/api/bots/test-bot/providers/",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # All providers should have configured=False since api_key is empty
        for p in data["providers"]:
            assert p["configured"] is False
            assert p["healthy"] is None
            assert p["latency_ms"] is None


@pytest.mark.integration
class TestProviderSwitch:
    """POST /api/bots/{bot_id}/providers/switch 测试."""

    @pytest.fixture(autouse=True)
    def _cleanup_rate_limit(self, _reset_rate_limit):
        """Reset rate limiter before each switch test."""
        pass

    async def test_switch_requires_auth(self, app_client):
        """无认证 → 401/403."""
        response = await app_client.post(
            "/api/bots/test-bot/providers/switch",
            json={"provider": "anthropic", "model": "claude-sonnet-4-20250514",
                  "api_key": "sk-ant-test-key-12345678"},
        )
        assert response.status_code in (401, 403)

    async def test_switch_invalid_provider_name(self, app_client, auth_headers):
        """无效 provider name → 422 (Pydantic 约束)."""
        # Invalid: contains uppercase
        response = await app_client.post(
            "/api/bots/test-bot/providers/switch",
            json={"provider": "INVALID", "model": "test-model",
                  "api_key": "sk-test-key-12345678"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_switch_api_key_too_short(self, app_client, auth_headers):
        """API key 太短 → 422 (Pydantic 约束)."""
        response = await app_client.post(
            "/api/bots/test-bot/providers/switch",
            json={"provider": "openai", "model": "gpt-4o",
                  "api_key": "short"},  # min_length=8
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_switch_bot_not_found(self, app_client, auth_headers):
        """不存在的 bot_id → 404."""
        state.bot_manager.get.return_value = None
        response = await app_client.post(
            "/api/bots/nonexistent/providers/switch",
            json={"provider": "anthropic", "model": "claude-sonnet-4-20250514",
                  "api_key": "sk-ant-test-key-12345678"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_switch_unsupported_provider(self, app_client, auth_headers):
        """不支持的 provider → 422."""
        mock_instance = MagicMock()
        mock_instance.config = {
            "llm_provider": "openai",
            "model_name": "gpt-4o",
            "api_key": "sk-test-key-12345678",
        }
        state.bot_manager.get.return_value = mock_instance

        response = await app_client.post(
            "/api/bots/test-bot/providers/switch",
            json={"provider": "unknown_provider", "model": "test-model",
                  "api_key": "sk-test-key-12345678"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_switch_connectivity_failure(self, app_client, auth_headers):
        """连通性测试失败 → 422, 不修改配置."""
        mock_instance = MagicMock()
        mock_instance.config = {
            "llm_provider": "openai",
            "model_name": "gpt-4o",
            "api_key": "sk-test-key-12345678",
        }
        mock_instance.save_config = MagicMock()
        mock_instance.is_running = MagicMock(return_value=False)
        state.bot_manager.get.return_value = mock_instance

        with patch("app.routers.providers.get_provider_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_pool.check_provider_health = AsyncMock(
                return_value={"healthy": False, "error": "Invalid API key"}
            )
            mock_get_pool.return_value = mock_pool

            response = await app_client.post(
                "/api/bots/test-bot/providers/switch",
                json={"provider": "anthropic", "model": "claude-sonnet-4-20250514",
                      "api_key": "sk-ant-invalid-key"},
                headers=auth_headers,
            )

        assert response.status_code == 422
        # save_config should NOT have been called (config not modified)
        mock_instance.save_config.assert_not_called()

    async def test_switch_success(self, app_client, auth_headers):
        """切换成功 → 200 + 正确响应."""
        mock_instance = MagicMock()
        mock_instance.config = {
            "llm_provider": "openai",
            "model_name": "gpt-4o",
            "api_key": "sk-test-key-12345678",
        }
        mock_instance.save_config = MagicMock()
        mock_instance.is_running = MagicMock(return_value=True)
        mock_instance.status = "running"
        state.bot_manager.get.return_value = mock_instance

        with patch("app.routers.providers.get_provider_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_pool.check_provider_health = AsyncMock(
                return_value={
                    "healthy": True,
                    "latency_ms": 200.0,
                    "model": "claude-sonnet-4-20250514",
                    "error": None,
                }
            )
            mock_get_pool.return_value = mock_pool

            response = await app_client.post(
                "/api/bots/test-bot/providers/switch",
                json={
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514",
                    "api_key": "sk-ant-test-key-12345678",
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["previous_provider"] == "openai"
        assert data["current_provider"] == "anthropic"
        assert data["current_model"] == "claude-sonnet-4-20250514"
        assert data["status"] == "running"
        assert "switched" in data["message"].lower()
        # save_config should have been called (first for new config, potentially more)
        assert mock_instance.save_config.called

    async def test_switch_restart_failure_rollback(self, app_client, auth_headers):
        """重启失败 → 回滚旧配置 (P0-2 修复)."""
        mock_instance = MagicMock()
        mock_instance.config = {
            "llm_provider": "openai",
            "model_name": "gpt-4o",
            "api_key": "sk-test-key-12345678",
        }
        mock_instance.save_config = MagicMock()
        mock_instance.is_running = MagicMock(return_value=False)
        state.bot_manager.get.return_value = mock_instance

        with patch("app.routers.providers.get_provider_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_pool.check_provider_health = AsyncMock(
                return_value={"healthy": True, "latency_ms": 100.0,
                              "model": "gpt-4o", "error": None}
            )
            mock_get_pool.return_value = mock_pool

            # Make mgr.restart raise an exception
            state.bot_manager.restart = AsyncMock(
                side_effect=Exception("Restart failed")
            )

            response = await app_client.post(
                "/api/bots/test-bot/providers/switch",
                json={
                    "provider": "google",
                    "model": "gemini-2.0-flash",
                    "api_key": "ai-test-key-12345678",
                },
                headers=auth_headers,
            )

        assert response.status_code == 500
        # save_config should have been called at least twice:
        # 1. For new config
        # 2. For rollback to old config
        assert mock_instance.save_config.call_count >= 2
        # Verify rollback config is the original one
        rollback_call_args = mock_instance.save_config.call_args_list[-1][0][0]
        assert rollback_call_args["llm_provider"] == "openai"

    async def test_switch_rate_limit(self, app_client, auth_headers):
        """速率限制 → 429."""
        mock_instance = MagicMock()
        mock_instance.config = {
            "llm_provider": "openai",
            "model_name": "gpt-4o",
            "api_key": "sk-test-key-12345678",
        }
        mock_instance.save_config = MagicMock()
        mock_instance.is_running = MagicMock(return_value=True)
        mock_instance.status = "running"
        state.bot_manager.get.return_value = mock_instance

        with patch("app.routers.providers.get_provider_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_pool.check_provider_health = AsyncMock(
                return_value={"healthy": True, "latency_ms": 100.0,
                              "model": "gpt-4o", "error": None}
            )
            mock_get_pool.return_value = mock_pool

            # First switch should succeed
            resp1 = await app_client.post(
                "/api/bots/test-bot/providers/switch",
                json={
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-20250514",
                    "api_key": "sk-ant-test-key-12345678",
                },
                headers=auth_headers,
            )
            assert resp1.status_code == 200

            # Immediate second switch should hit rate limit
            resp2 = await app_client.post(
                "/api/bots/test-bot/providers/switch",
                json={
                    "provider": "google",
                    "model": "gemini-2.0-flash",
                    "api_key": "ai-test-key-12345678",
                },
                headers=auth_headers,
            )
            assert resp2.status_code == 429
            assert "rate limit" in resp2.json()["detail"].lower()

    async def test_switch_with_base_url(self, app_client, auth_headers):
        """带 base_url 的切换 → 200 + 正确配置写入."""
        mock_instance = MagicMock()
        mock_instance.config = {
            "llm_provider": "openai",
            "model_name": "gpt-4o",
            "api_key": "sk-test-key-12345678",
        }
        mock_instance.save_config = MagicMock()
        mock_instance.is_running = MagicMock(return_value=True)
        mock_instance.status = "running"
        state.bot_manager.get.return_value = mock_instance

        with patch("app.routers.providers.get_provider_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_pool.check_provider_health = AsyncMock(
                return_value={"healthy": True, "latency_ms": 300.0,
                              "model": "deepseek-chat", "error": None}
            )
            mock_get_pool.return_value = mock_pool

            response = await app_client.post(
                "/api/bots/test-bot/providers/switch",
                json={
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "api_key": "sk-ds-test-key-12345678",
                    "base_url": "https://api.deepseek.com/v1",
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        # Verify config was saved with the base_url
        save_call_args = mock_instance.save_config.call_args_list[-1][0][0]
        assert save_call_args["llm_provider"] == "deepseek"
        assert save_call_args["base_url"] == "https://api.deepseek.com/v1"
