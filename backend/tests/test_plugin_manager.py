"""Tests for plugins.manager — PluginManager."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.utils import Stub, _async_stub


@pytest.fixture
def mock_llm_caller():
    async def caller(messages, images=None):
        return "LLM response"
    return caller


class TestPluginManagerInit:
    def test_loads_memory_plugin_by_default(self, mock_llm_caller):
        from plugins.manager import PluginManager
        pm = PluginManager({"memory_plugin": {}}, mock_llm_caller)
        names = [p.name for p in pm.plugins]
        assert any("Memory" in n or "memory" in n.lower() for n in names)

    def test_skips_disabled_config_plugins(self, mock_llm_caller):
        from plugins.manager import PluginManager
        pm = PluginManager({
            "disabled_plugin": {"enabled": False, "name": "ShouldNotLoad"}
        }, mock_llm_caller)
        names = [p.name for p in pm.plugins]
        assert "ShouldNotLoad" not in names

    def test_loads_config_based_plugin(self, mock_llm_caller):
        from plugins.manager import PluginManager
        pm = PluginManager({
            "my_config_plugin": {
                "enabled": True,
                "name": "ConfigPlugin",
                "trigger_type": "command",
                "triggers": ["!test"],
                "action_type": "http_request",
            }
        }, mock_llm_caller)
        names = [p.name for p in pm.plugins]
        assert "ConfigPlugin" in names


class TestGetAllTools:
    def test_returns_list(self, mock_llm_caller):
        from plugins.manager import PluginManager
        pm = PluginManager({}, mock_llm_caller)
        tools = pm.get_all_tools()
        assert isinstance(tools, list)


class TestGetAllToolFunctions:
    def test_returns_dict(self, mock_llm_caller):
        from plugins.manager import PluginManager
        pm = PluginManager({}, mock_llm_caller)
        funcs = pm.get_all_tool_functions(Stub(author=Stub(id=123, name="X")), {})
        assert isinstance(funcs, dict)


class TestProcessMessage:
    @pytest.mark.asyncio
    async def test_no_plugins_returns_none(self, mock_llm_caller):
        from plugins.manager import PluginManager
        pm = PluginManager({}, mock_llm_caller)
        msg = Stub(content="hello", author=Stub(id=1, name="U"), channel=Stub(id=1))
        result = await pm.process_message(msg, {})
        assert result is None

    @pytest.mark.asyncio
    async def test_config_plugin_override_mode(self, mock_llm_caller):
        from plugins.manager import PluginManager
        pm = PluginManager({
            "cmd_plugin": {
                "enabled": True,
                "name": "CmdPlugin",
                "trigger_type": "command",
                "triggers": ["!ping"],
                "action_type": "http_request",
                "http_config": {"url": "http://localhost"},
            }
        }, mock_llm_caller)

        async def fake_http_request(plugin_config, message, args):
            return "pong"

        msg = Stub(
            content="!ping please",
            author=Stub(id=1, name="U"),
            channel=Stub(id=1),
            reply=AsyncMock(),
        )
        with patch("plugins.configurable_plugin._execute_http_request",
                   new=AsyncMock(side_effect=fake_http_request)):
            result = await pm.process_message(msg, {})
        assert result is True

    @pytest.mark.asyncio
    async def test_config_plugin_append_mode(self, mock_llm_caller):
        from plugins.manager import PluginManager
        pm = PluginManager({
            "append_plugin": {
                "enabled": True,
                "name": "AppendPlugin",
                "trigger_type": "command",
                "triggers": ["!append"],
                "action_type": "llm_augmented_tool",
                "injection_mode": "append",
                "http_config": {"url": "http://localhost"},
            }
        }, mock_llm_caller)

        async def fake_http_request(plugin_config, message, args):
            return "appended data"

        msg = Stub(
            content="!append test",
            author=Stub(id=1, name="U"),
            channel=Stub(id=1),
            reply=AsyncMock(),
        )
        with patch("plugins.configurable_plugin._execute_http_request",
                   new=AsyncMock(side_effect=fake_http_request)):
            result = await pm.process_message(msg, {})
        assert result is not None
        assert result[0] == "append"
