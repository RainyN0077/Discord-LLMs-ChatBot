"""默认消息总线实现."""

import logging
from typing import Any, Dict, List, Optional

from ..ports.bot_runtime import BotRuntime
from ..ports.message_bus import MessageBus, MessageHandler
from ..ports.platform_message import PlatformMessage

logger = logging.getLogger(__name__)


class DefaultMessageBus(MessageBus):
    """默认消息总线实现."""

    def __init__(self) -> None:
        self._adapters: Dict[str, Any] = {}
        self._runtimes: Dict[str, BotRuntime] = {}
        self._handlers: List[MessageHandler] = []

    def register_platform_adapter(self, platform: str, adapter: Any) -> None:
        """注册平台适配器."""
        self._adapters[platform] = adapter
        logger.info("Platform adapter registered for '%s'", platform)

    def register_bot_runtime(self, bot_id: str, runtime: BotRuntime) -> None:
        """注册 BotRuntime 实例."""
        self._runtimes[bot_id] = runtime
        logger.info("BotRuntime registered for bot '%s'", bot_id)

    def subscribe(self, handler: MessageHandler) -> None:
        """订阅消息处理器."""
        if handler not in self._handlers:
            self._handlers.append(handler)

    def unsubscribe(self, handler: MessageHandler) -> None:
        """取消订阅消息处理器."""
        self._handlers = [h for h in self._handlers if h is not handler]

    async def publish_event(self, event: Any, platform: str) -> bool:
        """发布平台原生事件.

        Returns:
            是否成功派发消息
        """
        from ..ports.platform_adapter import PlatformAdapter

        adapter = self._adapters.get(platform)
        if adapter is None:
            logger.warning("No adapter registered for platform '%s'", platform)
            return False

        bot_id = adapter.get_bot_id_from_event(event)
        if bot_id is None:
            logger.debug("Could not extract bot_id from event, skipping")
            return False

        runtime = self._runtimes.get(bot_id)
        if runtime is None:
            logger.warning("No runtime registered for bot '%s'", bot_id)
            return False

        message = await adapter.event_to_message(event, runtime)
        if message is None:
            return False  # event filtered by adapter (e.g. self-filter)

        await self.publish_message(message, runtime)
        return True

    async def publish_message(self, message: PlatformMessage, runtime: BotRuntime) -> None:
        """直接发布 PlatformMessage."""
        for handler in self._handlers:
            try:
                await handler(message, runtime)
            except Exception:
                logger.exception("Handler failed for message %s", message.id)
