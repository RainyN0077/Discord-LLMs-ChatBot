import pytest


@pytest.mark.integration
class TestPluginsRoutes:
    async def test_trigger_plugin_requires_auth(self, app_client):
        response = await app_client.post("/api/plugins/trigger", json={"plugin_name": "test"})
        assert response.status_code == 403

    async def test_trigger_nonexistent_plugin(self, app_client, auth_headers):
        payload = {
            "plugin_name": "nonexistent_plugin_xyz",
            "args": {},
        }
        response = await app_client.post("/api/plugins/trigger", json=payload, headers=auth_headers)
        assert response.status_code == 404

    async def test_get_plugin_config_requires_auth(self, app_client):
        response = await app_client.get("/api/plugins/test_plugin/config")
        assert response.status_code == 403

    async def test_get_plugin_config_not_found(self, app_client, auth_headers):
        response = await app_client.get("/api/plugins/nonexistent_plugin/config", headers=auth_headers)
        assert response.status_code == 404

    async def test_post_plugin_config_requires_auth(self, app_client):
        response = await app_client.post("/api/plugins/test_plugin/config", json={})
        assert response.status_code == 403

    async def test_post_plugin_config_not_found(self, app_client, auth_headers):
        response = await app_client.post("/api/plugins/nonexistent_plugin/config", json={}, headers=auth_headers)
        assert response.status_code == 404
