"""Bot 运行时抽象接口 — 定义 BotRuntime Port.

所有具体 Bot 运行时适配器（NoneBot、Mock）必须实现此接口。
这是六边形架构中的核心 Port，业务代码只依赖此接口。
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional


class BotStatus(str, Enum):
    """Bot 运行时状态枚举."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


class BotIdentity(ABC):
    """Bot 身份信息接口.

    提供 Bot 的基本身份信息，不依赖具体平台实现。
    """

    @property
    @abstractmethod
    def bot_id(self) -> str:
        """Bot 的唯一标识符."""
        ...

    @property
    @abstractmethod
    def self_id(self) -> str:
        """平台上的 Bot 自身 User ID."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Bot 的显示名称."""
        ...

    @property
    @abstractmethod
    def platform(self) -> str:
        """Bot 所属平台 ('discord', 'qq', 'mock')."""
        ...


class MessageSender(ABC):
    """消息发送接口 — 平台无关的发信能力.

    所有平台适配器必须实现此接口，提供统一的消息发送能力。
    """

    @abstractmethod
    async def send_message(
        self,
        channel_id: str,
        content: str,
        reply_to_message_id: Optional[str] = None,
    ) -> Optional[str]:
        """发送消息到指定频道.

        Args:
            channel_id: 目标频道 ID
            content: 消息内容
            reply_to_message_id: 回复的消息 ID（可选）

        Returns:
            发送的消息 ID（如果平台支持），否则 None
        """
        ...

    @abstractmethod
    async def edit_message(
        self,
        channel_id: str,
        message_id: str,
        content: str,
    ) -> None:
        """编辑已发送的消息.

        Args:
            channel_id: 频道 ID
            message_id: 要编辑的消息 ID
            content: 新的消息内容
        """
        ...

    @abstractmethod
    async def trigger_typing_indicator(self, channel_id: str) -> None:
        """触发输入状态指示器.

        Args:
            channel_id: 频道 ID
        """
        ...


class BotRuntime(BotIdentity, MessageSender, ABC):
    """Bot 运行时抽象 — 统一管理 Bot 生命周期和消息发送.

    所有具体 Bot 运行时适配器（NoneBot、Mock）必须实现此接口。
    这是六边形架构中的核心 Port，业务代码只依赖此接口。
    """

    @abstractmethod
    async def start(self) -> None:
        """启动 Bot 运行时，连接到平台."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """停止 Bot 运行时，断开连接并清理资源."""
        ...

    @property
    @abstractmethod
    def status(self) -> BotStatus:
        """返回当前运行时状态."""
        ...

    @abstractmethod
    async def health(self) -> Dict[str, Any]:
        """返回健康检查信息.

        Returns:
            包含连接状态、延迟等信息的字典
        """
        ...

    @abstractmethod
    def get_feature(self, feature_name: str) -> bool:
        """查询运行时支持的功能.

        Args:
            feature_name: 功能名称，如 'edit_message', 'typing_indicator'

        Returns:
            是否支持该功能
        """
        ...
