"""AstrBot Configuration Generator.

Converts the existing per-bot config.json (managed by BotInstance/config_cache.py)
into AstrBot-compatible configuration files.

Each bot instance gets:
    data/bots/{bot_id}/astrbot/
        config.yml          — main AstrBot configuration
        stars/              — symlinks/copies of shared star packages
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

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

# Providers that use OpenAI-compatible protocol (same adapter, different base_url)
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


def get_astrbot_config_dir(bot_id: str) -> Path:
    """Return the AstrBot config directory for a given bot."""
    return get_bot_dir(bot_id) / "astrbot"


def _resolve_base_url(config: Dict[str, Any], provider_key: str) -> Optional[str]:
    """Resolve the effective base URL for a provider from the config dict."""
    url_key = BASE_URL_KEYS.get(provider_key)
    if url_key and config.get(url_key):
        return config[url_key]
    return config.get("base_url") or None


def _build_provider_config(bot_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build the AstrBot provider settings section for the active LLM provider."""
    provider_key = bot_config.get("llm_provider", "openai")
    astrbot_provider = PROVIDER_MAP.get(provider_key, "openai")
    api_key = bot_config.get("api_key", "")
    base_url = _resolve_base_url(bot_config, provider_key)
    model_name = bot_config.get("model_name", "gpt-4o")

    provider_settings: Dict[str, Any] = {
        astrbot_provider: {
            "api_key": api_key,
            "model": model_name,
            "temperature": bot_config.get("temperature"),
            "max_tokens": bot_config.get("max_tokens"),
            "top_p": bot_config.get("top_p"),
            "top_k": bot_config.get("top_k"),
            "frequency_penalty": bot_config.get("frequency_penalty"),
            "presence_penalty": bot_config.get("presence_penalty"),
            "system_prompt": bot_config.get("system_prompt", "You are a helpful assistant."),
            "stream": bot_config.get("stream_response", True),
        }
    }
    # Strip None values for cleaner YAML
    provider_settings[astrbot_provider] = {
        k: v for k, v in provider_settings[astrbot_provider].items() if v is not None
    }
    if base_url:
        provider_settings[astrbot_provider]["base_url"] = base_url

    # Embedding provider
    emb_provider = bot_config.get("embedding_provider", "")
    if emb_provider:
        provider_settings.setdefault("embedding", {})
        provider_settings["embedding"]["provider"] = PROVIDER_MAP.get(emb_provider, emb_provider)
        provider_settings["embedding"]["model"] = bot_config.get("embedding_model_name", "")
        if bot_config.get("embedding_api_key"):
            provider_settings["embedding"]["api_key"] = bot_config["embedding_api_key"]
        if bot_config.get("embedding_base_url"):
            provider_settings["embedding"]["base_url"] = bot_config["embedding_base_url"]

    # Rerank provider
    rerank_provider = bot_config.get("rerank_provider", "")
    if rerank_provider:
        provider_settings.setdefault("rerank", {})
        provider_settings["rerank"]["provider"] = PROVIDER_MAP.get(rerank_provider, rerank_provider)
        provider_settings["rerank"]["model"] = bot_config.get("rerank_model_name", "")
        if bot_config.get("rerank_api_key"):
            provider_settings["rerank"]["api_key"] = bot_config["rerank_api_key"]
        if bot_config.get("rerank_base_url"):
            provider_settings["rerank"]["base_url"] = bot_config["rerank_base_url"]

    # OCR provider
    ocr_provider = bot_config.get("ocr_provider", "")
    if ocr_provider:
        provider_settings.setdefault("ocr", {})
        provider_settings["ocr"]["provider"] = PROVIDER_MAP.get(ocr_provider, ocr_provider)
        provider_settings["ocr"]["model"] = bot_config.get("ocr_model_name", "")
        if bot_config.get("ocr_api_key"):
            provider_settings["ocr"]["api_key"] = bot_config["ocr_api_key"]
        if bot_config.get("ocr_base_url"):
            provider_settings["ocr"]["base_url"] = bot_config["ocr_base_url"]

    return {
        "active": astrbot_provider,
        "providers": provider_settings,
    }


