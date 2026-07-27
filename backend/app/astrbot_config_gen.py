"""AstrBot Configuration Generator (AstrBot 4.26.7 native format).

Converts the existing per-bot config.json (managed by BotInstance/config_cache.py)
into AstrBot-compatible native JSON configuration at::

    data/bots/{bot_id}/astrbot/data/cmd_config.json

Each bot gets an isolated AstrBot root directory with ``.astrbot`` marker,
``data/plugins/`` and all required sub-directories.
"""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config_cache import BOTS_DIR, get_bot_dir

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider name mapping: current config key → AstrBot internal provider name
# ---------------------------------------------------------------------------
PROVIDER_MAP: Dict[str, str] = {
    "openai": "openai",
    "google": "google",
    "anthropic": "anthropic",
    "grok": "xai",              # xAI/Grok → registered as "xai" in AstrBot
    "deepseek": "deepseek",
    "siliconflow": "siliconflow",
    "volcengine": "volcengine",
    "dashscope": "dashscope",
    "moonshot": "moonshot",
    "zhipu": "zhipu",
    "stepfun": "stepfun",
}

# Providers that use OpenAI-compatible protocol (same adapter type, different provider)
OPENAI_COMPATIBLE_PROVIDERS = {
    "deepseek", "siliconflow", "volcengine", "dashscope",
    "moonshot", "zhipu", "stepfun",
}

# Base URL config key per provider
BASE_URL_KEYS: Dict[str, str] = {
    "openai": "openai_base_url",
    "anthropic": "anthropic_base_url",
    "grok": "grok_base_url",
    "deepseek": "deepseek_base_url",
    "siliconflow": "siliconflow_base_url",
    "volcengine": "volcengine_base_url",
    "dashscope": "dashscope_base_url",
    "moonshot": "moonshot_base_url",
    "zhipu": "zhipu_base_url",
    "stepfun": "stepfun_base_url",
}

# AstrBot adapter type per provider key
PROVIDER_ADAPTER_TYPE: Dict[str, str] = {
    "openai": "openai_chat_completion",
    "google": "googlegenai_chat_completion",
    "anthropic": "anthropic_chat_completion",
    "grok": "openai_chat_completion",
    "deepseek": "openai_chat_completion",
    "siliconflow": "openai_chat_completion",
    "volcengine": "openai_chat_completion",
    "dashscope": "openai_chat_completion",
    "moonshot": "openai_chat_completion",
    "zhipu": "openai_chat_completion",
    "stepfun": "openai_chat_completion",
}


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_astrbot_root_dir(bot_id: str) -> Path:
    """Return the AstrBot root directory for a given bot.

    This is the directory that contains ``.astrbot`` marker and ``data/``.
    """
    return get_bot_dir(bot_id) / "astrbot"


def get_cmd_config_path(bot_id: str) -> Path:
    """Return the path to the AstrBot native ``cmd_config.json`` file."""
    return get_astrbot_root_dir(bot_id) / "data" / "cmd_config.json"


# ---------------------------------------------------------------------------
# Root directory initialisation
# ---------------------------------------------------------------------------

def ensure_astrbot_root(root_dir: Path) -> None:
    """Ensure *root_dir* is a valid AstrBot root directory.

    Creates ``.astrbot`` marker file and all required sub-directories.
    Idempotent — safe to call on every start.
    """
    root_dir.mkdir(parents=True, exist_ok=True)

    # .astrbot marker — AstrBot uses this to detect the root
    dot_astrbot = root_dir / ".astrbot"
    if not dot_astrbot.exists():
        dot_astrbot.touch()

    # Required sub-directories
    for subdir in ("data", "data/config", "data/plugins", "data/temp"):
        (root_dir / subdir).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_base_url(config: Dict[str, Any], provider_key: str) -> Optional[str]:
    """Resolve the effective base URL for a provider from the config dict."""
    url_key = BASE_URL_KEYS.get(provider_key)
    if url_key and config.get(url_key):
        return config[url_key]
    return config.get("base_url") or None


def _get_api_key_list(config: Dict[str, Any], provider_key: str) -> List[str]:
    """Return the API key(s) as a list for AstrBot's ``key`` field."""
    key = config.get("api_key", "")
    if key:
        return [key]
    return []


# ---------------------------------------------------------------------------
# Provider config builder
# ---------------------------------------------------------------------------

