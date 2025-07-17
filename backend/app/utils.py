# backend/app/utils.py

import json
from typing import List, Dict, Any, Optional

import discord
import logging
import aiohttp

logger = logging.getLogger(__name__)

def split_message(text: str, max_length: int = 2000) -> List[str]:
    """将长文本分割成符合Discord消息长度限制的多个部分。"""
    if not text:
        return []
    parts = []
    while len(text) > 0:
        if len(text) <= max_length:
            parts.append(text)
            break
        # 优先从换行符切分
        cut_index = text.rfind('\n', 0, max_length)
        # 其次从空格切分
        if cut_index == -1:
            cut_index = text.rfind(' ', 0, max_length)
        # 如果都没有，就硬切
        if cut_index == -1:
            cut_index = max_length
        parts.append(text[:cut_index].strip())
        text = text[cut_index:].strip()
    return parts

def _format_with_placeholders(template_str: str, message: discord.Message, args: str) -> str:
    """用消息上下文中的值替换模板字符串中的占位符。"""
    if not isinstance(template_str, str): return ''
    replacements = {
        "{user_input}": args,
        "{raw_content}": message.content,
        "{author_id}": str(message.author.id),
        "{author_name}": message.author.name,
        "{author_display_name}": message.author.display_name,
        "{channel_id}": str(message.channel.id),
        "{guild_id}": str(message.guild.id) if message.guild else "N/A",
    }
    for placeholder, value in replacements.items():
        template_str = template_str.replace(placeholder, value)
    return template_str

async def _execute_http_request(plugin_config: Dict[str, Any], message: discord.Message, args: str) -> Optional[str]:
    """执行HTTP请求并返回结果字符串。"""
    http_conf = plugin_config.get('http_request_config', {})
    url = _format_with_placeholders(http_conf.get('url', ''), message, args)
    method = http_conf.get('method', 'GET').upper()
    if not url:
        logger.warning(f"Plugin '{plugin_config.get('name')}' has no URL configured.")
        return None
    headers_str = _format_with_placeholders(http_conf.get('headers', '{}'), message, args)
    body_str = _format_with_placeholders(http_conf.get('body_template', '{}'), message, args)
    try:
        headers = json.loads(headers_str) if headers_str.strip() else {}
        if body_str.strip() and 'content-type' not in (h.lower() for h in headers):
            headers['Content-Type'] = 'application/json'
        async with aiohttp.ClientSession(headers=headers) as session:
            request_kwargs = {}
            if method in ['POST', 'PUT', 'PATCH']:
                try:
                    request_kwargs['json'] = json.loads(body_str)
                except json.JSONDecodeError:
                    request_kwargs['data'] = body_str
            async with session.request(method, url, **request_kwargs) as response:
                response_text = await response.text()
                if 200 <= response.status < 300:
                    logger.info(f"Plugin '{plugin_config.get('name')}' HTTP request to {url} successful.")
                    return response_text
                else:
                    logger.error(f"Plugin '{plugin_config.get('name')}' HTTP request failed with status {response.status}: {response_text}")
                    return f"Error: API call failed with status {response.status}."
    except aiohttp.ClientError as e:
        logger.error(f"Plugin '{plugin_config.get('name')}' HTTP request network error: {e}", exc_info=True)
        return f"Error: Network error during API call: {e}"
    except (json.JSONDecodeError, TypeError) as e:
         logger.error(f"Plugin '{plugin_config.get('name')}' failed to parse Headers or Body JSON: {e}", exc_info=True)
         return f"Error: Invalid JSON in plugin configuration (Headers/Body): {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred in plugin '{plugin_config.get('name')}': {e}", exc_info=True)
        return f"Error: An unexpected error occurred while running the plugin."
