"""平台适配器接口 — 定义平台原生消息到 PlatformMessage 的转换契约.

每个平台（Discord、QQ、Web、Mock）实现此接口。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .platform_message import PlatformMessage
from .bot_runtime import BotRuntime


class PlatformAdapter(ABC):
    """平台适配器 — 将平台原生消息转换为 PlatformMessage.

    每个平台（Discord、QQ、Web、Mock）实现此接口。
    """

    @abstractmethod
    async def event_to_message(
        self,
        event: Any,
        runtime: BotRuntime,
    ) -> Optional[PlatformMessage]:
        """将平台原生事件转换为平台无关消息.

        Args:
            event: 平台原生事件对象
            runtime: Bot 运行时实例

        Returns:
            转换后的 PlatformMessage，返回 None 表示事件不应被处理
        """
        ...

    @abstractmethod
    def get_platform_name(self) -> str:
        """返回平台名称 ('discord', 'qq', 'mock')."""
        ...

    @abstractmethod
    def get_bot_id_from_event(self, event: Any) -> Optional[str]:
        """从事件中提取 Bot ID，用于路由到正确的 BotInstance."""
        ...

    @abstractmethod
    def is_triggered(self, message: PlatformMessage, config: Dict[str, Any]) -> bool:
        """判断是否应对此消息做出响应.

        Args:
            message: 平台无关消息
            config: Bot 配置

        Returns:
            是否触发响应
        """
        ...
