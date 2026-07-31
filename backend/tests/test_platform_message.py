"""PlatformMessage 数据模型测试 — AuthorInfo/ChannelInfo/GuildInfo/AttachmentInfo/PlatformMessage."""
from datetime import datetime, timezone

from app.ports.platform_message import (
    AttachmentInfo,
    AuthorInfo,
    ChannelInfo,
    GuildInfo,
    PlatformMessage,
)


class TestAuthorInfo:
    def test_fields_and_bot_property(self):
        author = AuthorInfo(
            id="u-1",
            name="User",
            display_name="Display",
            roles=["r1", "r2"],
            is_bot=True,
        )
        assert author.bot is True
        assert author.roles == ["r1", "r2"]

    def test_defaults(self):
        author = AuthorInfo(id="u-2", name="N", display_name="N")
        assert author.roles == []
        assert author.is_bot is False
        assert author.bot is False

    def test_hash_by_id(self):
        a1 = AuthorInfo(id="same", name="A", display_name="A")
        a2 = AuthorInfo(id="same", name="B", display_name="B")
        a3 = AuthorInfo(id="diff", name="A", display_name="A")
        assert hash(a1) == hash(a2)
        assert hash(a1) != hash(a3)

    def test_bool_always_true(self):
        assert bool(AuthorInfo(id="u-3", name="N", display_name="N")) is True


class TestMetadataModels:
    def test_channel_info_defaults(self):
        channel = ChannelInfo(id="c-1")
        assert channel.name == ""
        assert channel.type == "text"

    def test_guild_info_defaults(self):
        guild = GuildInfo(id="g-1")
        assert guild.name == ""

    def test_attachment_info_defaults(self):
        attachment = AttachmentInfo(url="https://example.com/a.png")
        assert attachment.filename == ""
        assert attachment.content_type == ""
        assert attachment.bytes is None


class TestPlatformMessage:
    def test_full_fields(self):
        author = AuthorInfo(id="u-1", name="U", display_name="U")
        message = PlatformMessage(
            id="msg-1",
            content="hi",
            author=author,
            channel=ChannelInfo(id="c-1"),
            guild=GuildInfo(id="g-1"),
            mentions=[author],
            attachments=[AttachmentInfo(url="https://x/y.png")],
            raw="raw-event",
        )
        assert message.id == "msg-1"
        assert message.content == "hi"
        assert message.author is author
        assert message.guild.id == "g-1"
        assert len(message.mentions) == 1
        assert len(message.attachments) == 1
        assert message.raw == "raw-event"

    def test_created_at_aware_datetime(self):
        message = PlatformMessage(
            id="m", content="", author=AuthorInfo(id="u", name="U", display_name="U"),
            channel=ChannelInfo(id="c"),
        )
        assert isinstance(message.created_at, datetime)
        assert message.created_at.tzinfo is not None

    def test_default_lists_are_independent(self):
        a = PlatformMessage(
            id="a", content="", author=AuthorInfo(id="u", name="U", display_name="U"),
            channel=ChannelInfo(id="c"),
        )
        b = PlatformMessage(
            id="b", content="", author=AuthorInfo(id="u", name="U", display_name="U"),
            channel=ChannelInfo(id="c"),
        )
        a.mentions.append("x")
        a.attachments.append("y")
        assert b.mentions == []
        assert b.attachments == []
