"""端到端测试：验证 MessageContext shim 通过完整 context pipeline 不崩溃。"""
from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.nonebug]

from nb_plugins.core_llm_bot.event_shim import event_to_message_context
from app.handlers.context_assembler import build_full_context
from app.core_logic.context_builder import format_user_message_for_llm


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