def _build_provider_config(bot_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build the AstrBot ``provider`` entry (a single provider object).

    Returns a dict with ``provider`` key containing a **list** with one
    provider entry (the active LLM provider).
    """
    provider_key = bot_config.get("llm_provider", "openai")
    astrbot_provider = PROVIDER_MAP.get(provider_key, "openai")
    adapter_type = PROVIDER_ADAPTER_TYPE.get(provider_key, "openai_chat_completion")

    # Build the provider entry matching AstrBot 4.26.7 CONFIG_METADATA_2
    provider_entry: Dict[str, Any] = {
        "id": astrbot_provider,
        "provider": astrbot_provider,
        "type": adapter_type,
        "provider_type": "chat_completion",
        "enable": True,
        "key": _get_api_key_list(bot_config, provider_key),
        "api_base": _resolve_base_url(bot_config, provider_key) or "",
        "timeout": 120,
        "proxy": "",
    }

    # Model name override
    model_name = bot_config.get("model_name", "")
    if model_name:
        provider_entry["model"] = model_name

    # Extra model parameters (forwarded to the LLM adapter)
    extra_params: Dict[str, Any] = {}
    for param in ("temperature", "max_tokens", "top_p", "top_k",
                  "frequency_penalty", "presence_penalty"):
        val = bot_config.get(param)
        if val is not None:
            extra_params[param] = val

    # System prompt
    system_prompt = bot_config.get("system_prompt", "")
    if system_prompt:
        extra_params["system_prompt"] = system_prompt

    # Streaming preference
    stream = bot_config.get("stream_response", True)
    extra_params["stream"] = stream

    if extra_params:
        provider_entry["kwargs"] = extra_params

    # Custom headers (OpenAI-compatible providers often need them)
    custom_headers = _build_custom_headers(bot_config, provider_key)
    if custom_headers:
        provider_entry["custom_headers"] = custom_headers

    return {"provider": [provider_entry]}


def _build_custom_headers(bot_config: Dict[str, Any],
                          provider_key: str) -> Optional[Dict[str, str]]:
    """Build custom_headers dict for provider config.

    Reads the structured ``custom_headers`` list from bot config (list of
    ``{"key": ..., "value": ...}``) and converts to a flat dict.
    """
    raw = bot_config.get("custom_headers", [])
    if not raw:
        return None
    headers: Dict[str, str] = {}
    for item in raw:
        if isinstance(item, dict) and "key" in item:
            headers[item["key"]] = str(item.get("value", ""))
    return headers if headers else None


# ---------------------------------------------------------------------------
# Platform config builder
# ---------------------------------------------------------------------------

def _build_platform_config(bot_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build the AstrBot ``platform`` entry for Discord.

    Returns a dict with ``platform`` key containing a **list** with one
    Discord platform adapter entry.
    """
    platform_entry: Dict[str, Any] = {
        "id": bot_config.get("bot_id", "main"),
        "type": "discord",
        "enable": bot_config.get("enabled", True),
        "discord_token": bot_config.get("discord_token", ""),
        "discord_proxy": "",
        "discord_command_register": True,
        "discord_activity_name": "",
        "discord_allow_bot_messages": False,
    }

    return {"platform": [platform_entry]}


# ---------------------------------------------------------------------------
# Full config generator
# ---------------------------------------------------------------------------

def generate_astrbot_config(bot_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a complete AstrBot 4.26.7-native configuration dict.

    The returned dict is structured according to AstrBot's ``DEFAULT_CONFIG``
    and ``CONFIG_METADATA_2`` schemas.  Unknown top-level keys are silently
    ignored by AstrBot, so we use them to forward configuration to our custom
    star plugins.

    Args:
        bot_config: Per-bot configuration dict (BotInstance.config).

    Returns:
        Dict suitable for JSON serialization as ``cmd_config.json``.
    """
    config: Dict[str, Any] = {
        # ------------------------------------------------------------------
        # Core AstrBot fields
        # ------------------------------------------------------------------
        "config_version": 2,
        "wake_prefix": ["/"],
        "log_level": "INFO",
        "admins_id": ["astrbot"],
        "plugin_set": ["*"],

        # ------------------------------------------------------------------
        # Dashboard — port must be unique per instance to avoid conflict
        # ------------------------------------------------------------------
        "dashboard": {
            "port": bot_config.get("dashboard_port", 6185),
            "web_path": "/dashboard",
        },

        # ------------------------------------------------------------------
        # Provider & platform arrays (built by dedicated helpers)
        # ------------------------------------------------------------------
        **_build_provider_config(bot_config),
        **_build_platform_config(bot_config),

        # ------------------------------------------------------------------
        # Empty provider/platform settings stubs (AstrBot expects them)
        # ------------------------------------------------------------------
        "provider_settings": {},
        "platform_settings": {},

        # ------------------------------------------------------------------
        # Persona — list of persona definitions
        # ------------------------------------------------------------------
        "persona": [
            {
                "name": "default",
                "system_prompt": bot_config.get("system_prompt",
                    "You are a helpful assistant."),
                "bot_nickname": bot_config.get("bot_nickname", "Bot"),
            },
        ],
    }

    # ------------------------------------------------------------------
    # Custom top-level keys forwarded to star plugins
    # AstrBot silently ignores unknown keys, so this is safe.
    # ------------------------------------------------------------------

    # Internal API endpoint (visited by star plugins for IPC)
    config["internal_api"] = {
        "base_url": "http://127.0.0.1:8093/internal",
        "secret_token": bot_config.get("api_secret_key", "") + ":internal",
    }

    # Knowledge/memory settings
    config["knowledge"] = {
        "recall_top_k": bot_config.get("auto_memory_recall_top_k", 12),
        "recall_char_limit": bot_config.get("auto_memory_recall_char_limit", 2200),
        "recall_max_age_days": bot_config.get("auto_memory_recall_max_age_days", 365),
        "memory_dedup_threshold": bot_config.get("memory_dedup_threshold", 0.0),
        "world_book_dedup_threshold": bot_config.get("world_book_dedup_threshold", 0.0),
        "embedding_enabled": bot_config.get("memory_embedding_enabled", False),
        "rerank_enabled": bot_config.get("memory_rerank_enabled", False),
    }

    # Conversation/context settings
    cc = bot_config.get("channel_context_settings", {})
    mc = bot_config.get("memory_context_settings", {})
    config["conversation"] = {
        "context_mode": bot_config.get("context_mode", "channel"),
        "channel": {
            "message_limit": cc.get("message_limit", 10),
            "char_limit": cc.get("char_limit", 4000),
            "unlimited": cc.get("unlimited_context_length", False),
        },
        "memory": {
            "message_limit": mc.get("message_limit", 15),
            "char_limit": mc.get("char_limit", 6000),
            "unlimited": mc.get("unlimited_context_length", False),
        },
    }

    # Star plugin configuration
    current_plugins = bot_config.get("plugins", {})
    config["stars"] = {
        "context_assembler": {"enabled": True},
        "persona": {"enabled": True},
        "knowledge_bridge": {"enabled": True},
        "trigger": {"enabled": True},
        "post_process": {"enabled": True},
        "streaming_respond": {"enabled": True},
        "ocr_image": {"enabled": True},
        "usage_tracker": {"enabled": True},
        "auto_interject": {
            "enabled": bot_config.get("auto_interject_enabled", False),
            "interval": bot_config.get("auto_interject_interval", 20),
            "min_length": bot_config.get("auto_interject_min_length", 0),
        },
        "repeat_parrot": {
            "enabled": bot_config.get("repeat_parrot_enabled", False),
            "threshold": bot_config.get("repeat_parrot_threshold", 3),
            "case_sensitive": bot_config.get("repeat_parrot_case_sensitive", False),
            "trim_whitespace": bot_config.get("repeat_parrot_trim_whitespace", True),
            "min_length": bot_config.get("repeat_parrot_min_length", 2),
            "require_multiple_users": bot_config.get("repeat_parrot_require_multiple_users", True),
        },
        "plugin_bridge": {
            "enabled": True,
            **({"plugins": current_plugins} if current_plugins else {}),
        },
        "memory_tools": {"enabled": True},
        "interaction_recorder": {"enabled": True},
        "debug_capture": {"enabled": True},
    }

    # User options
    config["user_options"] = bot_config.get("user_options", {
        "enabled": False,
        "rules": {},
    })

    # Trigger configuration
    config["trigger"] = {
        "keywords": bot_config.get("trigger_keywords", []),
        "match_mode": bot_config.get("trigger_match_mode", "contains"),
        "case_sensitive": bot_config.get("trigger_case_sensitive", False),
    }

    # Bot metadata
    config["astrbot"] = {
        "bot_id": bot_config.get("bot_id", "main"),
        "bot_name": bot_config.get("bot_name", "Unnamed Bot"),
        "bot_nickname": bot_config.get("bot_nickname", "Bot"),
        "version": "4.0",
    }

    return config


# ---------------------------------------------------------------------------
# Write / remove
# ---------------------------------------------------------------------------

def write_astrbot_config(bot_id: str, bot_config: Dict[str, Any]) -> Path:
    """Generate and write AstrBot native ``cmd_config.json`` for a bot.

    Steps:
        1. Ensure AstrBot root directory exists (``ensure_astrbot_root``).
        2. Build the native config dict via ``generate_astrbot_config``.
        3. Serialise to ``{root}/data/cmd_config.json`` (pretty-printed JSON).

    Args:
        bot_id: The bot's unique identifier.
        bot_config: Per-bot configuration dict.

    Returns:
        Path to the written ``cmd_config.json``.
    """
    root_dir = get_astrbot_root_dir(bot_id)
    ensure_astrbot_root(root_dir)

    astrbot_config = generate_astrbot_config(bot_config)

    config_path = get_cmd_config_path(bot_id)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(astrbot_config, f, indent=2, ensure_ascii=False)

    # Restrict file permissions — config contains API keys and tokens
    try:
        os.chmod(config_path, 0o600)
    except Exception:
        pass

    logger.info("Generated AstrBot config for bot '%s' at %s", bot_id, config_path)
    return config_path


def remove_astrbot_config(bot_id: str) -> None:
    """Remove the generated AstrBot root directory for a bot."""
    root_dir = get_astrbot_root_dir(bot_id)
    if root_dir.exists():
        shutil.rmtree(str(root_dir))
        logger.info("Removed AstrBot root for bot '%s' at %s", bot_id, root_dir)
