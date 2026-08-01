"""Tests for prompt studio preset routes (backend/app/routers/prompts.py).

Covers:
  - Authentication protection on all preset endpoints (no-auth → 401/403)
  - Preset CRUD: list, get, save (with _validate_templates / _validate_preset_name),
    delete (404 for missing presets, 400 for the readonly default preset)
  - bot_id validation (400 for illegal characters)
  - Preview endpoint: bot existence check (404)

All preset writes use ``bot_id=test-bot`` so presets.json lands in the
per-test tmp_path bot directory (see conftest BOTS_DIR monkeypatch).
"""

import pytest
from urllib.parse import quote

#: 与 app/routers/prompts.py 中逐字一致（默认预设为 readonly）。
DEFAULT_PRESET_NAME = "(默认)开箱即用"

#: 合法模板：4 必填键（operational_instructions 为 list[str]）。
VALID_TEMPLATES = {
    "message_format": "「{author_name}」说：\n{content}",
    "user_request_block": "<user_request>\n{parts}\n</user_request>",
    "system_prompt_foundation_header": "你是一个乐于助人的 AI 助手。",
    "operational_instructions": ["保持简洁", "不要编造事实"],
    "image_note": "",
    "reply_context": "",
    "deleted_reply_context": "",
    "tool_context": "",
    "memory_context": "",
    "worldbook_context": "",
    "system_prompt_persona_header": "",
    "system_prompt_situation_header": "",
    "system_prompt_participants_header": "",
    "system_prompt_security_header": "",
}

#: 缺必填键的非法模板（触发 _validate_templates → 400）。
INVALID_TEMPLATES_MISSING_KEYS = {"image_note": "not enough"}

#: operational_instructions 类型非法的模板（触发 _validate_templates → 400）。
INVALID_TEMPLATES_BAD_INSTRUCTIONS = {
    "message_format": "「{author_name}」说：\n{content}",
    "user_request_block": "<user_request>\n{parts}\n</user_request>",
    "system_prompt_foundation_header": "你是一个乐于助人的 AI 助手。",
    "operational_instructions": "not-a-list",
}


