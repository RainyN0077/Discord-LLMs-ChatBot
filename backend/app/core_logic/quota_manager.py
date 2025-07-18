# backend/app/core_logic/quota_manager.py
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import discord
import json

from ..utils import TokenCalculator

logger = logging.getLogger(__name__)

def check_and_reset_quota(user_id: int, role_config: Dict[str, Any], usage_tracker: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    """检查并重置用户的配额。返回更新后的用户用量数据。"""
    now = datetime.now(timezone.utc)
    usage = usage_tracker.get(user_id, {"count": 0, "chars": 0, "timestamp": now})
    
    enabled_refreshes = []
    if role_config.get('enable_message_limit'):
        enabled_refreshes.append(role_config.get('message_refresh_minutes', 60))
    if role_config.get('enable_char_limit'):
        enabled_refreshes.append(role_config.get('char_refresh_minutes', 60))
        
    shortest_refresh = min(enabled_refreshes) if enabled_refreshes else -1
    
    if shortest_refresh > 0 and now - usage.get('timestamp', now) > timedelta(minutes=shortest_refresh):
        usage = {"count": 0, "chars": 0, "timestamp": now}
        usage_tracker[user_id] = usage
        logger.info(f"Usage quota for user {user_id} has been reset.")
        
    return usage

async def check_pre_request_quota(message: discord.Message, role_config: Dict[str, Any], usage: Dict[str, Any], token_calculator: TokenCalculator, bot_config: dict, system_prompt: str, history_for_llm: list, final_formatted_content: str) -> Optional[str]:
    """在发送LLM请求前检查配额。如果超额，返回错误消息字符串。"""
    # 检查消息数限制
    if role_config.get('enable_message_limit') and (usage['count'] + 1) > role_config.get('message_limit', 0):
        return f"Sorry, your message quota ({role_config.get('message_limit', 0)} messages) would be exceeded. Please try again later."
    
    # 检查Token数限制
    if role_config.get('enable_char_limit'):
        token_limit = role_config.get('char_limit', 0)
        budget = role_config.get('char_output_budget', 500)
        
        provider = bot_config.get("llm_provider")
        model = bot_config.get("model_name")
        
        history_text_for_calc = json.dumps(history_for_llm)
        pre_estimated_tokens = token_calculator.get_token_count(system_prompt + history_text_for_calc + final_formatted_content, provider, model) + budget
        
        if (usage['chars'] + pre_estimated_tokens) > token_limit:
            return f"Sorry, this request (estimated tokens: {pre_estimated_tokens}) would exceed your remaining token quota ({token_limit - usage['chars']}). Please try a shorter message or wait for the quota to reset."
    
    return None

def update_post_request_usage(user_id: int, usage_tracker: Dict[int, Dict[str, Any]], token_calculator: TokenCalculator, bot_config: dict, system_prompt: str, history_for_llm: list, final_formatted_content: str, full_response: str) -> None:
    """在LLM响应后，精确更新用户的用量。"""
    usage = usage_tracker.setdefault(user_id, {"count": 0, "chars": 0, "timestamp": datetime.now(timezone.utc)})
    usage['count'] += 1
    
    provider = bot_config.get("llm_provider")
    model = bot_config.get("model_name")
    
    history_text_for_calc = json.dumps(history_for_llm)
    input_tokens = token_calculator.get_token_count(system_prompt + history_text_for_calc + final_formatted_content, provider, model)
    output_tokens = token_calculator.get_token_count(full_response, provider, model)
    total_tokens = input_tokens + output_tokens
    
    usage['chars'] += total_tokens
    logger.info(f"User {user_id} usage updated: +1 msg, +{total_tokens} tokens. New total: {usage['count']} msgs, {usage['chars']} tokens.")
