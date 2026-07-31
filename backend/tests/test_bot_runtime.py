"""BotRuntime 端口/适配器测试 — MockBotRuntime 行为 + NoneBotRuntime 适配 + 工厂."""
import pytest

from app.adapters.factory import create_bot_runtime
from app.adapters.mock_bot_runtime import MockBotRuntime
from app.adapters.nonebot_runtime import NoneBotRuntime
from app.adapters.discord_platform_adapter import DiscordPlatformAdapter
from app.ports.bot_runtime import BotRuntime, BotStatus
from app.utils import Stub, _async_stub

RUNTIME_CONFIG = {
    "bot_name": "TestBot",
    "platform": "discord",
    "runtime_type": "nonebot",
}


@pytest.fixture(autouse=True)
def _clean_self_id_mappings():
    """清理 DiscordPlatformAdapter 类级 self_id 映射（跨测试隔离）."""
    yield
    DiscordPlatformAdapter._self_id_to_bot_id.clear()


class TestMockBotRuntime:
    async def test_identity_properties(self):
        runtime = MockBotRuntime(bot_id="mock-1")
        assert runtime.bot_id == "mock-1"
        assert runtime.self_id == "1234567890"
        assert runtime.display_name == "Mock Bot"
        assert runtime.platform == "mock"
        assert isinstance(runtime, BotRuntime)

    async def test_start_stop_status_lifecycle(self):
        runtime = MockBotRuntime()
        assert runtime.status == BotStatus.STOPPED
        await runtime.start()
        assert runtime.status == BotStatus.RUNNING
        await runtime.stop()
        assert runtime.status == BotStatus.STOPPED

    async def test_health(self):
        runtime = MockBotRuntime(bot_id="mock-2")
        health = await runtime.health()
        assert health == {"bot_id": "mock-2", "status": "stopped", "platform": "mock"}

    async def test_send_message_records_and_returns_id(self):
        runtime = MockBotRuntime()
        msg_id = await runtime.send_message("chan-1", "hello", reply_to_message_id="reply-1")
        assert msg_id == "mock_msg_0"
        assert runtime.sent_messages == [
            {
                "channel_id": "chan-1",
                "content": "hello",
                "reply_to": "reply-1",
                "message_id": "mock_msg_0",
            }
        ]

    async def test_edit_message_records(self):
        runtime = MockBotRuntime()
        await runtime.edit_message("chan-1", "msg-9", "updated")
        assert runtime.edited_messages == [
            {"channel_id": "chan-1", "message_id": "msg-9", "content": "updated"}
        ]

    async def test_trigger_typing_indicator_noop(self):
        runtime = MockBotRuntime()
        await runtime.trigger_typing_indicator("chan-1")  # 不抛即通过

    def test_get_feature_all_true(self):
        runtime = MockBotRuntime()
        assert runtime.get_feature("edit_message") is True
        assert runtime.get_feature("typing_indicator") is True


class TestNoneBotRuntime:
    def _make_runtime(self, bot_id="nb-1"):
        return NoneBotRuntime(bot_id, dict(RUNTIME_CONFIG))

    async def test_identity_properties(self):
        runtime = self._make_runtime()
        assert runtime.bot_id == "nb-1"
        assert runtime.display_name == "TestBot"
        assert runtime.platform == "discord"
        assert runtime.self_id == ""  # 未 attach bot

    async def test_start_stop(self):
        runtime = self._make_runtime()
        await runtime.start()
        assert runtime.status == BotStatus.RUNNING
        health = await runtime.health()
        assert health["status"] == "running"
        assert health["connected"] is False
        await runtime.stop()
        assert runtime.status == BotStatus.STOPPED

    async def test_send_message_without_bot_raises(self):
        runtime = self._make_runtime()
        with pytest.raises(RuntimeError, match="Bot not running"):
            await runtime.send_message("chan-1", "hello")

    async def test_send_message_with_bot_delegates(self):
        runtime = self._make_runtime()
        bot = Stub(
            self_id="111222333",
            send_to=_async_stub(Stub(id="sent-1")),
        )
        runtime.attach_bot(bot)
        msg_id = await runtime.send_message("42", "hello")
        assert msg_id == "sent-1"
        assert runtime.self_id == "111222333"

    async def test_attach_bot_registers_self_id_mapping(self):
        runtime = self._make_runtime()
        bot = Stub(self_id="111222333")
        runtime.attach_bot(bot)
        assert DiscordPlatformAdapter._self_id_to_bot_id["111222333"] == "nb-1"
        # stop 时清理映射
        await runtime.stop()
        assert "111222333" not in DiscordPlatformAdapter._self_id_to_bot_id

    async def test_edit_message_delegates(self):
        runtime = self._make_runtime()
        bot = Stub(self_id="1", edit_message=_async_stub(None))
        runtime.attach_bot(bot)
        await runtime.edit_message("7", "8", "new")  # 不抛即通过

    async def test_trigger_typing_indicator_exception_swallowed(self):
        runtime = self._make_runtime()

        async def _boom(channel_id):
            raise RuntimeError("typing failed")

        runtime.attach_bot(Stub(self_id="1", trigger_typing_indicator=_boom))
        await runtime.trigger_typing_indicator("9")  # 异常不传播

    def test_get_feature_map(self):
        runtime = self._make_runtime()
        assert runtime.get_feature("send_message") is True
        assert runtime.get_feature("unknown_feature") is False


class TestCreateBotRuntime:
    def test_factory_nonebot(self):
        runtime = create_bot_runtime("bot-1", {"runtime_type": "nonebot"})
        assert isinstance(runtime, NoneBotRuntime)

    def test_factory_mock(self):
        runtime = create_bot_runtime("bot-2", {"runtime_type": "mock"})
        assert isinstance(runtime, MockBotRuntime)

    def test_factory_default_nonebot(self):
        runtime = create_bot_runtime("bot-3", {})
        assert isinstance(runtime, NoneBotRuntime)

    def test_factory_invalid_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported runtime_type"):
            create_bot_runtime("bot-4", {"runtime_type": "weird"})
