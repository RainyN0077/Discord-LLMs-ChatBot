"""Mock Bot 运行时 — 用于测试和开发环境.

Mock 实现记录所有发送的消息，不连接真实平台。
"""

from typing import Any, Dict, List, Optional

from ..ports.bot_runtime import BotRuntime, BotStatus


class MockBotRuntime(BotRuntime):
    """Mock 实现: 用于单元测试和集成测试.

    记录所有发送的消息，不连接真实平台。
    """

    def __init__(self, bot_id: str = "mock_bot") -> None:
        """初始化 Mock Bot 运行时.

        Args:
            bot_id: Bot 的唯一标识符
        """
        self._bot_id = bot_id
        self._status = BotStatus.STOPPED
        self.sent_messages: List[Dict[str, Any]] = []
        self.edited_messages: List[Dict[str, Any]] = []

    # --- BotIdentity ---

    @property
    def bot_id(self) -> str:
        return self._bot_id

    @property
    def self_id(self) -> str:
        return "1234567890"

    @property
    def display_name(self) -> str:
        return "Mock Bot"

    @property
    def platform(self) -> str:
        return "mock"

    # --- MessageSender ---

    async def send_message(
        self,
        channel_id: str,
        content: str,
        reply_to_message_id: Optional[str] = None,
    ) -> Optional[str]:
        """发送消息到指定频道（Mock 实现，记录操作）.

        Args:
            channel_id: 目标频道 ID
            content: 消息内容
            reply_to_message_id: 回复的消息 ID（可选）

        Returns:
            模拟的消息 ID
        """
        msg_id = f"mock_msg_{len(self.sent_messages)}"
        self.sent_messages.append(
            {
                "channel_id": channel_id,
                "content": content,
                "reply_to": reply_to_message_id,
                "message_id": msg_id,
            }
        )
        return msg_id

    async def edit_message(
        self,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> None:
        """编辑已发送的消息（Mock 实现，记录操作）.

        Args:
            channel_id: 频道 ID
            message_id: 要编辑的消息 ID
            content: 新的消息内容
        """
        self.edited_messages.append(
            {
                "channel_id": channel_id,
                "message_id": message_id,
                "content": content,
            }
        )

    async def trigger_typing_indicator(self, channel_id: str) -> None:
        """触发输入状态指示器（Mock 实现，无操作）.

        Args:
            channel_id: 频道 ID
        """
        pass

    # --- BotRuntime ---

    async def start(self) -> None:
        """启动 Bot 运行时."""
        self._status = BotStatus.RUNNING

    async def stop(self) -> None:
        """停止 Bot 运行时."""
        self._status = BotStatus.STOPPED

    @property
    def status(self) -> BotStatus:
        return self._status

    async def health(self) -> Dict[str, Any]:
        """返回健康检查信息.

        Returns:
            包含连接状态、状态等信息的字典
        """
        return {
            "bot_id": self._bot_id,
            "status": self._status.value,
            "platform": "mock",
        }

    def get_feature(self, feature_name: str) -> bool:
        """查询运行时支持的功能（Mock 支持所有特性）.

        Args:
            feature_name: 功能名称

        Returns:
            始终返回 True
        """
        return True
