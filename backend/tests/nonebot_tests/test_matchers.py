from unittest.mock import AsyncMock, MagicMock
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.nonebug]

from nb_plugins.core_llm_bot.matchers import (
    register_bot_instance,
    unregister_bot_instance,
    _resolve_bot_id,
)


class TestBotRegistration:
    def test_register_and_resolve(self):
        instance = MagicMock()
        instance.config = {"bot_name": "TestBot"}
        register_bot_instance("test-bot", instance)
        from nb_plugins.core_llm_bot.matchers import _bot_instance_map
        assert "test-bot" in _bot_instance_map
        unregister_bot_instance("test-bot")
        assert "test-bot" not in _bot_instance_map

    def test_resolve_bot_id_falls_back_to_first(self):
        bot = MagicMock()
        bot.self_id = "999999"
        instance = MagicMock()
        register_bot_instance("test-bot", instance)
        result = _resolve_bot_id(bot)
        assert result == "test-bot"
        unregister_bot_instance("test-bot")
