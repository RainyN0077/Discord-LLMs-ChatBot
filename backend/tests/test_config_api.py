"""API tests for /api/config quota_alert passthrough semantics.

Covers:
  - quota_alert provided → persisted on PUT/POST update
  - quota_alert omitted (None) → existing value preserved (no overwrite)
"""
import pytest

from app import state
from app.config_cache import invalidate_cache, load_config


@pytest.mark.integration
class TestConfigQuotaAlertApi:
    async def test_put_config_saves_quota_alert(self, app_client, auth_headers, test_config_dict):
        """POST /api/config with quota_alert is persisted to the global config."""
        quota_alert = {
            "enabled": True,
            "webhook_url": "https://hooks.example.com/per-bot",
            "token_limit": 5000,
            "request_limit": 200,
            "warning_threshold": 0.6,
            "critical_threshold": 0.95,
        }
        body = {**test_config_dict, "bot_id": "other-bot", "quota_alert": quota_alert}
        response = await app_client.post("/api/config", json=body, headers=auth_headers)
        assert response.status_code == 200, response.text

        invalidate_cache()
        assert load_config()["quota_alert"] == quota_alert

    async def test_put_config_without_quota_alert_keeps_existing(
        self, app_client, auth_headers, test_config_dict
    ):
        """quota_alert omitted from the request body must not wipe the stored value."""
        existing_quota = {
            "enabled": True,
            "token_limit": 5000,
            "webhook_url": "https://hooks.example.com/existing",
        }
        mock_instance = state.bot_manager._instances["test-bot"]
        mock_instance.config = {**test_config_dict, "enabled": False, "quota_alert": existing_quota}

        body = {**test_config_dict, "bot_id": "test-bot"}
        response = await app_client.post("/api/config", json=body, headers=auth_headers)
        assert response.status_code == 200, response.text

        saved = mock_instance.save_config.call_args[0][0]
        assert saved["quota_alert"] == existing_quota
