import copy
import json
import logging
import os
import secrets
from pathlib import Path
from typing import Any, Dict, Optional

from .ocr_service import DEFAULT_OCR_PROMPT_TEMPLATE, OCR_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

DATA_DIR = Path.cwd() / "data"
DATA_DIR.mkdir(exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"
BOTS_DIR = DATA_DIR / "bots"
BOTS_DIR.mkdir(exist_ok=True)
DEFAULT_BOT_ID = "main"

_cache: Optional[Dict[str, Any]] = None
_cache_mtime: float = 0.0

DEFAULT_CONFIG: Dict[str, Any] = {
    'bot_id': '', 'bot_name': 'Unnamed Bot', 'platform': 'discord', 'enabled': True,
    'discord_token': '', 'llm_provider': 'openai', 'api_key': '', 'base_url': None,
    'openai_base_url': None, 'anthropic_base_url': None, 'grok_base_url': None,
    'model_name': 'gpt-4o',
    'llm_is_multimodal': True,
    'ocr_provider': 'openai',
    'ocr_api_key': '',
    'ocr_base_url': '',
    'ocr_port': '',
    'ocr_model_name': '',
    'ocr_prompt_template': DEFAULT_OCR_PROMPT_TEMPLATE,
    'ocr_max_output_chars': 4000,
    'ocr_timeout_seconds': OCR_TIMEOUT_SECONDS,
    'ocr_timeout_disabled': False,
    'embedding_provider': 'openai',
    'embedding_api_key': '',
    'embedding_base_url': '',
    'embedding_port': '',
    'embedding_model_name': 'text-embedding-3-small',
    'embedding_dimensions': 1536,
    'rerank_provider': 'openai',
    'rerank_api_key': '',
    'rerank_base_url': '',
    'rerank_port': '',
    'rerank_model_name': 'gpt-4.1-mini',
    'system_prompt': 'You are a helpful assistant...',
    'blocked_prompt_response': '...',
    'bot_nickname': 'Bot',
    'trigger_keywords': [], 'stream_response': True,
    'trigger_match_mode': 'contains',
    'trigger_case_sensitive': False,
    'auto_interject_enabled': False,
    'auto_interject_interval': 20,
    'auto_interject_min_length': 0,
    'repeat_parrot_enabled': False,
    'repeat_parrot_threshold': 3,
    'repeat_parrot_case_sensitive': False,
    'repeat_parrot_trim_whitespace': True,
    'repeat_parrot_min_length': 2,
    'repeat_parrot_require_multiple_users': True,
    'memory_dedup_threshold': 0.0,
    'world_book_dedup_threshold': 0.0,
    'memory_embedding_enabled': False,
    'memory_rerank_enabled': False,
    'user_personas': {}, 'role_based_config': {}, 'scoped_prompts': {'guilds': {}, 'channels': {}},
    'context_mode': 'channel',
    'channel_context_settings': {'message_limit': 10, 'char_limit': 4000, 'unlimited_context_length': False, 'unlimited_message_count': False},
    'memory_context_settings': {'message_limit': 15, 'char_limit': 6000, 'unlimited_context_length': False, 'unlimited_message_count': False},
    'custom_parameters': [], 'plugins': {},
    'api_secret_key': secrets.token_hex(32),
}


def _set_defaults_recursive(default: dict, config: dict) -> None:
    for key, value in default.items():
        if isinstance(value, dict):
            config.setdefault(key, {})
            _set_defaults_recursive(value, config[key])
        else:
            config.setdefault(key, value)


def load_config() -> Dict[str, Any]:
    global _cache, _cache_mtime
    try:
        mtime = os.path.getmtime(CONFIG_FILE)
    except OSError:
        mtime = 0.0

    if _cache is not None and mtime == _cache_mtime:
        return _cache

    if not os.path.exists(CONFIG_FILE):
        logger.warning(f"Config file not found at {CONFIG_FILE}. Creating a default one.")
        save_config(DEFAULT_CONFIG)
        _cache = dict(DEFAULT_CONFIG)
        _cache_mtime = os.path.getmtime(CONFIG_FILE)
        return _cache

    try:
        with open(CONFIG_FILE, "r", encoding='utf-8') as f:
            data = json.load(f)
        _set_defaults_recursive(DEFAULT_CONFIG, data)
        if not data.get("api_secret_key"):
            data["api_secret_key"] = secrets.token_hex(32)
            logger.warning("api_secret_key was empty in config.json, generated a new one")
        save_config(data)
        return data
    except json.JSONDecodeError as e:
        logger.error(f"FATAL: config.json is corrupted. Error: {e}. Using defaults.")
        _cache = dict(DEFAULT_CONFIG)
        _cache_mtime = 0.0
        return _cache
    except Exception as e:
        logger.error(f"FATAL: Unexpected error loading config.json: {e}", exc_info=True)
        _cache = dict(DEFAULT_CONFIG)
        _cache_mtime = 0.0
        return _cache


def save_config(config_data: Dict[str, Any]) -> None:
    global _cache, _cache_mtime
    with open(CONFIG_FILE, "w", encoding='utf-8') as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)
    _cache = config_data
    _cache_mtime = os.path.getmtime(CONFIG_FILE)


def invalidate_cache() -> None:
    global _cache, _cache_mtime
    _cache = None
    _cache_mtime = 0.0


def get_bot_dir(bot_id: str) -> Path:
    return BOTS_DIR / bot_id


def get_bot_config_path(bot_id: str) -> Path:
    return get_bot_dir(bot_id) / "config.json"


def get_bot_knowledge_path(bot_id: str) -> Path:
    return get_bot_dir(bot_id) / "knowledge.sqlite"


def get_bot_usage_path(bot_id: str) -> Path:
    return get_bot_dir(bot_id) / "usage_data.json"


# Legacy field name mappings: old key → new key
# Covers configs from earlier versions of the project where field names may have changed.
LEGACY_FIELD_MAP: Dict[str, str] = {
    'name': 'bot_name',
    'nickname': 'bot_nickname',
    'token': 'discord_token',
    'api_url': 'openai_base_url',
    'anthropic_api_url': 'anthropic_base_url',
    'grok_api_url': 'grok_base_url',
    'embedding_api_url': 'embedding_base_url',
    'rerank_api_url': 'rerank_base_url',
    'ocr_api_url': 'ocr_base_url',
}


def normalize_config(config: Dict[str, Any], *, apply_defaults: bool = True) -> Dict[str, Any]:
    """Normalize a config dict: remap legacy field names and optionally apply defaults."""
    normalized = copy.deepcopy(config)

    for old_key, new_key in LEGACY_FIELD_MAP.items():
        if old_key in normalized:
            normalized.setdefault(new_key, normalized[old_key])
            if old_key != new_key:
                del normalized[old_key]

    if normalized.get('openai_base_url') and not normalized.get('base_url'):
        normalized['base_url'] = normalized['openai_base_url']

    if apply_defaults:
        _set_defaults_recursive(DEFAULT_CONFIG, normalized)

    return normalized
