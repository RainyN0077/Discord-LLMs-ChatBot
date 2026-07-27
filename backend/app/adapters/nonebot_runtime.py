"""NoneBot2 运行时适配器 — 将 NoneBot2 适配为 BotRuntime 接口.

封装 NoneBot2 的 Bot 实例，提供统一的 BotRuntime 接口。
"""

import logging
from typing import Any, Dict, Optional

from ..ports.bot_runtime import BotRuntime, BotStatus

logger = logging.getLogger(__name__)


class NoneBotRuntime(BotRuntime):
    """适配器: 将 NoneBot2 Discord Bot 适配为 BotRuntime.

    封装 NoneBot2 的 Bot 实例，提供统一的 BotRuntime 接口。
    """

    def __init__(self, bot_id: str, config: Dict[str, Any]) -> None:
        """初始化 NoneBot 运行时适配器.

        Args:
            bot_id: Bot 的唯一标识符
            config: Bot 配置字典
        """
        self._bot_id = bot_id
        self._config = config
        self._bot: Optional[Any] = None
        self._status = BotStatus.STOPPED

    # --- BotIdentity ---

    @property
    def bot_id(self) -> str:
        return self._bot_id

    @property
    def self_id(self) -> str:
        if self._bot is not None:
            return str(getattr(self._bot, "self_id", ""))
        return ""

    @property
    def display_name(self) -> str:
        return self._config.get("bot_name", "Unnamed Bot")

    @property
    def platform(self) -> str:
        return self._config.get("platform", "discord")

    # --- MessageSender ---

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

        Raises:
            RuntimeError: Bot 未运行时
        """
        if self._bot is None:
            raise RuntimeError("Bot not running")
        msg = await self._bot.send_to(
            channel_id=int(channel_id),
            message=content,
        )
        return str(getattr(msg, "id", "")) if msg else None

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

        Raises:
            RuntimeError: Bot 未运行时
        """
        if self._bot is None:
            raise RuntimeError("Bot not running")
        await self._bot.edit_message(
            channel_id=int(channel_id),
            message_id=int(message_id),
            content=content,
        )

    async def trigger_typing_indicator(self, channel_id: str) -> None:
        """触发输入状态指示器.

        Args:
            channel_id: 频道 ID
        """
        if self._bot is None:
            return
        try:
            await self._bot.trigger_typing_indicator(channel_id=int(channel_id))
        except Exception:
            logger.debug("Typing indicator failed for channel %s (non-critical)", channel_id)

    # --- BotRuntime ---

    async def start(self) -> None:
        """启动 Bot 运行时."""
        self._status = BotStatus.RUNNING
        logger.info("NoneBotRuntime '%s' started", self._bot_id)

    async def stop(self) -> None:
        """停止 Bot 运行时."""
        self._bot = None
        self._status = BotStatus.STOPPED
        logger.info("NoneBotRuntime '%s' stopped", self._bot_id)

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
            "platform": self.platform,
            "connected": self._bot is not None,
        }

    def get_feature(self, feature_name: str) -> bool:
        """查询运行时支持的功能.

        Args:
            feature_name: 功能名称

        Returns:
            是否支持该功能
        """
        features: Dict[str, bool] = {
            "edit_message": True,
            "typing_indicator": True,
            "send_message": True,
            "send_reply": True,
        }
        return features.get(feature_name, False)

    def attach_bot(self, bot: Any) -> None:
        """注入 NoneBot2 Bot 实例.

        由 matchers 在事件触发时传入。

        Args:
            bot: NoneBot2 Bot 实例
        """
        self._bot = bot
