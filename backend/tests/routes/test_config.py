import pytest


@pytest.mark.integration
class TestConfigRoutes:
    async def test_get_config_returns_data(self, app_client, auth_headers):
        response = await app_client.get("/api/config", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "api_secret_key" in data
        assert "system_prompt" in data

    async def test_get_config_no_auth_returns_403(self, app_client):
        response = await app_client.get("/api/config")
        assert response.status_code == 403

    async def test_get_config_wrong_api_key_returns_403(self, app_client, bad_auth_headers):
        response = await app_client.get("/api/config", headers=bad_auth_headers)
        assert response.status_code == 403

    async def test_post_config_requires_auth(self, app_client):
        response = await app_client.post("/api/config", json={})
        assert response.status_code in (401, 403)

    async def test_post_config_with_auth_invalid_body(self, app_client, auth_headers):
        response = await app_client.post("/api/config", json={"invalid": "body"}, headers=auth_headers)
        assert response.status_code == 422

    async def test_post_config_with_wrong_api_key(self, app_client, bad_auth_headers):
        response = await app_client.post("/api/config", json={}, headers=bad_auth_headers)
        assert response.status_code == 403

    async def test_bootstrap_sets_key_when_empty(self, app_client, tmp_path, test_config_dict, monkeypatch):
        """Bootstrap should succeed when api_secret_key is empty and request is from localhost."""
        import json
        import app.config_cache as cc
        import app.routers.config as config_mod
        from app.security.secrets_manager import SecretsManager

        # Overwrite the config file on disk with an empty api_secret_key.
        config_file = cc.CONFIG_FILE
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_without_key = {**test_config_dict, "api_secret_key": ""}
        encrypted = SecretsManager().encrypt_dict(config_without_key)
        config_file.write_text(json.dumps(encrypted, indent=2), encoding="utf-8")
        cc.invalidate_cache()

        # Also update the CONFIG_FILE reference in config.py since it's imported by value.
        monkeypatch.setattr(config_mod, "CONFIG_FILE", config_file)

        response = await app_client.post("/api/auth/bootstrap", json={"api_secret_key": "new-bootstrap-key"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["api_secret_key"] == "new-bootstrap-key"

    async def test_bootstrap_403_when_key_already_set(self, app_client, auth_headers):
        """Bootstrap should fail with 403 when api_secret_key is already configured."""
        response = await app_client.post("/api/auth/bootstrap", json={"api_secret_key": "another-key"}, headers=auth_headers)
        assert response.status_code == 403

    async def test_auth_status_returns_key_on_localhost(self, app_client):
        """Auth status on localhost returns api_secret_key for auto-auth (傻瓜式启动)."""
        response = await app_client.get("/api/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False
        assert data["api_secret_key"]  # localhost 返回密钥

    async def test_auth_status_hides_key_for_remote(self):
        """Auth status from non-localhost must not leak api_secret_key."""
        from httpx import ASGITransport, AsyncClient
        from app.main import app

        transport = ASGITransport(app=app, client=("192.168.1.100", 54321))
        async with AsyncClient(transport=transport, base_url="http://test") as remote_client:
            response = await remote_client.get("/api/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False
        assert data["api_secret_key"] == ""

    async def test_bootstrap_requires_localhost(self, app_client, tmp_path, test_config_dict, monkeypatch):
        """Bootstrap from non-localhost client should be rejected."""
        import json
        import app.config_cache as cc
        import app.routers.config as config_mod
        from app.security.secrets_manager import SecretsManager

        # Overwrite the config file on disk with an empty api_secret_key.
        config_file = cc.CONFIG_FILE
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_without_key = {**test_config_dict, "api_secret_key": ""}
        encrypted = SecretsManager().encrypt_dict(config_without_key)
        config_file.write_text(json.dumps(encrypted, indent=2), encoding="utf-8")
        cc.invalidate_cache()

        monkeypatch.setattr(config_mod, "CONFIG_FILE", config_file)

        # Simulate non-localhost by passing a request with client host set to a remote IP
        from httpx import ASGITransport, AsyncClient
        from app.main import app
        transport = ASGITransport(app=app, client=("192.168.1.100", 54321))
        async with AsyncClient(transport=transport, base_url="http://test") as remote_client:
            response = await remote_client.post("/api/auth/bootstrap", json={"api_secret_key": "new-key"})
        assert response.status_code == 403
