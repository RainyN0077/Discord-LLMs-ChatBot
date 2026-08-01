"""NoneBot2 运行时适配器 — 将 NoneBot2 适配为 BotRuntime 接口.

封装 NoneBot2 的 Bot 实例，提供统一的 BotRuntime 接口。
"""

import asyncio
import functools
import logging
from typing import Any, Dict, Optional

from ..ports.bot_runtime import BotRuntime, BotStatus
from ..utils import log_task_exception

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
        self._reconnect_task: Optional[asyncio.Task] = None
        self._reconnect_attempt = 0
        self._MAX_RECONNECT_ATTEMPTS = 10

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
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        self._reconnect_task.add_done_callback(
            functools.partial(log_task_exception, label="NoneBot reconnect loop")
        )
        logger.info("NoneBotRuntime '%s' started with reconnect loop", self._bot_id)

    async def stop(self) -> None:
        """停止 Bot 运行时."""
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        # 清理 self_id → bot_id 映射
        if self._bot is not None:
            from .discord_platform_adapter import DiscordPlatformAdapter
            DiscordPlatformAdapter.unregister_self_id_mapping(
                str(self._bot.self_id)
            )
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
        自动注册 self_id → bot_id 映射，使 MessageBus 能通过事件找到 Bot。

        Args:
            bot: NoneBot2 Bot 实例
        """
        self._bot = bot
        # P0-1: 注册 self_id → bot_id 映射，确保 MessageBus 可以路由事件
        from .discord_platform_adapter import DiscordPlatformAdapter
        DiscordPlatformAdapter.register_self_id_mapping(
            str(bot.self_id), self._bot_id
        )

    # --- Reconnection Logic ---

    async def _reconnect_loop(self) -> None:
        """重连主循环：主动检测 websocket 连接状态并在断开时触发重连.

        关键修复（P0-3 + P0-5）：
        - 主动健康检查，检查 ``_ws`` 状态
        - 不再依赖 ``asyncio.sleep`` 异常
        """
        while self._status == BotStatus.RUNNING and self._reconnect_attempt < self._MAX_RECONNECT_ATTEMPTS:
            try:
                await asyncio.sleep(5)

                # 主动健康检查（P0-5 修复：不再依赖 sleep 异常）
                if self._bot is not None:
                    ws = getattr(self._bot, '_ws', None)
                    if ws is None or getattr(ws, 'closed', False):
                        self._reconnect_attempt += 1
                        logger.warning(
                            "Bot '%s' connection lost (attempt %d/%d)",
                            self._bot_id, self._reconnect_attempt, self._MAX_RECONNECT_ATTEMPTS,
                        )
                        await self._reconnect(self._reconnect_attempt)
                        continue

                # 连接正常，重置计数
                if self._reconnect_attempt > 0:
                    logger.info("Bot '%s' connection restored", self._bot_id)
                    self._reconnect_attempt = 0

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._reconnect_attempt += 1
                logger.error(
                    "Bot '%s' reconnect error (attempt %d/%d): %s",
                    self._bot_id, self._reconnect_attempt, self._MAX_RECONNECT_ATTEMPTS, exc,
                )
                await self._reconnect(self._reconnect_attempt)

        if self._reconnect_attempt >= self._MAX_RECONNECT_ATTEMPTS and self._status == BotStatus.RUNNING:
            logger.error(
                "Bot '%s' exceeded max reconnect attempts (%d)",
                self._bot_id, self._MAX_RECONNECT_ATTEMPTS,
            )
            self._status = BotStatus.STOPPED

    async def _reconnect(self, attempt: int) -> None:
        """单次重连，指数退避.

        退避序列: 1s, 2s, 4s, 8s, ... 上限 60s.
        仅在 ``status == RUNNING`` 时执行。

        Args:
            attempt: 当前重连尝试次数（1-based）
        """
        if self._status != BotStatus.RUNNING:
            return

        delay = min(1.0 * (2 ** (attempt - 1)), 60.0)
        logger.warning(
            "Bot '%s' reconnecting in %.1fs (attempt %d)",
            self._bot_id, delay, attempt,
        )
        await asyncio.sleep(delay)

        if self._status != BotStatus.RUNNING:
            return

        try:
            from nb_plugins.core_llm_bot.matchers import (
                register_bot_instance,
                unregister_bot_instance,
            )
            unregister_bot_instance(self.bot_id)
            register_bot_instance(self.bot_id, self)
            logger.info(
                "Bot '%s' re-registered with NoneBot adapter (attempt %d)",
                self._bot_id, attempt,
            )
        except Exception as e:
            logger.error("Bot '%s' reconnect failed: %s", self._bot_id, e)
            # P1-B: 不重新抛出异常避免 _reconnect_loop 中重复递增计数
