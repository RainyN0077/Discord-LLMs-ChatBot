"""Mock 平台适配器 — 用于测试."""

from typing import Any, Dict, Optional

from ..ports.platform_adapter import PlatformAdapter
from ..ports.platform_message import (
    AuthorInfo,
    ChannelInfo,
    GuildInfo,
    PlatformMessage,
)
from ..ports.bot_runtime import BotRuntime


class MockPlatformAdapter(PlatformAdapter):
    """Mock 实现: 用于单元测试."""

    def __init__(self) -> None:
        """初始化 Mock 适配器."""
        self.converted_events: list = []

    async def event_to_message(
        self,
        event: Any,
        runtime: BotRuntime,
    ) -> Optional[PlatformMessage]:
        """将 Mock 事件转换为平台无关消息.

        Args:
            event: Mock 事件对象（可具有 content, author_id 等属性）
            runtime: Bot 运行时实例

        Returns:
            转换后的 PlatformMessage，或 None 如果事件不包含内容
        """
        if hasattr(event, "content"):
            msg = PlatformMessage(
                id=str(getattr(event, "id", "mock_1")),
                content=str(event.content),
                author=AuthorInfo(
                    id=str(getattr(event, "author_id", "12345")),
                    name=getattr(event, "author_name", "MockUser"),
                    display_name=getattr(event, "author_display_name", "MockUser"),
                ),
                channel=ChannelInfo(id=str(getattr(event, "channel_id", "1"))),
                guild=GuildInfo(id=str(getattr(event, "guild_id", "1"))),
            )
            self.converted_events.append(msg)
            return msg
        return None

    def get_platform_name(self) -> str:
        """返回平台名称.

        Returns:
            "mock"
        """
        return "mock"

    def get_bot_id_from_event(self, event: Any) -> Optional[str]:
        """从事件中提取 Bot ID.

        Args:
            event: Mock 事件对象

        Returns:
            Bot ID 或 None
        """
        return getattr(event, "bot_id", None)

    def is_triggered(
        self, message: PlatformMessage, config: Dict[str, Any]
    ) -> bool:
        """判断是否应对此消息做出响应（Mock 始终触发）.

        Args:
            message: 平台无关消息
            config: Bot 配置

        Returns:
            始终返回 True
        """
        return True
