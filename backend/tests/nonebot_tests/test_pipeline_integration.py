"""端到端测试：验证 MessageContext shim 通过完整 context pipeline 不崩溃。"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.nonebug]

from nb_plugins.core_llm_bot.matchers import _event_to_message_context as event_to_message_context
from nb_plugins.core_llm_bot.context import build_full_context
from nb_plugins.core_llm_bot.pipeline import _apply_memory_injection
from app.core_logic.context_builder import format_user_message_for_llm
from app.core_logic import persona_manager as pm_module


def _make_event(content="Hello", author_id=123, author_name="Tester",
                global_name="Tester", channel_id=456, guild_id=789,
                mentions=None, attachments=None, reply=None):
    e = MagicMock()
    e.id = 1001
    e.content = content
    e.channel_id = channel_id
    e.guild_id = guild_id
    a = MagicMock()
    a.id = author_id
    a.username = author_name
    a.global_name = global_name
    a.bot = False
    e.author = a
    e.mentions = mentions or []
    e.attachments = attachments or []
    e.reply = reply
    return e


def _make_bot(self_id="999999999"):
    b = MagicMock()
    b.self_id = self_id
    b.self_info = MagicMock()
    b.self_info.id = int(self_id)
    return b


@pytest.mark.asyncio
async def test_build_full_context_with_message_context():
    """验证 MessageContext 流经 build_full_context 不抛出异常。"""
    event = _make_event(content="你好，测试消息")
    bot = _make_bot()
    message_ctx = event_to_message_context(event, bot)

    config = {
        "system_prompt": "你是测试助手。",
        "context_mode": "none",
        "trigger_keywords": [],
        "user_personas": {},
        "role_based_config": {},
        "scoped_prompts": {"channels": {}, "guilds": {}},
    }

    result = await build_full_context(
        bot=bot,
        config=config,
        message=message_ctx,
        memory_cutoffs={},
        injected_data=None,
    )

    system_prompt, final_content, history_llm, history_msgs, role_name, role_config = result

    assert isinstance(system_prompt, str)
    assert "你是测试助手" in system_prompt
    assert isinstance(final_content, str)
    assert isinstance(history_llm, list)
    assert isinstance(history_msgs, list)
    assert len(history_llm) == 0
    assert len(history_msgs) == 0


@pytest.mark.asyncio
async def test_build_full_context_with_mention_and_persona():
    """验证带 mention 和 persona 配置的 MessageContext 不崩溃。"""
    m = MagicMock()
    m.id = 777
    m.username = "MentionedUser"
    event = _make_event(content="<@999999999> hello", mentions=[m])
    bot = _make_bot()
    message_ctx = event_to_message_context(event, bot)

    config = {
        "system_prompt": "你是助手。",
        "context_mode": "none",
        "trigger_keywords": [],
        "user_personas": {
            "p1": {
                "id": "777",
                "name": "MentionedUser",
                "prompt": "This user is an admin.",
                "nickname": "Admin",
            }
        },
        "role_based_config": {},
        "scoped_prompts": {"channels": {}, "guilds": {}},
    }

    result = await build_full_context(
        bot=bot,
        config=config,
        message=message_ctx,
        memory_cutoffs={},
        injected_data=None,
    )

    system_prompt, final_content, history_llm, history_msgs, role_name, role_config = result
    assert isinstance(system_prompt, str)
    assert isinstance(final_content, str)


@pytest.mark.asyncio
async def test_format_user_message_for_llm_with_message_context():
    """验证 format_user_message_for_llm 对 MessageContext 正常输出。"""
    event = _make_event(content="<@999999999> 你好世界", author_name="Alice")
    bot = _make_bot()
    message_ctx = event_to_message_context(event, bot)

    config = {
        "system_prompt": "你是助手。",
        "user_personas": {},
        "role_based_config": {},
        "scoped_prompts": {},
    }

    result = await format_user_message_for_llm(
        message=message_ctx,
        client=bot,
        bot_config=config,
        role_config=None,
    )

    assert "你好世界" in result
    assert "<@999999999>" not in result
    assert "[用户请求块]" in result


@pytest.mark.asyncio
async def test_pipeline_with_reply_context():
    """验证带回复上下文的 MessageContext 正常处理。"""
    reply = MagicMock()
    reply.id = 2001
    reply.content = "原始消息"
    ra = MagicMock()
    ra.id = 456
    ra.username = "ReplyUser"
    ra.global_name = "ReplyUser"
    reply.author = ra

    event = _make_event(content="回复内容", reply=reply)
    bot = _make_bot()
    message_ctx = event_to_message_context(event, bot)

    config = {
        "system_prompt": "你是助手。",
        "context_mode": "none",
        "trigger_keywords": [],
        "user_personas": {},
        "role_based_config": {},
        "scoped_prompts": {"channels": {}, "guilds": {}},
    }

    result = await build_full_context(
        bot=bot,
        config=config,
        message=message_ctx,
        memory_cutoffs={},
        injected_data=None,
    )

    system_prompt, final_content, history_llm, history_msgs, role_name, role_config = result
    assert isinstance(final_content, str)
    assert isinstance(system_prompt, str)


def _base_config() -> dict:
    return {
        "system_prompt": "You are a test assistant.",
        "context_mode": "none",
        "trigger_keywords": [],
        "user_personas": {},
        "role_based_config": {},
        "scoped_prompts": {"channels": {}, "guilds": {}},
    }


# A1 回归快照：无 prompt_templates 键的 config 走完整 pipeline 的 final_content 基线（改动前捕获）。
A1_FINAL_CONTENT_SNAPSHOT = (
    "[用户请求块]\n\n"
    "[当前用户信息]\n"
    "[Tester Tester id：123]\n"
    "[/当前用户信息]\n\n"
    "[Tester Tester id：123]: Hello 123\n\n"
    "[/用户请求块]"
)


def _freeze_clock(monkeypatch):
    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2024, 1, 1, 12, 0, 0, tzinfo=tz or timezone.utc)

    monkeypatch.setattr(pm_module, "datetime", _FixedDatetime)


@pytest.mark.asyncio
async def test_no_templates_config_output_byte_identical_snapshot():
    """A1：无 prompt_templates 键的 config 走完整 pipeline，final_content 与基线逐字节一致（快照断言）. """
    event = _make_event(content="Hello 123")
    bot = _make_bot()
    message_ctx = event_to_message_context(event, bot)
    config = _base_config()

    _, final_content, history_llm, history_msgs, _, _ = await build_full_context(
        bot=bot, config=config, message=message_ctx, memory_cutoffs={}, injected_data=None,
    )

    assert final_content == A1_FINAL_CONTENT_SNAPSHOT
    assert isinstance(history_llm, list)
    assert isinstance(history_msgs, list)


@pytest.mark.asyncio
@pytest.mark.parametrize("templates_value", [
    None,
    "not-a-dict",
    42,
    {"message_format": ""},
    {"unknown_key": "x"},
    {"memory_context": ""},
])
async def test_no_templates_config_byte_identical_across_variants(monkeypatch, templates_value):
    """A1：无键 / 显式 None / 非法类型 / 空值 / 未知键 → 与无键基线逐字节一致（回退语义）. """
    _freeze_clock(monkeypatch)
    event = _make_event(content="Hello 123")
    bot = _make_bot()
    message_ctx = event_to_message_context(event, bot)
    baseline = await build_full_context(
        bot=bot, config=_base_config(), message=message_ctx, memory_cutoffs={}, injected_data=None,
    )
    variant = await build_full_context(
        bot=bot,
        config={**_base_config(), "prompt_templates": templates_value},
        message=message_ctx, memory_cutoffs={}, injected_data=None,
    )
    assert variant[0] == baseline[0]  # system_prompt 逐字节一致
    assert variant[1] == baseline[1]  # final_content 逐字节一致


@pytest.mark.asyncio
async def test_prompt_templates_effective_through_build_full_context():
    """S3 接线点：prompt_templates 经 build_full_context 全链路生效（persona + user request）. """
    event = _make_event(content="Hello 123")
    bot = _make_bot()
    message_ctx = event_to_message_context(event, bot)
    config = {
        **_base_config(),
        "prompt_templates": {
            "message_format": "«{author_id_str}»「{content}」",
            "user_request_block": "<user_request>\n{parts}\n</user_request>",
            "system_prompt_foundation_header": "定制基础规则",
        },
    }
    system_prompt, final_content, _, _, _, _ = await build_full_context(
        bot=bot, config=config, message=message_ctx, memory_cutoffs={}, injected_data=None,
    )
    assert final_content.startswith("<user_request>")
    assert "«Tester Tester id：123»" in final_content
    assert "[定制基础规则]" in system_prompt


OLD_MEMORY_PREFIX = (
    "<knowledge>\n<long_term_memory>\n{memory_knowledge}\n"
    "</long_term_memory>\n</knowledge>\n\n"
)


class TestMemoryContextInjection:
    """S5/A5：memory_context 有键且占位符匹配 → 新前缀；否则旧拼接逐字节不变. """

    def test_memory_injection_uses_template_when_configured(self):
        config = {"prompt_templates": {"memory_context": "[长期记忆]\n{data}"}}
        result = _apply_memory_injection("SYS", "KNOW", config)
        assert result == "[长期记忆]\nKNOW\n\nSYS"

    def test_memory_injection_uses_full_template_with_system_prompt(self):
        config = {"prompt_templates": {"memory_context": "记忆：\n{data}\n结束"}}
        result = _apply_memory_injection("SYSTEM_PROMPT", "MEM1\nMEM2", config)
        assert result == "记忆：\nMEM1\nMEM2\n结束\n\nSYSTEM_PROMPT"

    @pytest.mark.parametrize("config", [
        {},                                             # 无键
        {"prompt_templates": None},                     # 显式 None
        {"prompt_templates": "invalid"},                # 非 dict
        {"prompt_templates": {"memory_context": ""}},   # 空串
        {"prompt_templates": {"memory_context": None}},  # 键值 None
        {"prompt_templates": {"memory_context": 123}},  # 键值非 str
        {"prompt_templates": {"memory_context": "无占位符的静态文本"}},  # 无占位符
        {"prompt_templates": {"memory_context": "{wrong_placeholder}"}},  # 占位符不匹配
    ])
    def test_memory_injection_fallback_byte_identical(self, config):
        result = _apply_memory_injection("SYS", "KNOW", config)
        assert result == OLD_MEMORY_PREFIX.format(memory_knowledge="KNOW") + "SYS"
