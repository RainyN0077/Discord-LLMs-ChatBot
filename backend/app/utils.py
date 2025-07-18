# backend/app/utils.py
import json
import logging
import os
import asyncio
from typing import List, Dict, Any, Optional

import discord
import aiohttp
import tiktoken
import anthropic
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)

# --- 日志系统设置 ---
def setup_logging():
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()
    
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(log_formatter)
    logger.addHandler(stream_handler)
    
    if not os.path.exists('logs'):
        os.makedirs('logs')
    file_handler = RotatingFileHandler('logs/bot.log', maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)
    
# --- Token 计算器 ---
class TokenCalculator:
    def __init__(self):
        self._openai_cache = {}
        try:
            self._anthropic_client = anthropic.Anthropic()
        except Exception as e:
            logger.warning(f"Could not initialize Anthropic client for token counting: {e}")
            self._anthropic_client = None

    def _get_openai_tokenizer(self, model_name: str):
        if model_name in self._openai_cache: return self._openai_cache[model_name]
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            logger.warning(f"Model '{model_name}' not found for tokenization. Falling back to 'cl100k_base'.")
            encoding = tiktoken.get_encoding("cl100k_base")
        self._openai_cache[model_name] = encoding
        return encoding

    def get_token_count(self, text: str, provider: str, model: str) -> int:
        if not text: return 0
        try:
            if provider == "openai": return len(self._get_openai_tokenizer(model).encode(text))
            elif provider == "anthropic" and self._anthropic_client: return self._anthropic_client.count_tokens(text)
            elif provider == "google": return max(1, int(len(text) / 3.5)) 
            else: return len(text)
        except Exception as e:
            logger.warning(f"Token calculation failed for provider {provider}: {e}. Falling back to len().")
            return len(text)

# --- 消息工具 ---
def split_message(text: str, max_length: int = 2000) -> List[str]:
    if not text:
        return []
    parts = []
    while len(text) > 0:
        if len(text) <= max_length:
            parts.append(text)
            break
        cut_index = text.rfind('\n', 0, max_length)
        if cut_index == -1:
            cut_index = text.rfind(' ', 0, max_length)
        if cut_index == -1:
            cut_index = max_length
        parts.append(text[:cut_index].strip())
        text = text[cut_index:].strip()
    return parts

def escape_content(text: str) -> str:
    return text.replace('[', '&#91;').replace(']', '&#93;')

async def download_image(url: str) -> bytes | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200: return await resp.read()
    except Exception as e:
        logger.warning(f"Error downloading image from {url}", exc_info=True)
    return None

# --- 插件 HTTP 请求工具 ---
def _format_with_placeholders(template_str: str, message: discord.Message, args: str) -> str:
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
