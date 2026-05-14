from unittest.mock import MagicMock
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.nonebug]

from nb_plugins.core_llm_bot.event_shim import event_to_message_context, MessageContext


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


class TestEventToMessageContext:
    def test_basic_conversion(self):
        event = _make_event()
        bot = MagicMock()
        ctx = event_to_message_context(event, bot)
        assert isinstance(ctx, MessageContext)
        assert ctx.id == 1001
        assert ctx.content == "Hello"
        assert ctx.author.id == 123
        assert ctx.author.name == "Tester"
        assert ctx.channel.id == 456
        assert ctx.guild.id == 789

    def test_empty_content(self):
        event = _make_event(content="")
        bot = MagicMock()
        ctx = event_to_message_context(event, bot)
        assert ctx.content == ""

    def test_no_guild(self):
        event = _make_event(guild_id=None)
        bot = MagicMock()
        ctx = event_to_message_context(event, bot)
        assert ctx.guild is None

    def test_with_mentions(self):
        m = MagicMock()
        m.id = 999
        m.username = "Mentioned"
        event = _make_event(mentions=[m])
        bot = MagicMock()
        ctx = event_to_message_context(event, bot)
        assert len(ctx.mentions) == 1
        assert ctx.mentions[0].id == 999
        assert ctx.mentions[0].name == "Mentioned"

    def test_with_attachments(self):
        a = MagicMock()
        a.url = "https://example.com/img.png"
        a.filename = "img.png"
        a.content_type = "image/png"
        event = _make_event(attachments=[a])
        bot = MagicMock()
        ctx = event_to_message_context(event, bot)
        assert len(ctx.attachments) == 1
        assert ctx.attachments[0].url == "https://example.com/img.png"

    def test_with_reply(self):
        reply = MagicMock()
        reply.id = 2001
        reply.content = "Original"
        ra = MagicMock()
        ra.id = 456
        ra.username = "ReplyUser"
        ra.global_name = "ReplyUser"
        reply.author = ra
        event = _make_event(reply=reply)
        bot = MagicMock()
        ctx = event_to_message_context(event, bot)
        assert ctx.reference.resolved.id == 2001
        assert ctx.reference.resolved.author.name == "ReplyUser"