@pytest.mark.integration
class TestPromptPresetRoutes:
    async def test_list_presets_requires_auth(self, app_client):
        response = await app_client.get("/api/prompts/presets")
        assert response.status_code in (401, 403)

    async def test_list_presets_returns_default_first(self, app_client, auth_headers):
        response = await app_client.get("/api/prompts/presets", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == DEFAULT_PRESET_NAME
        assert data[0]["readonly"] is True

    async def test_list_presets_includes_saved_preset(self, app_client, auth_headers):
        await app_client.put(
            "/api/prompts/presets/custom-list",
            json=VALID_TEMPLATES,
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        response = await app_client.get(
            "/api/prompts/presets",
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        names = [item["name"] for item in response.json()]
        assert "custom-list" in names
        custom = next(item for item in response.json() if item["name"] == "custom-list")
        assert custom["readonly"] is False

    async def test_get_preset_requires_auth(self, app_client):
        response = await app_client.get(f"/api/prompts/presets/{quote(DEFAULT_PRESET_NAME)}")
        assert response.status_code in (401, 403)

    async def test_get_default_preset_returns_templates(self, app_client, auth_headers):
        response = await app_client.get(
            f"/api/prompts/presets/{quote(DEFAULT_PRESET_NAME)}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        templates = response.json()
        assert templates["message_format"]
        assert templates["user_request_block"]
        assert templates["system_prompt_foundation_header"]
        assert isinstance(templates["operational_instructions"], list)

    async def test_get_preset_not_found_returns_404(self, app_client, auth_headers):
        response = await app_client.get(
            "/api/prompts/presets/no-such-preset",
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_save_preset_requires_auth(self, app_client):
        response = await app_client.put("/api/prompts/presets/test-preset", json=VALID_TEMPLATES)
        assert response.status_code in (401, 403)

    async def test_save_preset_success(self, app_client, auth_headers):
        response = await app_client.put(
            "/api/prompts/presets/test-preset",
            json=VALID_TEMPLATES,
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-preset"
        assert "保存成功" in data["message"]

        # 回读确认持久化内容一致
        get_response = await app_client.get(
            "/api/prompts/presets/test-preset",
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        assert get_response.status_code == 200
        assert get_response.json()["message_format"] == VALID_TEMPLATES["message_format"]

    async def test_save_preset_missing_required_keys_returns_400(self, app_client, auth_headers):
        """结构非法（缺必填键）触发 _validate_templates → 400."""
        response = await app_client.put(
            "/api/prompts/presets/broken-preset",
            json=INVALID_TEMPLATES_MISSING_KEYS,
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "缺少必填模板键" in response.json()["detail"]

    async def test_save_preset_bad_operational_instructions_returns_400(self, app_client, auth_headers):
        """operational_instructions 非 list[str] 触发 _validate_templates → 400."""
        response = await app_client.put(
            "/api/prompts/presets/broken-preset",
            json=INVALID_TEMPLATES_BAD_INSTRUCTIONS,
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "operational_instructions" in response.json()["detail"]

    async def test_save_preset_empty_name_returns_400(self, app_client, auth_headers):
        response = await app_client.put(
            "/api/prompts/presets/%20",
            json=VALID_TEMPLATES,
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "预设名称不能为空" in response.json()["detail"]

    async def test_save_preset_default_name_returns_400(self, app_client, auth_headers):
        """默认预设 readonly，不可覆盖 → 400."""
        response = await app_client.put(
            f"/api/prompts/presets/{quote(DEFAULT_PRESET_NAME)}",
            json=VALID_TEMPLATES,
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "默认预设不可修改" in response.json()["detail"]

    async def test_save_preset_name_too_long_returns_400(self, app_client, auth_headers):
        response = await app_client.put(
            "/api/prompts/presets/" + "x" * 65,
            json=VALID_TEMPLATES,
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "不能超过 64 个字符" in response.json()["detail"]

    async def test_save_preset_invalid_bot_id_returns_400(self, app_client, auth_headers):
        """bot_id 含非法字符（防路径穿越）→ 400."""
        response = await app_client.put(
            "/api/prompts/presets/test-preset",
            json=VALID_TEMPLATES,
            params={"bot_id": "Bad ID!"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "只能包含小写字母" in response.json()["detail"]

    async def test_save_preset_overwrites_existing(self, app_client, auth_headers):
        """同名保存为 upsert 语义：重复名创建返回 200 并覆盖旧内容."""
        await app_client.put(
            "/api/prompts/presets/dup-preset",
            json=VALID_TEMPLATES,
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        updated = {**VALID_TEMPLATES, "message_format": "覆盖后的格式"}
        response = await app_client.put(
            "/api/prompts/presets/dup-preset",
            json=updated,
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        get_response = await app_client.get(
            "/api/prompts/presets/dup-preset",
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        assert get_response.json()["message_format"] == "覆盖后的格式"

    async def test_delete_preset_requires_auth(self, app_client):
        response = await app_client.delete("/api/prompts/presets/test-preset")
        assert response.status_code in (401, 403)

    async def test_delete_preset_success(self, app_client, auth_headers):
        await app_client.put(
            "/api/prompts/presets/to-delete",
            json=VALID_TEMPLATES,
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        response = await app_client.delete(
            "/api/prompts/presets/to-delete",
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        assert response.status_code == 204

        # 删除后再次获取 → 404
        get_response = await app_client.get(
            "/api/prompts/presets/to-delete",
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        assert get_response.status_code == 404

    async def test_delete_preset_not_found_returns_404(self, app_client, auth_headers):
        response = await app_client.delete(
            "/api/prompts/presets/no-such-preset",
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_delete_default_preset_returns_400(self, app_client, auth_headers):
        response = await app_client.delete(
            f"/api/prompts/presets/{quote(DEFAULT_PRESET_NAME)}",
            params={"bot_id": "test-bot"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "默认预设不可删除" in response.json()["detail"]

    async def test_preview_requires_auth(self, app_client):
        response = await app_client.post(
            "/api/prompts/preview",
            json={"templates": {}, "scenario": {}},
        )
        assert response.status_code in (401, 403)

    async def test_preview_bot_not_found_returns_404(self, app_client, auth_headers):
        """preview 提供不存在 bot_id → 404（conftest mock bot_manager.get 返回 None）."""
        response = await app_client.post(
            "/api/prompts/preview",
            json={"templates": {}, "scenario": {}},
            params={"bot_id": "nonexistent-bot"},
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert "不存在" in response.json()["detail"]
