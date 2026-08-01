"""DiscordPlatformAdapter 测试 — 事件转换、self_id 映射、平台名、触发判断.

Discord MessageEvent 用鸭子类型 Stub 模拟（nonebot.adapters.discord 实例化复杂）。
"""
import pytest

from app.adapters.discord_platform_adapter import DiscordPlatformAdapter
from app.adapters.mock_bot_runtime import MockBotRuntime
from app.utils import Stub


@pytest.fixture(autouse=True)
def _clean_self_id_mappings():
    """清理类级 self_id 映射（跨测试隔离）."""
    yield
    DiscordPlatformAdapter._self_id_to_bot_id.clear()


def _make_event(**overrides) -> Stub:
    """构造鸭子类型 Discord 事件."""
    author = Stub(
        id=123456789,
        username="TestUser",
        global_name="TestDisplay",
        bot=False,
        roles=[Stub(id=111), Stub(id=222)],
    )
    defaults = {
        "id": "msg-100",
        "content": "Hello world",
        "author": author,
        "channel_id": 987654321,
        "guild_id": 555555555,
        "mentions": [
            Stub(id=777, username="Mentioned", global_name="MentionDisplay"),
        ],
        "attachments": [
            Stub(url="https://cdn.example.com/a.png", filename="a.png", content_type="image/png"),
        ],
        "self_id": "999999999",
    }
    defaults.update(overrides)
    return Stub(**defaults)


class TestEventToMessage:
    async def test_full_conversion(self):
        adapter = DiscordPlatformAdapter()
        runtime = MockBotRuntime()  # self_id = 1234567890, 与 author.id 不同
        message = await adapter.event_to_message(_make_event(), runtime)
        assert message is not None
        assert message.id == "msg-100"
        assert message.content == "Hello world"
        assert message.author.id == "123456789"
        assert message.author.name == "TestUser"
        assert message.author.display_name == "TestDisplay"
        assert message.author.is_bot is False
        assert message.author.roles == ["111", "222"]
        assert message.channel.id == "987654321"
        assert message.guild.id == "555555555"
        assert [m.id for m in message.mentions] == ["777"]
        assert message.attachments[0].url == "https://cdn.example.com/a.png"
        assert message.attachments[0].filename == "a.png"
        assert message.attachments[0].content_type == "image/png"

    async def test_self_filter_returns_none(self):
        adapter = DiscordPlatformAdapter()
        runtime = MockBotRuntime()  # self_id = "1234567890"
        event = _make_event(author=Stub(id=1234567890, username="Bot", bot=True))
        assert await adapter.event_to_message(event, runtime) is None

    async def test_missing_optionals(self):
        adapter = DiscordPlatformAdapter()
        runtime = MockBotRuntime()
        event = Stub(
            id="m",
            content="x",
            author=Stub(id=1, username="User", global_name=None, bot=False, roles=[]),
            channel_id=1,
            guild_id=None,
            mentions=[],
            attachments=[],
            self_id="s",
        )
        message = await adapter.event_to_message(event, runtime)
        assert message.guild is None
        assert message.mentions == []
        assert message.attachments == []
        assert message.author.roles == []

    async def test_no_author_falls_back_to_unknown(self):
        adapter = DiscordPlatformAdapter()
        runtime = MockBotRuntime()
        # author 缺失（如系统消息/某些边缘事件）→ 不抛异常，回退 unknown 作者
        event = _make_event(author=None)
        message = await adapter.event_to_message(event, runtime)
        assert message is not None
        assert message.author.id == "unknown"
        assert message.author.name == "Unknown"
        assert message.author.display_name == "Unknown"

    async def test_author_bot_flag(self):
        adapter = DiscordPlatformAdapter()
        runtime = MockBotRuntime()
        event = _make_event(author=Stub(id=1, username="Bot", global_name=None, bot=True, roles=[]))
        message = await adapter.event_to_message(event, runtime)
        assert message.author.is_bot is True
        assert message.author.display_name == "Bot"  # global_name 缺失回退 username


class TestMappingAndIdentity:
    def test_register_unregister_self_id_mapping(self):
        adapter = DiscordPlatformAdapter()
        adapter.register_self_id_mapping("111", "bot-a")
        adapter.register_self_id_mapping("222", "bot-b")
        assert adapter._self_id_to_bot_id == {"111": "bot-a", "222": "bot-b"}
        adapter.unregister_self_id_mapping("111")
        assert "111" not in adapter._self_id_to_bot_id
        adapter.unregister_self_id_mapping("missing")  # 不抛

    def test_get_bot_id_from_event(self):
        adapter = DiscordPlatformAdapter()
        adapter.register_self_id_mapping("123", "bot-main")
        assert adapter.get_bot_id_from_event(Stub(self_id="123")) == "bot-main"
        assert adapter.get_bot_id_from_event(Stub(self_id="unknown")) is None
        assert adapter.get_bot_id_from_event(Stub(self_id=None)) is None
        assert adapter.get_bot_id_from_event(Stub()) is None

    def test_get_platform_name(self):
        assert DiscordPlatformAdapter().get_platform_name() == "discord"

    def test_is_triggered_default_true(self):
        adapter = DiscordPlatformAdapter()
        assert adapter.is_triggered(None, {}) is True
