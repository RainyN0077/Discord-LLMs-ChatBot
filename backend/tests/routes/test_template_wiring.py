"""模板运行时接线（S4）：chat/debug/interactions 路由向 build_system_prompt /
format_user_message_for_llm 透传 templates == config['prompt_templates']（归一化后，含 None）.

与线上路径（build_full_context）同 config 同输出（A6 参数透传断言）。
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = [pytest.mark.unit]

import app.routers.chat as chat_mod
import app.routers.debug as debug_mod
import app.routers.interactions as inter_mod
import app.core_logic.persona_manager as pm_mod
import app.core_logic.context_builder as cb_mod


def _base_config() -> dict:
    return {
        "system_prompt": "You are a test assistant.",
        "user_personas": {},
        "role_based_config": {},
        "scoped_prompts": {"guilds": {}, "channels": {}},
        "llm_provider": "openai",
        "model_name": "gpt-4o",
    }


def _variants():
    """(config 的 prompt_templates 值, 期望透传值)."""
    return [
        (None, None),                                  # 无键
        ({"message_format": "«{content}»"}, {"message_format": "«{content}»"}),  # 合法 dict
        ("invalid-type", None),                        # 非 dict → 归一化 None
    ]


async def _run_direct_chat(monkeypatch, config) -> tuple:
    build_spy = AsyncMock(return_value="spy-system")
    format_spy = AsyncMock(return_value="spy-user")
    monkeypatch.setattr(chat_mod, "build_system_prompt", build_spy)
    monkeypatch.setattr(chat_mod, "format_user_message_for_llm", format_spy)
    monkeypatch.setattr(chat_mod, "load_config", lambda: config)

    class _Pool:
        async def collect_full_response(self, *a, **k):
            return ("response-ok", {"prompt_tokens": 1, "completion_tokens": 1})

    monkeypatch.setattr(chat_mod, "get_provider_pool", lambda: _Pool())

    from app.models import DirectChatRequest, DirectChatMessage, DirectChatDebugContext

    request = DirectChatRequest(
        messages=[DirectChatMessage(role="user", content="Hello")],
        debug_mode=True,
        debug_context=DirectChatDebugContext(user_id="123", channel_id="456", guild_id="789"),
        bot_id=None,
    )
    await chat_mod.direct_chat(request)
    return build_spy, format_spy


async def _run_debug_simulate(monkeypatch, config) -> tuple:
    build_spy = AsyncMock(return_value="spy-system")
    format_spy = AsyncMock(return_value="spy-user")
    monkeypatch.setattr(debug_mod, "build_system_prompt", build_spy)
    monkeypatch.setattr(debug_mod, "format_user_message_for_llm", format_spy)
    monkeypatch.setattr(debug_mod, "load_config", lambda: config)

    class _Pool:
        async def execute(self, *a, **k):
            async def _gen():
                yield ("final", "llm-ok")

            return _gen()

    monkeypatch.setattr(debug_mod, "get_provider_pool", lambda: _Pool())

    from app.models import DebuggerRequest

    request = DebuggerRequest(
        user_id="123", channel_id="456", guild_id="789",
        message_content="hi", bot_id=None,
    )
    await debug_mod.simulate_debugger_run(request)
    return build_spy, format_spy


async def _run_reconstruct_context(monkeypatch, bot_config) -> tuple:
    # interactions.py 在函数体内局部 import，须 monkeypatch 源模块
    build_spy = AsyncMock(return_value="spy-system")
    format_spy = AsyncMock(return_value="spy-user")
    monkeypatch.setattr(pm_mod, "build_system_prompt", build_spy)
    monkeypatch.setattr(cb_mod, "format_user_message_for_llm", format_spy)
    import app.config_cache as cc_mod
    monkeypatch.setattr(cc_mod, "load_config", lambda: {"bots": {"b1": bot_config}})

    class _Recorder:
        async def read_messages(self, *a, **k):
            return [{
                "timestamp": "2025-01-01T12:00:00",
                "author_id": "444",
                "author_name": "TestUser",
                "content": "Hello bot!",
                "attachments": [],
            }]

    monkeypatch.setattr(inter_mod, "get_interaction_recorder", lambda: _Recorder())

    await inter_mod.reconstruct_context(
        bot_id="b1", guild_id="111", role_id="222",
        channel_id="333", member_id="444", date="2025-01-01",
    )
    return build_spy, format_spy


class TestChatTemplateWiring:
    @pytest.mark.parametrize("templates_value, expected", _variants())
    async def test_direct_chat_passes_templates(self, monkeypatch, templates_value, expected):
        config = _base_config()
        if templates_value is not None:
            config["prompt_templates"] = templates_value
        build_spy, format_spy = await _run_direct_chat(monkeypatch, config)
        assert build_spy.await_args.kwargs["templates"] == expected
        assert format_spy.await_args.kwargs["templates"] == expected


class TestDebugTemplateWiring:
    @pytest.mark.parametrize("templates_value, expected", _variants())
    async def test_debug_simulate_passes_templates(self, monkeypatch, templates_value, expected):
        config = _base_config()
        if templates_value is not None:
            config["prompt_templates"] = templates_value
        build_spy, format_spy = await _run_debug_simulate(monkeypatch, config)
        assert build_spy.await_args.kwargs["templates"] == expected
        assert format_spy.await_args.kwargs["templates"] == expected


class TestInteractionsTemplateWiring:
    @pytest.mark.parametrize("templates_value, expected", _variants())
    async def test_reconstruct_context_passes_templates(self, monkeypatch, templates_value, expected):
        bot_config = _base_config()
        if templates_value is not None:
            bot_config["prompt_templates"] = templates_value
        build_spy, format_spy = await _run_reconstruct_context(monkeypatch, bot_config)
        assert build_spy.await_args.kwargs["templates"] == expected
        assert format_spy.await_args.kwargs["templates"] == expected
