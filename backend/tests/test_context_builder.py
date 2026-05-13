import pytest
from app.utils import Stub, _async_stub
from app.core_logic.context_builder import format_user_message_for_llm


class TestFormatUserMessageForLLM:
    def test_basic_message_formatting(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="Hello world")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "[用户请求块]" in result
        assert "Hello world" in result

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
        """Stub reference.resolved fails isinstance(discord.Message) check, falls to deleted branch."""
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
        assert "已被删除" in result

    def test_deleted_reply_handling(self, mock_discord_message, mock_discord_bot):
        reference = Stub(resolved="not a valid message")
        msg = mock_discord_message(content="Replying to deleted", reference=reference)
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "已被删除" in result

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
        assert "<tool_output>" in result

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
        assert result.startswith("[用户请求块]")
        assert result.endswith("[/用户请求块]")

    def test_image_note_injection(self, mock_discord_message, mock_discord_bot):
        image_attachment = Stub(content_type="image/png", filename="test.png")
        msg = mock_discord_message(content="Look at this", attachments=[image_attachment])
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "张图片" in result

    def test_no_image_note_without_attachments(self, mock_discord_message, mock_discord_bot):
        msg = mock_discord_message(content="No images here")
        config = {
            "user_personas": {},
            "role_based_config": {},
        }
        result = format_user_message_for_llm(msg, mock_discord_bot, config, None)
        assert "张图片" not in result

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
        assert "已被删除" in result
