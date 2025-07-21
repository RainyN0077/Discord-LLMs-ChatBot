# backend/app/core_logic/usage_manager.py
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

import discord

from ..utils import TokenCalculator

logger = logging.getLogger(__name__)

class UsageManager:
    """
    一个线程安全的类，用于管理用户用量和配额。
    它封装了所有与配额相关的逻辑，并使用锁来防止并发访问下的竞态条件。
    """
    def __init__(self, token_calculator: TokenCalculator):
        self._usage_tracker: Dict[int, Dict[str, Any]] = {}
        self._user_locks = defaultdict(asyncio.Lock)
        self._token_calculator = token_calculator

    def _get_initial_usage_data(self) -> Dict[str, Any]:
        """返回一个初始化的用户用量字典。"""
        return {
            "message_count": 0,
            "total_tokens": 0,
            "timestamp": datetime.now(timezone.utc)
        }

    def _should_reset_quota(self, usage_data: Dict[str, Any], role_config: Dict[str, Any]) -> bool:
        """根据角色配置和上次使用时间，判断是否应该重置配额。"""
        now = datetime.now(timezone.utc)
        last_timestamp = usage_data.get("timestamp", now)
        
        # 兼容旧的'chars'命名
        if 'chars' in usage_data and 'total_tokens' not in usage_data:
            usage_data['total_tokens'] = usage_data['chars']

        # 检查消息数刷新周期
        if role_config.get('enable_message_limit'):
            refresh_minutes = role_config.get('message_refresh_minutes', 60)
            if now - last_timestamp > timedelta(minutes=refresh_minutes):
                return True
        
        # 检查Token数刷新周期 (旧称char_limit)
        if role_config.get('enable_char_limit'):
            refresh_minutes = role_config.get('char_refresh_minutes', 60)
            if now - last_timestamp > timedelta(minutes=refresh_minutes):
                return True
                
        return False

    async def check_quota_and_get_usage(self, user_id: int, role_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取用户的当前用量数据。如果需要，会自动重置配额。
        这是一个原子操作。
        """
        async with self._user_locks[user_id]:
            current_usage = self._usage_tracker.get(user_id)
            
            if not current_usage:
                current_usage = self._get_initial_usage_data()
                self._usage_tracker[user_id] = current_usage
                return current_usage

            if self._should_reset_quota(current_usage, role_config):
                logger.info(f"Usage quota for user {user_id} has been reset.")
                current_usage = self._get_initial_usage_data()
                self._usage_tracker[user_id] = current_usage
            
            return current_usage.copy() # 返回副本以防止外部修改

    async def check_pre_request_quota(self, user_id: int, role_config: Dict[str, Any], current_usage: Dict[str, Any], estimated_input_tokens: int) -> Optional[str]:
        """
        在发送LLM请求前检查配额。如果超额，返回错误消息字符串。
        """
        # 检查消息数限制
        if role_config.get('enable_message_limit'):
            limit = role_config.get('message_limit', 0)
            if (current_usage.get('message_count', 0) + 1) > limit:
                return f"Sorry, your message quota ({limit} messages) would be exceeded. Please try again later."

        # 检查Token数限制 (旧称char_limit)
        if role_config.get('enable_char_limit'):
            token_limit = role_config.get('char_limit', 0)
            # 预算一些输出token，以防止请求因微小超出而被拒绝
            output_budget = role_config.get('char_output_budget', 500)
            
            # 兼容旧的'chars'命名
            tokens_used = current_usage.get('total_tokens') or current_usage.get('chars', 0)
            
            if (tokens_used + estimated_input_tokens + output_budget) > token_limit:
                remaining_quota = token_limit - tokens_used
                return f"Sorry, this request (estimated tokens: {estimated_input_tokens + output_budget}) would exceed your remaining token quota ({remaining_quota}). Please try a shorter message or wait for the quota to reset."

        return None

    async def update_post_request_usage(self, user_id: int, input_tokens: int, output_tokens: int) -> None:
        """
        在LLM响应后，精确更新用户的用量。这是一个原子操作。
        """
        async with self._user_locks[user_id]:
            usage = self._usage_tracker.get(user_id)
            if not usage:
                 # 如果用量数据不存在，可能是因为机器人重启了。创建一个新的。
                usage = self._get_initial_usage_data()
                self._usage_tracker[user_id] = usage

            usage['message_count'] += 1
            
            # 兼容旧的'chars'命名
            if 'chars' in usage and 'total_tokens' not in usage:
                usage['total_tokens'] = usage.get('chars', 0)

            usage['total_tokens'] += input_tokens + output_tokens
            # 更新时间戳以用于刷新逻辑
            usage['timestamp'] = datetime.now(timezone.utc)
            
            logger.info(
                f"User {user_id} usage updated: +1 msg, +{input_tokens + output_tokens} tokens. "
                f"New total: {usage['message_count']} msgs, {usage['total_tokens']} tokens."
            )