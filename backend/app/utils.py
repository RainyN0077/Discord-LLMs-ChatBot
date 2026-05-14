# backend/app/utils.py
import json
import logging
import os
import asyncio
import ipaddress
import socket
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional, Tuple, Callable, Awaitable
import re
from datetime import datetime
from xml.sax.saxutils import escape as _xml_escape
import pytz # Timezone library

import discord
import aiohttp

class Stub:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def _async_stub(return_value: Any = None) -> Callable[..., Awaitable[Any]]:
    async def _fn(*args: Any, **kwargs: Any) -> Any:
        return return_value
    return _fn

def _safe_text(value) -> str:
    text = str(value or "")
    return text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")

def _json_safe(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value if not isinstance(value, str) else _safe_text(value)
    if isinstance(value, dict):
        return {_safe_text(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return _safe_text(value)

def _safe_str_list(value) -> list:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [_safe_text(item) for item in value]

def _safe_dict_list(value) -> list:
    if not isinstance(value, (list, tuple, set)):
        return []
    safe_items = []
    for item in value:
        sanitized = _json_safe(item)
        if isinstance(sanitized, dict):
            safe_items.append(sanitized)
        else:
            safe_items.append({"_value": sanitized})
    return safe_items
import tiktoken
import anthropic
from logging.handlers import RotatingFileHandler
from pathlib import Path

logger = logging.getLogger(__name__)

# --- 日志系统设置 (最终优化版) ---
import time
def setup_logging():
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    log_formatter = logging.Formatter(
        fmt='%(asctime)s.%(msecs)03dZ [%(name)-18s] - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )
    log_formatter.converter = time.gmtime

    root_logger.setLevel(logging.INFO)
    
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(log_formatter)
    root_logger.addHandler(stream_handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(logging.INFO)
    
    try:
        data_dir = Path.cwd() / 'data'
        log_dir = data_dir / 'logs'
        log_dir.mkdir(exist_ok=True, parents=True)
        log_file = log_dir / 'bot.log'

        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=5*1024*1024,
            backupCount=5, 
            encoding='utf-8'
        )
        file_handler.setFormatter(log_formatter)
        root_logger.addHandler(file_handler)
        
        root_logger.info(f"File logging configured successfully to: {log_file}")
        
    except (PermissionError, IOError) as e:
        root_logger.error(f"FATAL: Could not configure file logging due to a permission or I/O error: {e}", exc_info=True)
    except Exception as e:
        root_logger.error(f"FATAL: An unexpected error occurred during file logging setup: {e}", exc_info=True)

    noisy_loggers = {
        "httpx": logging.WARNING,
        "httpcore": logging.WARNING,
        "discord.client": logging.WARNING,
        "discord.gateway": logging.WARNING,
        "discord.http": logging.WARNING,
        "discord.state": logging.WARNING,
        "urllib3": logging.WARNING,
        "asyncio": logging.WARNING,
    }
    for name, level in noisy_loggers.items():
        logging.getLogger(name).setLevel(level)

    os.environ.setdefault("LOGURU_LEVEL", "WARNING")
    os.environ.setdefault("LOGURU_AUTOINIT", "0")


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

    def get_token_count_for_messages(self, messages: List[Dict[str, Any]], provider: str, model: str) -> int:
        """
        Calculates token count for a list of messages, providing a more accurate estimate.
        """
        if not messages:
            return 0
            
        total_tokens = 0
        try:
            if provider in {"openai", "grok"}:
                tokenizer = self._get_openai_tokenizer(model)
                for message in messages:
                    # Based on OpenAI's cookbook for token counting
                    total_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
                    for key, value in message.items():
                        if value:
                           total_tokens += len(tokenizer.encode(str(value)))
                        if key == "name":  # if there's a name, the role is omitted
                            total_tokens -= 1  # role is always required and always 1 token
                total_tokens += 2 # every reply is primed with <im_start>assistant
                return total_tokens
            
            # For other providers, we'll concatenate content and count. This is less accurate but better than json.dumps.
            full_text = "".join([str(m.get("content", "")) for m in messages])
            
            if provider == "anthropic" and self._anthropic_client:
                return self._anthropic_client.count_tokens(full_text)
            elif provider == "google":
                return max(1, int(len(full_text) / 3.5))
            else:
                encoding = tiktoken.get_encoding("cl100k_base")
                return len(encoding.encode(full_text))
                
        except Exception as e:
            logger.warning(f"Token calculation for messages failed for provider {provider}: {e}. Falling back to len().")
            fallback_text = "".join([str(m.get("content", "")) for m in messages])
            return len(fallback_text)
            
    def get_token_count(self, text: str, provider: str, model: str) -> int:
        # This function remains for simple text, like counting the final response.
        if not text: return 0
        try:
            if provider in {"openai", "grok"}: return len(self._get_openai_tokenizer(model).encode(text))
            elif provider == "anthropic" and self._anthropic_client:
                return self._anthropic_client.count_tokens(text)
            elif provider == "google":
                return max(1, int(len(text) / 3.5))
            elif provider == "anthropic":
                encoding = tiktoken.get_encoding("cl100k_base")
                return len(encoding.encode(text))
            else:
                encoding = tiktoken.get_encoding("cl100k_base")
                return len(encoding.encode(text))
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


def matches_trigger_keywords(
    message_content: str,
    trigger_keywords: List[str],
    match_mode: str = "contains",
    case_sensitive: bool = False,
) -> bool:
    """
    Returns whether the message content matches any configured trigger keyword.
    Supported modes: contains, starts_with, exact, regex.
    """
    if not message_content or not trigger_keywords:
        return False

    mode = (match_mode or "contains").strip().lower()
    content = message_content if case_sensitive else message_content.lower()

    for keyword in trigger_keywords:
        if not keyword:
            continue
        kw = str(keyword).strip()
        if not kw:
            continue

        kw_for_match = kw if case_sensitive else kw.lower()

        if mode == "starts_with":
            if content.startswith(kw_for_match):
                return True
        elif mode == "exact":
            if content == kw_for_match:
                return True
        elif mode == "regex":
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                if re.search(kw, message_content, flags=flags):
                    return True
            except re.error:
                logger.warning("Invalid trigger keyword regex skipped: %s", kw)
        else:
            # Default mode: contains
            if kw_for_match in content:
                return True

    return False

async def download_image(url: str, max_size_mb: int = 100) -> bytes | None:
    """
    安全地下载一张图片，增加了超时和大小限制。
    :param url: 图片的URL
    :param max_size_mb: 允许下载的最大文件大小（单位：MB）
    :return: 图片的字节数据，如果失败则返回None
    """
    max_size_bytes = max_size_mb * 1024 * 1024
    # 设置一个合理的超时，防止请求永久挂起
    timeout = aiohttp.ClientTimeout(total=20) # 总超时20秒

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.warning(f"Failed to download image from {url}, status code: {resp.status}")
                    return None

                content_length = resp.headers.get('Content-Length')
                if content_length and int(content_length) > max_size_bytes:
                    logger.warning(f"Image from {url} exceeds size limit of {max_size_mb}MB. "
                                   f"Reported size: {int(content_length) / 1024 / 1024:.2f}MB.")
                    return None

                downloaded_size = 0
                image_data = bytearray()
                # 逐块读取响应，而不是一次性加载到内存
                async for chunk in resp.content.iter_chunked(8192): # 8KB per chunk
                    downloaded_size += len(chunk)
                    if downloaded_size > max_size_bytes:
                        logger.warning(f"Image download from {url} aborted, exceeded size limit of {max_size_mb}MB.")
                        return None
                    image_data.extend(chunk)
                
                logger.info(f"Successfully downloaded image from {url}, size: {downloaded_size / 1024:.2f}KB")
                return bytes(image_data)

    except asyncio.TimeoutError:
        logger.warning(f"Timeout when downloading image from {url}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while downloading image from {url}", exc_info=True)
        return None

# --- 插件 HTTP 请求工具 ---

# [SECURITY] Add utility to check for internal/private IPs to prevent SSRF
async def _is_internal_url(url: str) -> Tuple[bool, List[str], str]:
    """Checks if a URL resolves to a private, local, or reserved IP address.
    Returns (is_blocked, resolved_ips, hostname) to prevent DNS rebinding TOCTOU."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True, [], ""

        try:
            ipaddress.ip_address(hostname)
            ips = [hostname]
        except ValueError:
            loop = asyncio.get_event_loop()
            addrinfo = await loop.run_in_executor(None, socket.getaddrinfo, hostname, None)
            ips = sorted(set(info[4][0] for info in addrinfo))

        for ip_str in ips:
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                return True, ips, hostname
        return False, ips, hostname
    except (socket.gaierror, ValueError) as e:
        logger.warning(f"Could not resolve or parse IP for URL '{url}': {e}")
        return True, [], ""
    except Exception as e:
        logger.error(f"Unexpected error during URL validation for '{url}': {e}", exc_info=True)
        return True, [], ""

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
    plugin_name = plugin_config.get('name', 'Unknown Plugin')

    if not url:
        logger.warning(f"Plugin '{plugin_name}' has no URL configured.")
        return None

    allow_internal = http_conf.get('allow_internal_requests', False)
    resolved_ips: List[str] = []
    original_hostname = ""
    validated_ips: set = set()
    if not allow_internal:
        is_blocked, resolved_ips, original_hostname = await _is_internal_url(url)
        if is_blocked:
            error_msg = f"Error: Request to internal or private IP address is blocked for security reasons. URL: {url}"
            logger.error(f"Plugin '{plugin_name}' attempted to access a blocked internal URL. {error_msg}")
            return error_msg
        validated_ips = set(resolved_ips) if resolved_ips else set()

    headers_str = _format_with_placeholders(http_conf.get('headers', '{}'), message, args)
    body_str = _format_with_placeholders(http_conf.get('body_template', '{}'), message, args)

    MAX_BODY_SIZE = 64 * 1024
    if len(body_str) > MAX_BODY_SIZE:
        error_msg = f"Error: Request body exceeds maximum size of {MAX_BODY_SIZE} bytes."
        logger.error(f"Plugin '{plugin_name}' {error_msg}")
        return error_msg

    try:
        headers = await asyncio.to_thread(json.loads, headers_str) if headers_str.strip() else {}
        if body_str.strip() and 'content-type' not in (h.lower() for h in headers):
            headers['Content-Type'] = 'application/json'

        if resolved_ips and original_hostname:
            original_url = url
            parsed = urlparse(url)
            ip_to_use = resolved_ips[0]
            if parsed.port:
                url = parsed._replace(netloc=f"{ip_to_use}:{parsed.port}").geturl()
            else:
                url = parsed._replace(netloc=ip_to_use).geturl()
            headers['Host'] = original_hostname

        if validated_ips and original_hostname:
            _, current_ips, _ = await _is_internal_url(original_url)
            if current_ips and set(current_ips) != validated_ips:
                error_msg = f"Error: DNS resolution changed during request, possible DNS rebinding attack. URL: {url}"
                logger.error(f"Plugin '{plugin_name}' DNS rebinding detected: {validated_ips} -> {current_ips}")
                return error_msg

        async with aiohttp.ClientSession(headers=headers) as session:
            request_kwargs = {}
            if method in ['POST', 'PUT', 'PATCH']:
                try:
                    request_kwargs['json'] = await asyncio.to_thread(json.loads, body_str)
                except json.JSONDecodeError:
                    request_kwargs['data'] = body_str
            async with session.request(method, url, **request_kwargs) as response:
                MAX_RESPONSE_SIZE = 1 * 1024 * 1024
                response_text = await response.text()
                if len(response_text) > MAX_RESPONSE_SIZE:
                    logger.warning(f"Plugin '{plugin_name}' response truncated from {len(response_text)} to {MAX_RESPONSE_SIZE} bytes.")
                    response_text = response_text[:MAX_RESPONSE_SIZE]
                if 200 <= response.status < 300:
                    logger.info(f"Plugin '{plugin_name}' HTTP request to {url} successful.")
                    return response_text
                else:
                    logger.error(f"Plugin '{plugin_name}' HTTP request failed with status {response.status}: {response_text}")
                    return f"Error: API call failed with status {response.status}."
    except aiohttp.ClientError as e:
        logger.error(f"Plugin '{plugin_name}' HTTP request network error: {e}", exc_info=True)
        return f"Error: Network error during API call: {e}"
    except (json.JSONDecodeError, TypeError) as e:
         logger.error(f"Plugin '{plugin_name}' failed to parse Headers or Body JSON: {e}", exc_info=True)
         return f"Error: Invalid JSON in plugin configuration (Headers/Body): {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred in plugin '{plugin_name}': {e}", exc_info=True)
        return f"Error: An unexpected error occurred while running the plugin."

def escape_xml(text: str) -> str:
    return _xml_escape(str(text or ""), {'"': '&quot;', "'": '&apos;'})


# --- Memory Transformation ---

def transform_memories_for_prompt(memories: List[Dict[str, Any]], target_timezone_str: str = 'UTC') -> List[str]:
    """
    Transforms raw memory entries from the database into human-readable strings for the LLM prompt.
    It converts the stored UTC timestamp to a target timezone.
    All content is XML-escaped to prevent prompt injection through memory content.
    """
    transformed_memories = []
    
    try:
        target_tz = pytz.timezone(target_timezone_str)
    except pytz.UnknownTimeZoneError:
        logger.warning(f"Unknown timezone '{target_timezone_str}'. Falling back to UTC.")
        target_tz = pytz.utc

    for memory in memories:
        content = memory.get('content', '')
        
        # Regex to find the structured tag: [memory key="value" ...]
        tag_match = re.search(r'\[memory\s+(.*?)\]', content)
        
        if not tag_match:
            transformed_memories.append(escape_xml(content))
            continue

        tag_content = tag_match.group(1)
        attributes = dict(re.findall(r'(\w+)="(.*?)"', tag_content))
        
        original_timestamp_str = attributes.get('timestamp')
        user_name = attributes.get('user_name', 'Unknown')
        
        if not original_timestamp_str:
            clean_content = content.replace(tag_match.group(0), '').strip()
            transformed_memories.append(escape_xml(clean_content))
            continue
            
        try:
            utc_timestamp = datetime.fromisoformat(original_timestamp_str.replace('Z', '+00:00'))
            local_timestamp = utc_timestamp.astimezone(target_tz)
            formatted_time = local_timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')
            nl_prefix = f"[由 {user_name} 在 {formatted_time} 记录]"
            final_content = content.replace(tag_match.group(0), nl_prefix).strip()
            transformed_memories.append(escape_xml(final_content))
            
        except (ValueError, TypeError) as e:
            logger.error(f"Could not parse or convert timestamp '{original_timestamp_str}': {e}")
            clean_content = content.replace(tag_match.group(0), '').strip()
            transformed_memories.append(escape_xml(clean_content))

    return transformed_memories
