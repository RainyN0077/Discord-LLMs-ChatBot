"""消息总线抽象接口 — 解耦事件源与消息处理器.

职责:
1. 注册 PlatformAdapter 实例，用于转换平台原生事件
2. 注册 BotRuntime 实例，用于消息发送能力
3. 将 PlatformMessage 分发给注册的处理器
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine, Dict, List, Optional

from .bot_runtime import BotRuntime
from .platform_message import PlatformMessage

# 消息处理器类型签名
MessageHandler = Callable[
    [PlatformMessage, BotRuntime],
    Coroutine[Any, Any, None],
]


class MessageBus(ABC):
    """消息总线 — 解耦事件源与消息处理器."""

    @abstractmethod
    def register_platform_adapter(
        self, platform: str, adapter: "PlatformAdapter"
    ) -> None:
        """注册平台适配器.

        Args:
            platform: 平台名称（如 "discord"）
            adapter: PlatformAdapter 实例
        """
        ...

    @abstractmethod
    def register_bot_runtime(self, bot_id: str, runtime: BotRuntime) -> None:
        """注册 BotRuntime 实例.

        Args:
            bot_id: Bot 唯一标识符
            runtime: BotRuntime 实例
        """
        ...

    @abstractmethod
    def subscribe(self, handler: MessageHandler) -> None:
        """订阅消息处理器.

        Args:
            handler: 消息处理器 callable
        """
        ...

    @abstractmethod
    def unsubscribe(self, handler: MessageHandler) -> None:
        """取消订阅消息处理器.

        Args:
            handler: 已注册的处理器 callable
        """
        ...

    @abstractmethod
    async def publish_event(self, event: Any, platform: str) -> bool:
        """发布平台原生事件.

        内部流程:
        1. 根据 platform 查找 PlatformAdapter
        2. 调用 adapter.event_to_message(event, runtime) -> PlatformMessage
        3. 将 PlatformMessage 分发给所有订阅者

        Args:
            event: 平台原生事件对象
            platform: 平台名称

        Returns:
            是否成功派发消息
        """
        ...

    @abstractmethod
    async def publish_message(
        self, message: PlatformMessage, runtime: BotRuntime
    ) -> None:
        """直接发布 PlatformMessage.

        Args:
            message: 平台无关消息对象
            runtime: 关联的 BotRuntime 实例
        """
        ...