def _build_platform_config(bot_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build the AstrBot platform/Discord adapter configuration."""
    token = bot_config.get("discord_token", "")
    platform_config: Dict[str, Any] = {
        "platforms": [
            {
                "type": "discord",
                "id": bot_config.get("bot_id", "main"),
                "enabled": bot_config.get("enabled", True),
                "discord_token": token,
                "discord_intents": bot_config.get("discord_intents", {
                    "guilds": True,
                    "guild_messages": True,
                    "direct_messages": True,
                    "message_content": True,
                    "members": True,
                }),
                # Custom settings forwarded to Discord adapter
                "discord_command_register": True,
                "discord_allow_bot_messages": False,
            }
        ]
    }
    return platform_config


def _build_star_config(bot_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build AstrBot star (plugin) configuration."""
    stars: Dict[str, Any] = {}
    current_plugins = bot_config.get("plugins", {})

    # Always include our custom stars (matching astrbot_stars/ directory names)
    stars["context_assembler"] = {"enabled": True}
    stars["persona"] = {"enabled": True}
    stars["knowledge_bridge"] = {"enabled": True}
    stars["trigger"] = {"enabled": True}
    stars["post_process"] = {"enabled": True}
    stars["streaming_respond"] = {"enabled": True}
    stars["ocr_image"] = {"enabled": True}
    stars["usage_tracker"] = {"enabled": True}
    stars["auto_interject"] = {
        "enabled": bot_config.get("auto_interject_enabled", False),
        "interval": bot_config.get("auto_interject_interval", 20),
        "min_length": bot_config.get("auto_interject_min_length", 0),
    }
    stars["repeat_parrot"] = {
        "enabled": bot_config.get("repeat_parrot_enabled", False),
        "threshold": bot_config.get("repeat_parrot_threshold", 3),
        "case_sensitive": bot_config.get("repeat_parrot_case_sensitive", False),
        "trim_whitespace": bot_config.get("repeat_parrot_trim_whitespace", True),
        "min_length": bot_config.get("repeat_parrot_min_length", 2),
        "require_multiple_users": bot_config.get("repeat_parrot_require_multiple_users", True),
    }
    stars["plugin_bridge"] = {"enabled": True}
    stars["memory_tools"] = {"enabled": True}
    stars["interaction_recorder"] = {"enabled": True}
    stars["debug_capture"] = {"enabled": True}

    # Forward custom plugin configs
    if current_plugins:
        stars["plugin_bridge"]["plugins"] = current_plugins

    return {"stars": stars}


def _build_knowledge_config(bot_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build AstrBot knowledge base configuration."""
    return {
        "knowledge": {
            "recall_top_k": bot_config.get("auto_memory_recall_top_k", 12),
            "recall_char_limit": bot_config.get("auto_memory_recall_char_limit", 2200),
            "recall_max_age_days": bot_config.get("auto_memory_recall_max_age_days", 365),
            "memory_dedup_threshold": bot_config.get("memory_dedup_threshold", 0.0),
            "world_book_dedup_threshold": bot_config.get("world_book_dedup_threshold", 0.0),
            "embedding_enabled": bot_config.get("memory_embedding_enabled", False),
            "rerank_enabled": bot_config.get("memory_rerank_enabled", False),
        }
    }


def _build_conversation_config(bot_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build AstrBot conversation/context configuration."""
    cc = bot_config.get("channel_context_settings", {})
    mc = bot_config.get("memory_context_settings", {})
    return {
        "conversation": {
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
    }


def generate_astrbot_config(bot_config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a complete AstrBot configuration dict from a BotInstance config.

    Args:
        bot_config: Per-bot configuration dict (BotInstance.config)

    Returns:
        Nested dict suitable for YAML serialization as AstrBot config.
    """
    config: Dict[str, Any] = {
        "astrbot": {
            "bot_id": bot_config.get("bot_id", "main"),
            "bot_name": bot_config.get("bot_name", "Unnamed Bot"),
            "bot_nickname": bot_config.get("bot_nickname", "Bot"),
            "version": "4.0",
        },
        ** _build_platform_config(bot_config),
        ** _build_provider_config(bot_config),
        ** _build_knowledge_config(bot_config),
        ** _build_conversation_config(bot_config),
        ** _build_star_config(bot_config),
        # Forward persona/scoped_prompts/user_options as custom fields
        "persona": {
            "system_prompt": bot_config.get("system_prompt", ""),
            "bot_nickname": bot_config.get("bot_nickname", "Bot"),
            "role_based_config": bot_config.get("role_based_config", {}),
            "scoped_prompts": bot_config.get("scoped_prompts", {"guilds": {}, "channels": {}}),
            "blocked_prompt_response": bot_config.get("blocked_prompt_response", ""),
        },
        "user_options": bot_config.get("user_options", {"enabled": False, "rules": {}}),
        "trigger": {
            "keywords": bot_config.get("trigger_keywords", []),
            "match_mode": bot_config.get("trigger_match_mode", "contains"),
            "case_sensitive": bot_config.get("trigger_case_sensitive", False),
        },
        # Internal API endpoint (for stars to reach management layer)
        #
        # The internal secret token is DERIVED from api_secret_key by
        # appending ":internal".  This isolates IPC credentials from the
        # external management API key so they can be rotated independently
        # without adding a new config field in Phase 1.
        "internal_api": {
            "base_url": "http://127.0.0.1:8093/internal",
            "secret_token": bot_config.get("api_secret_key", "") + ":internal",
        },
    }
    return config


def write_astrbot_config(bot_id: str, bot_config: Dict[str, Any]) -> Path:
    """Generate and write AstrBot config files for a bot instance.

    Args:
        bot_id: The bot's unique identifier.
        bot_config: Per-bot configuration dict.

    Returns:
        Path to the written config directory.
    """
    config_dir = get_astrbot_config_dir(bot_id)
    config_dir.mkdir(parents=True, exist_ok=True)

    astrbot_config = generate_astrbot_config(bot_config)

    config_path = config_dir / "config.yml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(astrbot_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Restrict file permissions — config.yml contains API keys and tokens
    try:
        os.chmod(config_path, 0o600)
    except Exception:
        pass

    logger.info("Generated AstrBot config for bot '%s' at %s", bot_id, config_path)
    return config_dir


def remove_astrbot_config(bot_id: str) -> None:
    """Remove generated AstrBot config files for a bot."""
    config_dir = get_astrbot_config_dir(bot_id)
    if config_dir.exists():
        shutil.rmtree(str(config_dir))
        logger.info("Removed AstrBot config for bot '%s' at %s", bot_id, config_dir)
