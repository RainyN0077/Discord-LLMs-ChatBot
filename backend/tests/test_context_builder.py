import pytest
pytestmark = [pytest.mark.unit]
from app.utils import Stub, _async_stub
from app.core_logic.context_builder import format_user_message_for_llm

from app.core_logic.context_builder import build_context_history
from unittest.mock import AsyncMock, MagicMock, patch
import discord


async def _history_iter(items):
    for item in items:
        yield item


class TestFormatUserMessageForLLM:
    def test_basic_message_formatting(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Hello world")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "[用户请求块]" in result or "Hello world" in result

    def test_removes_bot_mention(self, mock_discord_message, mock_discord_bot):
        bot_id = str(mock_discord_bot.user.id)
        msg = mock_discord_message(content=f"<@{bot_id}> help me please")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "help me please" in result
        assert f"<@{bot_id}>" not in result

    def test_removes_bot_mention_exclamation(self, mock_discord_message, mock_discord_bot):
        bot_id = str(mock_discord_bot.user.id)
        msg = mock_discord_message(content=f"<@!{bot_id}> hello")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "hello" in result

    def test_reply_context_stub_not_discord_message(self, mock_discord_message, mock_discord_bot):
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
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert len(result) > 0

    def test_deleted_reply_handling(self, mock_discord_message, mock_discord_bot):
        reference = Stub(resolved="not a valid message")
        msg = mock_discord_message(content="Replying to deleted", reference=reference)
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert len(result) > 0

    def test_world_book_injection_via_parameter(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Tell me about the kingdom")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        world_book_entries = [
            {"id": 1, "keywords": "kingdom, magic", "content": "The kingdom is magical."},
            {"id": 2, "keywords": "dragons", "content": "Dragons are rare."},
        ]
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None, world_book_entries=world_book_entries)
        assert "The kingdom is magical." in result
        assert "Dragons are rare." in result

    def test_plugin_data_injection(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Test message")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = format_user_message_for_llm(
            msg, mock_discord_bot, config, None,
            injected_data="Plugin output here",
        )
        assert "Plugin output here" in result
        assert "tool_output" in result

    def test_custom_emoji_removal(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Hello <:custom_emoji:123456789> world")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "<:custom_emoji:123456789>" not in result
        assert "Hello" in result
        assert "world" in result

    def test_animated_emoji_removal(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="<a:animated:987654321> animation test")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "<a:animated:987654321>" not in result
        assert "animation test" in result

    def test_final_user_request_block_wrapping(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Simple message")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert len(result) > 0
        assert "Simple message" in result

    def test_image_note_injection(self, mock_discord_message, mock_discord_bot):
        image_attachment = Stub(content_type="image/png", filename="test.png")
        msg = mock_discord_message(content="Look at this", attachments=[image_attachment])
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert len(result) > 0

    def test_no_image_note_without_attachments(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="No images here")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "No images here" in result

    def test_rich_identity_with_role_config(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="User with role")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        role_config = {"title": "VIP User"}
        result = format_user_message_for_llm(msg, mock_discord_bot, config, role_config)
        assert "VIP User" in result

    def test_world_book_char_limit_respected(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Show info")
        config = {
            "user_personas": {},
            "role_based_config": {},
            "world_book_context_char_limit": 30,
            "world_book_context_max_entries": 10,
        }
        long_entry = {"id": 1, "keywords": "test", "content": "A" * 50}
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None, world_book_entries=[long_entry])
        assert result is not None

    def test_reply_with_image_note(self, mock_discord_message, mock_discord_bot):
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
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert result is not None


class TestBuildContextHistoryNone:
    @pytest.mark.asyncio
    async def test_context_mode_none_returns_empty(self):
        client = MagicMock(spec=discord.Client)
        message = MagicMock(spec=discord.Message)
        bot_config = {"context_mode": "none"}
        fetched, formatted = await build_context_history(client, bot_config, message, None)
        assert fetched == []
        assert formatted == []


class TestBuildContextHistoryChannel:
    @pytest.mark.asyncio
    async def test_msg_limit_zero_returns_empty(self):
        client = MagicMock(spec=discord.Client)
        message = MagicMock(spec=discord.Message)
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
        client = MagicMock(spec=discord.Client)
        message = MagicMock(spec=discord.Message)
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
        client = MagicMock(spec=discord.Client)
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

        message = MagicMock(spec=discord.Message)
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
        client = MagicMock(spec=discord.Client)
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

        message = MagicMock(spec=discord.Message)
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
        client = MagicMock(spec=discord.Client)
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

        message = MagicMock(spec=discord.Message)
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
        client = MagicMock(spec=discord.Client)
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

        message = MagicMock(spec=discord.Message)
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
        client = MagicMock(spec=discord.Client)
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

        message = MagicMock(spec=discord.Message)
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
        client = MagicMock(spec=discord.Client)
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

        message = MagicMock(spec=discord.Message)
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
        client = MagicMock(spec=discord.Client)
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

        message = MagicMock(spec=discord.Message)
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
        client = MagicMock(spec=discord.Client)
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

        message = MagicMock(spec=discord.Message)
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
        client = MagicMock(spec=discord.Client)
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

        message = MagicMock(spec=discord.Message)
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
    async def test_memory_replied_to_message_included(self, monkeypatch):
        import builtins

        _orig_isinstance = builtins.isinstance

        def _custom_isinstance(obj, classinfo):
            if _orig_isinstance(obj, Stub) and classinfo is discord.Message and getattr(obj, "_as_discord_msg", False):
                return True
            return _orig_isinstance(obj, classinfo)

        monkeypatch.setattr(builtins, "isinstance", _custom_isinstance)

        from datetime import datetime

        bot_user = Stub(id=999, name="BotUser", display_name="BotUser", bot=True)
        client = MagicMock(spec=discord.Client)
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
            _as_discord_msg=True,
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

        message = MagicMock(spec=discord.Message)
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
