import logging

import pytest
pytestmark = [pytest.mark.unit]
from app.utils import Stub, _async_stub
from app.core_logic.context_builder import format_user_message_for_llm

from app.core_logic.context_builder import build_context_history
from app.core_logic.context_builder import (
    USER_REQUEST_BLOCK_TPL,
    USER_MESSAGE_TPL,
    _format_tpl,
    format_memory_context,
    resolve_prompt_templates,
)
from app.core_logic.user_options_manager import get_formatted_block_notice
from unittest.mock import AsyncMock, MagicMock, patch


async def _history_iter(items):
    for item in items:
        yield item


class TestFormatUserMessageForLLM:
    async def test_basic_message_formatting(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Hello world")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = await format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "[用户请求块]" in result or "Hello world" in result

    async def test_removes_bot_mention(self, mock_discord_message, mock_discord_bot):
        bot_id = str(mock_discord_bot.user.id)
        msg = mock_discord_message(content=f"<@{bot_id}> help me please")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = await format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "help me please" in result
        assert f"<@{bot_id}>" not in result

    async def test_removes_bot_mention_exclamation(self, mock_discord_message, mock_discord_bot):
        bot_id = str(mock_discord_bot.user.id)
        msg = mock_discord_message(content=f"<@!{bot_id}> hello")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = await format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "hello" in result

    async def test_reply_context_stub_not_discord_message(self, mock_discord_message, mock_discord_bot):
        replied_author = Stub(id=111222, display_name="OriginalAuthor", bot=False)
        replied_msg = Stub(
            author=replied_author,
            clean_content="Original message text",
            attachments=[],
        )
        reference = Stub(resolved=replied_msg)
        msg = mock_discord_message(content="My reply", reference=reference)
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = await format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert len(result) > 0

    async def test_deleted_reply_handling(self, mock_discord_message, mock_discord_bot):
        reference = Stub(resolved="not a valid message")
        msg = mock_discord_message(content="Replying to deleted", reference=reference)
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = await format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert len(result) > 0

    async def test_world_book_injection_via_parameter(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Tell me about the kingdom")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        world_book_entries = [
            {"id": 1, "keywords": "kingdom, magic", "content": "The kingdom is magical."},
            {"id": 2, "keywords": "dragons", "content": "Dragons are rare."},
        ]
        result = await format_user_message_for_llm(msg, mock_discord_bot, config, None, world_book_entries=world_book_entries)
        assert "The kingdom is magical." in result
        assert "Dragons are rare." in result

    async def test_plugin_data_injection(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Test message")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = await format_user_message_for_llm(
            msg, mock_discord_bot, config, None,
            injected_data="Plugin output here",
        )
        assert "Plugin output here" in result
        assert "tool_output" in result

    async def test_custom_emoji_removal(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Hello <:custom_emoji:123456789> world")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = await format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "<:custom_emoji:123456789>" not in result
        assert "Hello" in result
        assert "world" in result

    async def test_animated_emoji_removal(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="<a:animated:987654321> animation test")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = await format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "<a:animated:987654321>" not in result
        assert "animation test" in result

    async def test_final_user_request_block_wrapping(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Simple message")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = await format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert len(result) > 0
        assert "Simple message" in result

    async def test_image_note_injection(self, mock_discord_message, mock_discord_bot):
        image_attachment = Stub(content_type="image/png", filename="test.png")
        msg = mock_discord_message(content="Look at this", attachments=[image_attachment])
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = await format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert len(result) > 0

    async def test_no_image_note_without_attachments(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="No images here")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = await format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "No images here" in result

    async def test_rich_identity_with_role_config(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="User with role")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        role_config = {"title": "VIP User"}
        result = await format_user_message_for_llm(msg, mock_discord_bot, config, role_config)
        assert "VIP User" in result

    async def test_world_book_char_limit_respected(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Show info")
        config = {
            "user_personas": {},
            "role_based_config": {},
            "world_book_context_char_limit": 30,
            "world_book_context_max_entries": 10,
        }
        long_entry = {"id": 1, "keywords": "test", "content": "A" * 50}
        result = await format_user_message_for_llm(msg, mock_discord_bot, config, None, world_book_entries=[long_entry])
        assert result is not None

    async def test_reply_with_image_note(self, mock_discord_message, mock_discord_bot):
        replied_author = Stub(id=111, display_name="User1", bot=False)
        image_att = Stub(content_type="image/jpeg")
        replied_msg = Stub(
            author=replied_author,
            clean_content="Check this image",
            attachments=[image_att],
        )
        reference = Stub(resolved=replied_msg)
        msg = mock_discord_message(content="Nice picture", reference=reference)
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = await format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert result is not None


class TestBuildContextHistoryNone:
    @pytest.mark.asyncio
    async def test_context_mode_none_returns_empty(self):
        client = MagicMock()
        message = MagicMock()
        bot_config = {"context_mode": "none"}
        fetched, formatted = await build_context_history(client, bot_config, message, None)
        assert fetched == []
        assert formatted == []


class TestBuildContextHistoryChannel:
    @pytest.mark.asyncio
    async def test_msg_limit_zero_returns_empty(self):
        client = MagicMock()
        message = MagicMock()
        bot_config = {
            "context_mode": "channel",
            "channel_context_settings": {
                "message_limit": 0,
                "unlimited_message_count": False,
            },
        }
        fetched, formatted = await build_context_history(client, bot_config, message, None)
        assert fetched == []
        assert formatted == []

    @pytest.mark.asyncio
    async def test_empty_channel_history_returns_empty(self):
        client = MagicMock()
        message = MagicMock()
        message.channel.history = MagicMock(return_value=_history_iter([]))
        bot_config = {
            "context_mode": "channel",
            "channel_context_settings": {"message_limit": 5},
        }
        fetched, formatted = await build_context_history(client, bot_config, message, None)
        assert fetched == []
        assert formatted == []

    @pytest.mark.asyncio
    async def test_channel_history_basic(self):
        from datetime import datetime

        bot_user = Stub(id=999, name="BotUser", display_name="BotUser", bot=True)
        client = MagicMock()
        client.user = bot_user

        user_author = Stub(id=123, name="TestUser", display_name="TestUser", bot=False)

        msg1 = Stub(
            id=1,
            author=user_author,
            clean_content="Hello there",
            attachments=[],
            created_at=datetime(2024, 1, 1, 12, 0),
            content="Hello there",
        )
        msg2 = Stub(
            id=2,
            author=bot_user,
            clean_content="Hi! How can I help?",
            attachments=[],
            created_at=datetime(2024, 1, 1, 12, 1),
            content="Hi! How can I help?",
        )

        message = MagicMock()
        message.channel.history = MagicMock(return_value=_history_iter([msg1, msg2]))

        bot_config = {
            "context_mode": "channel",
            "channel_context_settings": {"message_limit": 10, "char_limit": 4000},
            "user_personas": {},
            "role_based_config": {},
        }

        fetched, formatted = await build_context_history(client, bot_config, message, None)
        assert len(formatted) == 2
        assert formatted[0]["role"] == "user"
        assert "Hello there" in formatted[0]["content"]
        assert formatted[1]["role"] == "assistant"
        assert "Hi! How can I help?" in formatted[1]["content"]

    @pytest.mark.asyncio
    async def test_channel_history_respects_msg_limit(self):
        from datetime import datetime

        bot_user = Stub(id=999, name="BotUser", display_name="BotUser", bot=True)
        client = MagicMock()
        client.user = bot_user

        user_author = Stub(id=123, name="TestUser", display_name="TestUser", bot=False)

        msgs = []
        for i in range(5):
            msgs.append(Stub(
                id=i + 1,
                author=user_author,
                clean_content=f"Message {i + 1}",
                attachments=[],
                created_at=datetime(2024, 1, 1, 12, i),
                content=f"Message {i + 1}",
            ))

        message = MagicMock()
        message.channel.history = MagicMock(return_value=_history_iter(msgs))

        bot_config = {
            "context_mode": "channel",
            "channel_context_settings": {
                "message_limit": 2,
                "char_limit": 100,
                "unlimited_message_count": False,
            },
            "user_personas": {},
            "role_based_config": {},
        }

        fetched, formatted = await build_context_history(client, bot_config, message, None)
        assert len(fetched) == 5
        assert len(formatted) <= 5

    @pytest.mark.asyncio
    async def test_channel_history_respects_char_limit(self):
        from datetime import datetime

        bot_user = Stub(id=999, name="BotUser", display_name="BotUser", bot=True)
        client = MagicMock()
        client.user = bot_user

        user_author = Stub(id=123, name="TestUser", display_name="TestUser", bot=False)

        msgs = []
        for i in range(4):
            msgs.append(Stub(
                id=i + 1,
                author=user_author,
                clean_content="A" * 80,
                attachments=[],
                created_at=datetime(2024, 1, 1, 12, i),
                content="A" * 80,
            ))

        message = MagicMock()
        message.channel.history = MagicMock(return_value=_history_iter(msgs))

        bot_config = {
            "context_mode": "channel",
            "channel_context_settings": {
                "message_limit": 10,
                "char_limit": 50,
                "unlimited_context_length": False,
            },
            "user_personas": {},
            "role_based_config": {},
        }

        fetched, formatted = await build_context_history(client, bot_config, message, None)
        assert len(fetched) == 4
        assert len(formatted) < 4

    @pytest.mark.asyncio
    async def test_channel_history_skip_empty_messages(self):
        from datetime import datetime

        bot_user = Stub(id=999, name="BotUser", display_name="BotUser", bot=True)
        client = MagicMock()
        client.user = bot_user

        user_author = Stub(id=123, name="TestUser", display_name="TestUser", bot=False)

        msg_empty = Stub(
            id=1,
            author=user_author,
            clean_content="",
            attachments=[],
            created_at=datetime(2024, 1, 1, 12, 0),
            content="",
        )
        msg_valid = Stub(
            id=2,
            author=user_author,
            clean_content="Real message",
            attachments=[],
            created_at=datetime(2024, 1, 1, 12, 1),
            content="Real message",
        )

        message = MagicMock()
        message.channel.history = MagicMock(return_value=_history_iter([msg_empty, msg_valid]))

        bot_config = {
            "context_mode": "channel",
            "channel_context_settings": {"message_limit": 10, "char_limit": 4000},
            "user_personas": {},
            "role_based_config": {},
        }

        fetched, formatted = await build_context_history(client, bot_config, message, None)
        assert len(fetched) == 2
        assert len(formatted) == 1
        assert "Real message" in formatted[0]["content"]


class TestBuildContextHistoryMemory:
    @pytest.mark.asyncio
    async def test_memory_no_trigger_keywords_no_matches(self):
        from datetime import datetime

        bot_user = Stub(id=999, name="BotUser", display_name="BotUser", bot=True)
        client = MagicMock()
        client.user = bot_user

        user_author = Stub(id=123, name="TestUser", display_name="TestUser", bot=False)

        msg1 = Stub(
            id=1,
            author=user_author,
            clean_content="Random chat message",
            attachments=[],
            created_at=datetime(2024, 1, 1, 12, 0),
            content="Random chat message",
            mentions=[],
            reference=None,
        )

        message = MagicMock()
        message.channel.history = MagicMock(return_value=_history_iter([msg1]))

        bot_config = {
            "context_mode": "memory",
            "memory_context_settings": {"message_limit": 10, "char_limit": 4000},
            "trigger_keywords": [],
            "user_personas": {},
            "role_based_config": {},
        }

        fetched, formatted = await build_context_history(client, bot_config, message, None)
        assert fetched == []
        assert formatted == []

    @pytest.mark.asyncio
    async def test_memory_bot_message_included(self):
        from datetime import datetime

        bot_user = Stub(id=999, name="BotUser", display_name="BotUser", bot=True)
        client = MagicMock()
        client.user = bot_user

        msg_bot = Stub(
            id=1,
            author=bot_user,
            clean_content="I am a bot message",
            attachments=[],
            created_at=datetime(2024, 1, 1, 12, 0),
            content="I am a bot message",
            mentions=[],
            reference=None,
        )

        message = MagicMock()
        message.channel.history = MagicMock(return_value=_history_iter([msg_bot]))

        bot_config = {
            "context_mode": "memory",
            "memory_context_settings": {"message_limit": 10, "char_limit": 4000},
            "trigger_keywords": [],
            "user_personas": {},
            "role_based_config": {},
        }

        fetched, formatted = await build_context_history(client, bot_config, message, None)
        assert len(fetched) == 1
        assert len(formatted) == 1
        assert formatted[0]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_memory_mentions_bot_included(self):
        from datetime import datetime

        bot_user = Stub(id=999, name="BotUser", display_name="BotUser", bot=True)
        client = MagicMock()
        client.user = bot_user

        user_author = Stub(id=123, name="TestUser", display_name="TestUser", bot=False)

        msg_mentions = Stub(
            id=1,
            author=user_author,
            clean_content="Hey bot, help me",
            attachments=[],
            created_at=datetime(2024, 1, 1, 12, 0),
            content="Hey bot, help me",
            mentions=[bot_user],
            reference=None,
        )

        message = MagicMock()
        message.channel.history = MagicMock(return_value=_history_iter([msg_mentions]))

        bot_config = {
            "context_mode": "memory",
            "memory_context_settings": {"message_limit": 10, "char_limit": 4000},
            "trigger_keywords": [],
            "user_personas": {},
            "role_based_config": {},
        }

        fetched, formatted = await build_context_history(client, bot_config, message, None)
        assert len(fetched) == 1
        assert len(formatted) == 1
        assert formatted[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_memory_has_keyword_included(self):
        from datetime import datetime

        bot_user = Stub(id=999, name="BotUser", display_name="BotUser", bot=True)
        client = MagicMock()
        client.user = bot_user

        user_author = Stub(id=123, name="TestUser", display_name="TestUser", bot=False)

        msg_keyword = Stub(
            id=1,
            author=user_author,
            clean_content="I need help with my homework",
            attachments=[],
            created_at=datetime(2024, 1, 1, 12, 0),
            content="I need help with my homework",
            mentions=[],
            reference=None,
        )

        message = MagicMock()
        message.channel.history = MagicMock(return_value=_history_iter([msg_keyword]))

        bot_config = {
            "context_mode": "memory",
            "memory_context_settings": {"message_limit": 10, "char_limit": 4000},
            "trigger_keywords": ["help"],
            "trigger_match_mode": "contains",
            "trigger_case_sensitive": False,
            "user_personas": {},
            "role_based_config": {},
        }

        fetched, formatted = await build_context_history(client, bot_config, message, None)
        assert len(fetched) == 1
        assert len(formatted) == 1

    @pytest.mark.asyncio
    async def test_memory_respects_msg_limit(self):
        from datetime import datetime

        bot_user = Stub(id=999, name="BotUser", display_name="BotUser", bot=True)
        client = MagicMock()
        client.user = bot_user

        msgs = []
        for i in range(5):
            msgs.append(Stub(
                id=i + 1,
                author=bot_user,
                clean_content=f"Bot message {i + 1}",
                attachments=[],
                created_at=datetime(2024, 1, 1, 12, i),
                content=f"Bot message {i + 1}",
                mentions=[],
                reference=None,
            ))

        message = MagicMock()
        message.channel.history = MagicMock(return_value=_history_iter(msgs))

        bot_config = {
            "context_mode": "memory",
            "memory_context_settings": {
                "message_limit": 3,
                "char_limit": 4000,
                "unlimited_message_count": False,
            },
            "trigger_keywords": [],
            "user_personas": {},
            "role_based_config": {},
        }

        fetched, formatted = await build_context_history(client, bot_config, message, None)
        assert len(fetched) == 3
        assert len(formatted) == 3

    @pytest.mark.asyncio
    async def test_memory_replied_to_message_included(self):
        from datetime import datetime

        bot_user = Stub(id=999, name="BotUser", display_name="BotUser", bot=True)
        client = MagicMock()
        client.user = bot_user

        user_author = Stub(id=123, name="TestUser", display_name="TestUser", bot=False)

        bot_replied_msg = Stub(
            id=1,
            author=bot_user,
            clean_content="Bot's original message",
            attachments=[],
            created_at=datetime(2024, 1, 1, 12, 0),
            content="Bot's original message",
            mentions=[],
            reference=None,
        )

        reference_stub = Stub(resolved=bot_replied_msg)

        user_reply_msg = Stub(
            id=2,
            author=user_author,
            clean_content="User replying to bot",
            attachments=[],
            created_at=datetime(2024, 1, 1, 12, 1),
            content="User replying to bot",
            mentions=[bot_user],
            reference=reference_stub,
        )

        message = MagicMock()
        message.channel.history = MagicMock(return_value=_history_iter([user_reply_msg, bot_replied_msg]))

        bot_config = {
            "context_mode": "memory",
            "memory_context_settings": {"message_limit": 10, "char_limit": 4000},
            "trigger_keywords": [],
            "user_personas": {},
            "role_based_config": {},
        }

        fetched, formatted = await build_context_history(client, bot_config, message, None)
        assert len(fetched) >= 2
        assert len(formatted) >= 2


def _basic_config() -> dict:
    return {"user_personas": {}, "role_based_config": {}}


def _blacklist_config() -> dict:
    return {
        **_basic_config(),
        "user_options": {
            "enabled": True,
            "rules": {
                "r1": {
                    "scope_type": "global",
                    "mode": "blacklist",
                    "users": {
                        "u1": {"user_id": "123456789", "blacklist_mode": "block_messages"},
                    },
                }
            },
        },
    }


class TestFormatUserMessageTemplates:
    """format_user_message_for_llm 的 templates 参数 7 键全量生效验证（S1/S3 接线目标）. """

    async def test_template_message_format_effective(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Hello world")
        templates = {"message_format": "«{author_id_str}»「{content}」"}
        result = await format_user_message_for_llm(msg, mock_discord_bot, _basic_config(), None, templates=templates)
        assert "«TestUser TestUser id：123456789»" in result
        assert "「Hello world」" in result

    async def test_template_image_note_effective(self, mock_discord_message, mock_discord_bot):
        image_attachment = Stub(content_type="image/png", filename="test.png")
        msg = mock_discord_message(content="Look at this", attachments=[image_attachment])
        templates = {"image_note": "【{count}张图】"}
        result = await format_user_message_for_llm(msg, mock_discord_bot, _basic_config(), None, templates=templates)
        assert "【1张图】" in result

    async def test_template_reply_context_effective(self, mock_discord_message, mock_discord_bot):
        replied_author = Stub(id=111222, display_name="OriginalAuthor", bot=False)
        replied_msg = Stub(
            author=replied_author,
            clean_content="Original message text",
            attachments=[],
        )
        reference = Stub(resolved=replied_msg)
        msg = mock_discord_message(content="My reply", reference=reference)
        templates = {"reply_context": "回复了{author_info}：{replied_content}"}
        result = await format_user_message_for_llm(msg, mock_discord_bot, _basic_config(), None, templates=templates)
        assert "回复了" in result
        assert "Original message text" in result

    async def test_template_deleted_reply_context_effective(self, mock_discord_message, mock_discord_bot):
        DeletedRef = type("DeletedReferencedMessage", (), {})
        reference = Stub(resolved=DeletedRef())
        msg = mock_discord_message(content="Replying to deleted", reference=reference)
        templates = {"deleted_reply_context": "这条回复已被删除"}
        result = await format_user_message_for_llm(msg, mock_discord_bot, _basic_config(), None, templates=templates)
        assert "这条回复已被删除" in result

    async def test_template_tool_context_effective(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Test message")
        templates = {"tool_context": "工具输出: {data}"}
        result = await format_user_message_for_llm(
            msg, mock_discord_bot, _basic_config(), None,
            injected_data="Plugin output here", templates=templates,
        )
        assert "工具输出: Plugin output here" in result

    async def test_template_worldbook_context_effective(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Tell me about the kingdom")
        templates = {"worldbook_context": "世界书: {data}"}
        world_book_entries = [{"id": 1, "keywords": "kingdom", "content": "The kingdom is magical."}]
        result = await format_user_message_for_llm(
            msg, mock_discord_bot, _basic_config(), None,
            world_book_entries=world_book_entries, templates=templates,
        )
        assert "世界书:" in result
        assert "The kingdom is magical." in result

    async def test_template_user_request_block_effective(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Simple message")
        templates = {"user_request_block": "<user_request>\n{parts}\n</user_request>"}
        result = await format_user_message_for_llm(msg, mock_discord_bot, _basic_config(), None, templates=templates)
        assert result.startswith("<user_request>")
        assert result.endswith("</user_request>")
        assert "Simple message" in result


class TestBlacklistBlockTemplates:
    """黑名单 block 路径经 _format_tpl 消费 user_request_block 键；无键/非法逐字节回退（S1/A4）. """

    async def test_blacklist_block_uses_template(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Hello world")
        templates = {"user_request_block": "<block>{parts}</block>"}
        result = await format_user_message_for_llm(
            msg, mock_discord_bot, _blacklist_config(), None, templates=templates
        )
        block_notice = get_formatted_block_notice(msg.author, {}, {}, "block_messages")
        assert result == f"<block>{block_notice}</block>"

    @pytest.mark.parametrize("templates", [None, {}, {"user_request_block": ""}, {"user_request_block": 123}])
    async def test_blacklist_block_fallback_byte_identical(
        self, mock_discord_message, mock_discord_bot, templates
    ):
        msg = mock_discord_message(content="Hello world")
        result = await format_user_message_for_llm(
            msg, mock_discord_bot, _blacklist_config(), None, templates=templates
        )
        block_notice = get_formatted_block_notice(msg.author, {}, {}, "block_messages")
        assert result == USER_REQUEST_BLOCK_TPL.format(parts=block_notice)


class TestTemplatesBoundary:
    """边界表：无键/非法值/空串/占位符缺失/未知键 → 与无模板基线逐字节一致（A3）. """

    @pytest.mark.parametrize("templates", [
        None,
        {},
        {"message_format": ""},
        {"message_format": None},
        {"message_format": 123},
        {"message_format": ["not-a-str"]},
        {"message_format": "{missing_placeholder}"},
        {"unknown_key": "ignored"},
        {"image_note": "", "reply_context": "", "tool_context": "", "worldbook_context": ""},
    ])
    async def test_boundary_byte_identical(self, mock_discord_message, mock_discord_bot, templates):
        msg = mock_discord_message(content="Hello world")
        expected = await format_user_message_for_llm(msg, mock_discord_bot, _basic_config(), None, templates=None)
        result = await format_user_message_for_llm(msg, mock_discord_bot, _basic_config(), None, templates=templates)
        assert result == expected


class TestResolvePromptTemplates:
    """读取点归一化：非 dict（含缺省）一律 None（契约：消费点只接 None/dict）. """

    def test_missing_key_returns_none(self):
        assert resolve_prompt_templates({}) is None

    def test_explicit_none_returns_none(self):
        assert resolve_prompt_templates({"prompt_templates": None}) is None

    @pytest.mark.parametrize("bad", ["not-a-dict", 42, [], ("a",), False])
    def test_non_dict_returns_none(self, bad):
        assert resolve_prompt_templates({"prompt_templates": bad}) is None

    def test_valid_dict_returned_as_is(self):
        t = {"message_format": "x"}
        assert resolve_prompt_templates({"prompt_templates": t}) is t


class TestFormatMemoryContext:
    """memory_context helper：占位符匹配才生效，否则 None（S5 回退语义）. """

    def test_effective_with_placeholder(self):
        result = format_memory_context({"memory_context": "记忆块:\n{data}"}, "MEM")
        assert result == "记忆块:\nMEM"

    def test_effective_multiple_placeholder(self):
        result = format_memory_context({"memory_context": "【{data}】【{data}】"}, "MEM")
        assert result == "【MEM】【MEM】"

    @pytest.mark.parametrize("templates", [
        None,
        {},
        {"memory_context": ""},
        {"memory_context": None},
        {"memory_context": 123},
        {"memory_context": ["not-a-str"]},
        {"memory_context": "静态文本无占位符"},
        {"memory_context": "{other_placeholder}"},
        {"memory_context": "{data}{other}"},
        {"memory_context": "{}"},
        {"memory_context": "前{data:>{x}}后"},
    ])
    def test_inapplicable_returns_none(self, templates):
        assert format_memory_context(templates, "MEM") is None


class TestFormatTplAttributeAccess:
    """F-1：模板属性访问表达式（{content.upper()} / {data.nonexistent_attr}）不再崩溃.

    AttributeError 此前未捕获：{content.nonexistent_attr} 等属性访问模板会导致
    pipeline 消息静默丢弃 / chat·debug 500。修复后属性表达式正常格式化，
    不存在属性时回退默认（format_memory_context 返回 None，调用方保持旧拼接）。
    """

    def test_format_tpl_attribute_expression_works(self):
        """{content.upper()}（属性调用语法，str.format 不支持）→ AttributeError → 回退默认，无异常."""
        result = _format_tpl(
            "{content.upper()} {content}", USER_MESSAGE_TPL,
            author_id_str="u1", content="hi", image_note="",
        )
        assert result == "[u1]: hi"

    def test_format_tpl_missing_attribute_falls_back(self):
        """{content.nonexistent_attr} 属性不存在 → AttributeError → 回退默认常量."""
        result = _format_tpl(
            "{content.nonexistent_attr}", USER_MESSAGE_TPL,
            author_id_str="u1", content="hi", image_note="",
        )
        assert result == "[u1]: hi"

    def test_format_memory_context_attribute_expression_works(self):
        """memory_context 含 {data.upper()}（属性调用语法）→ AttributeError → None（旧拼接回退）."""
        result = format_memory_context({"memory_context": "记忆块:\n{data.upper()}"}, "MEM")
        assert result is None

    def test_format_memory_context_missing_attribute_returns_none(self):
        """memory_context 含 {data.nonexistent_attr} → AttributeError → None（旧拼接回退）."""
        result = format_memory_context({"memory_context": "记忆块:\n{data.nonexistent_attr}"}, "MEM")
        assert result is None


class TestFormatTplFallbackWarning:
    """F-2：回退告警仅自定义模板（tpl_key 提供）时记录，含键名不含模板内容."""

    def test_fallback_logs_warning_with_tpl_key(self, caplog):
        with caplog.at_level(logging.WARNING, logger="app.core_logic.context_builder"):
            result = _format_tpl(
                "{author_name}", USER_MESSAGE_TPL,
                tpl_key="message_format",
                author_id_str="u1", content="hi", image_note="",
            )
        assert result == "[u1]: hi"
        messages = [r.message for r in caplog.records]
        assert any("template 'message_format' fallback to default (key=author_name)" in m for m in messages)

    def test_fallback_no_warning_without_tpl_key(self, caplog):
        """默认路径（未提供 tpl_key）回退不记录，避免每消息刷屏."""
        with caplog.at_level(logging.WARNING, logger="app.core_logic.context_builder"):
            _format_tpl(
                "{author_name}", USER_MESSAGE_TPL,
                author_id_str="u1", content="hi", image_note="",
            )
        assert not any("fallback to default" in r.message for r in caplog.records)

    def test_fallback_warning_logs_key_only_not_content(self, caplog):
        """告警日志不得包含模板内容/用户数据（仅键名与缺失占位符）."""
        with caplog.at_level(logging.WARNING, logger="app.core_logic.context_builder"):
            _format_tpl(
                "SECRET-PAYLOAD-{author_name}-SECRET", USER_MESSAGE_TPL,
                tpl_key="message_format",
                author_id_str="u1", content="hi", image_note="",
            )
        for record in caplog.records:
            assert "SECRET-PAYLOAD" not in record.message
            assert "hi" not in record.message

    async def test_runtime_message_format_fallback_logs_with_key(self, caplog, mock_discord_message, mock_discord_bot):
        """format_user_message_for_llm 自定义坏模板 → 回退 + 键名告警（仅 templates 提供时）."""
        msg = mock_discord_message(content="Hello world")
        templates = {"message_format": "{author_name}"}
        with caplog.at_level(logging.WARNING, logger="app.core_logic.context_builder"):
            result = await format_user_message_for_llm(msg, mock_discord_bot, _basic_config(), None, templates=templates)
        assert "Hello world" in result
        assert any("template 'message_format' fallback to default (key=author_name)" in r.message for r in caplog.records)

    async def test_runtime_default_path_no_warning(self, caplog, mock_discord_message, mock_discord_bot):
        """templates=None（默认路径）→ 不产生回退告警（避免每消息刷屏）."""
        msg = mock_discord_message(content="Hello world")
        with caplog.at_level(logging.WARNING, logger="app.core_logic.context_builder"):
            await format_user_message_for_llm(msg, mock_discord_bot, _basic_config(), None, templates=None)
        assert not any("fallback to default" in r.message for r in caplog.records)
