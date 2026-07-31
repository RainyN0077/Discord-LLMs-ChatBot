"""DefaultMessageBus 测试 — 路由、订阅、异常隔离."""
from typing import Optional

import pytest

from app.adapters.message_bus_impl import DefaultMessageBus
from app.adapters.mock_bot_runtime import MockBotRuntime
from app.ports.platform_message import AuthorInfo, ChannelInfo, PlatformMessage
from app.utils import Stub


def _make_message(msg_id: str = "m-1") -> PlatformMessage:
    return PlatformMessage(
        id=msg_id,
        content="hello",
        author=AuthorInfo(id="user-1", name="User", display_name="User"),
        channel=ChannelInfo(id="chan-1"),
    )


class FakeAdapter:
    """可编程平台适配器 fake."""

    def __init__(self, bot_id: Optional[str] = "bot-1", filter_all: bool = False):
        self._bot_id = bot_id
        self.filter_all = filter_all

    def get_bot_id_from_event(self, event):
        return self._bot_id

    async def event_to_message(self, event, runtime):
        if self.filter_all:
            return None
        return _make_message("m-1")


class TestRegisterAndSubscribe:
    def test_register_adapter_and_runtime(self):
        bus = DefaultMessageBus()
        adapter = FakeAdapter()
        runtime = MockBotRuntime()
        bus.register_platform_adapter("discord", adapter)
        bus.register_bot_runtime("bot-1", runtime)
        assert bus._adapters["discord"] is adapter
        assert bus._runtimes["bot-1"] is runtime

    def test_subscribe_idempotent_and_unsubscribe(self):
        bus = DefaultMessageBus()
        calls = []

        async def handler(message, runtime):
            calls.append(message.id)

        bus.subscribe(handler)
        bus.subscribe(handler)  # 重复订阅幂等
        assert len(bus._handlers) == 1
        bus.unsubscribe(handler)
        assert bus._handlers == []
        # 未订阅的 handler 注销不报错
        bus.unsubscribe(handler)


class TestPublishEvent:
    async def test_publish_event_routes_to_handler(self):
        bus = DefaultMessageBus()
        bus.register_platform_adapter("discord", FakeAdapter(bot_id="bot-1"))
        runtime = MockBotRuntime()
        bus.register_bot_runtime("bot-1", runtime)
        received = []

        async def handler(message, rt):
            received.append((message.id, rt))

        bus.subscribe(handler)
        result = await bus.publish_event(Stub(self_id="self-1"), "discord")
        assert result is True
        assert received == [("m-1", runtime)]

    async def test_publish_event_unknown_platform_returns_false(self):
        bus = DefaultMessageBus()
        bus.register_bot_runtime("bot-1", MockBotRuntime())
        assert await bus.publish_event(Stub(self_id="self-1"), "qq") is False

    async def test_publish_event_no_bot_id_mapping_returns_false(self):
        bus = DefaultMessageBus()
        bus.register_platform_adapter("discord", FakeAdapter(bot_id=None))
        bus.register_bot_runtime("bot-1", MockBotRuntime())
        assert await bus.publish_event(Stub(self_id="self-1"), "discord") is False

    async def test_publish_event_self_filtered_returns_false(self):
        bus = DefaultMessageBus()
        bus.register_platform_adapter("discord", FakeAdapter(bot_id="bot-1", filter_all=True))
        bus.register_bot_runtime("bot-1", MockBotRuntime())
        calls = []

        async def handler(message, rt):
            calls.append(message.id)

        bus.subscribe(handler)
        assert await bus.publish_event(Stub(self_id="self-1"), "discord") is False
        assert calls == []


class TestPublishMessage:
    async def test_publish_message_dispatches_to_all_handlers(self):
        bus = DefaultMessageBus()
        received = []

        async def handler_a(message, rt):
            received.append("a")

        async def handler_b(message, rt):
            received.append("b")

        bus.subscribe(handler_a)
        bus.subscribe(handler_b)
        await bus.publish_message(_make_message("x"), MockBotRuntime())
        assert received == ["a", "b"]

    async def test_handler_exception_does_not_propagate(self):
        bus = DefaultMessageBus()
        received = []

        async def failing_handler(message, rt):
            raise RuntimeError("handler boom")

        async def ok_handler(message, rt):
            received.append("ok")

        bus.subscribe(failing_handler)
        bus.subscribe(ok_handler)
        await bus.publish_message(_make_message("x"), MockBotRuntime())  # 不抛
        assert received == ["ok"]
