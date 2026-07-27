"""平台无关的配额管理器 — 从 usage_manager.py 提取，移除 discord 依赖.

管理用户的消息数和 Token 数配额，支持基于角色的配额控制和自动重置。
"""

import asyncio
import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class QuotaManager:
    """平台无关的配额管理器.

    管理用户的消息数和 Token 数配额。
    线程安全，支持每个用户的独立锁和自动重置周期。
    """

    def __init__(self) -> None:
        """初始化配额管理器."""
        self._usage: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._guard = threading.Lock()

    def _get_lock(self, user_key: str) -> asyncio.Lock:
        """获取用户级别的异步锁.

        Args:
            user_key: 用户唯一标识

        Returns:
            用户的异步锁实例
        """
        with self._guard:
            if user_key not in self._locks:
                self._locks[user_key] = asyncio.Lock()
            return self._locks[user_key]

    async def check_and_update(
        self,
        user_id: str,
        role_config: Dict[str, Any],
        estimated_input_tokens: int,
        output_tokens: int,
    ) -> Optional[str]:
        """检查配额并更新用量。

        如果超额返回错误消息，否则返回 None。

        Args:
            user_id: 用户 ID
            role_config: 角色配置（包含配额限制）
            estimated_input_tokens: 预估的输入 Token 数
            output_tokens: 实际输出 Token 数

        Returns:
            超额时的错误消息，或 None 表示配额充足
        """
        async with self._get_lock(user_id):
            now = time.monotonic()
            usage = self._usage.get(user_id)

            if not usage:
                usage = {"messages": 0, "tokens": 0, "reset_at": now}
                self._usage[user_id] = usage

            # 自动重置周期
            if role_config.get("enable_message_limit"):
                refresh = (
                    role_config.get("message_refresh_minutes", 60) * 60
                )
                if now - usage.get("reset_at", now) > refresh:
                    usage["messages"] = 0
                    usage["tokens"] = 0
                    usage["reset_at"] = now

            # 消息数配额检查
            msg_limit = role_config.get("message_limit", 0)
            if role_config.get("enable_message_limit") and msg_limit > 0:
                if usage["messages"] + 1 > msg_limit:
                    return f"消息配额 ({msg_limit}) 已用完"

            # Token 配额检查
            token_limit = (
                role_config.get("char_limit", 0)
                or role_config.get("token_limit", 0)
            )
            output_budget = (
                role_config.get("char_output_budget", 300)
                or role_config.get("token_output_budget", 300)
            )
            if role_config.get("enable_char_limit") and token_limit > 0:
                if (
                    usage["tokens"]
                    + estimated_input_tokens
                    + output_budget
                    > token_limit
                ):
                    return f"Token 配额 ({token_limit}) 不足"

            # 更新用量
            usage["messages"] += 1
            usage["tokens"] += estimated_input_tokens + output_tokens
            return None
