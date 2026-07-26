# backend/app/llm_providers/factory.py
import os
from typing import Any, Dict, Optional, Type

from .base import LLMProvider
from .openai_provider import OpenAIProvider
from .google_provider import GoogleProvider
from .anthropic_provider import AnthropicProvider
from .xai_provider import XAIProvider

# A mapping from provider names in the config to their corresponding class.
PROVIDER_MAP: Dict[str, Type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "google": GoogleProvider,
    "anthropic": AnthropicProvider,
    "grok": XAIProvider,
    "deepseek": OpenAIProvider,
    "siliconflow": OpenAIProvider,
    "volcengine": OpenAIProvider,
    "dashscope": OpenAIProvider,
    "moonshot": OpenAIProvider,
    "zhipu": OpenAIProvider,
    "stepfun": OpenAIProvider,
}

# Provider base URLs, overridable via environment variables:
#   LLM_BASE_URL_<PROVIDER_NAME_UPPER>
# e.g. LLM_BASE_URL_DEEPSEEK to override deepseek's base URL.
PROVIDER_BASE_URLS: Dict[str, str] = {
    "deepseek": "https://api.deepseek.com",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "volcengine": "https://ark.cn-beijing.volces.com/api/v3",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "stepfun": "https://api.stepfun.com/v1",
}

# Apply environment variable overrides to PROVIDER_BASE_URLS.
# For each provider, LLM_BASE_URL_<PROVIDER_NAME_UPPER> takes precedence.
for _provider_name in list(PROVIDER_BASE_URLS.keys()):
    _env_key = f"LLM_BASE_URL_{_provider_name.upper()}"
    _env_value = os.environ.get(_env_key)
    if _env_value:
        PROVIDER_BASE_URLS[_provider_name] = _env_value

# Module-level provider instance cache.
# Keys are derived from (provider_name, api_key_prefix, base_url, model_name)
# so that different credentials produce different cache entries, but full
# secrets are never stored in the key itself.
# The cache is bounded to prevent unbounded memory growth from many unique
# bot configurations.
_provider_cache: Dict[str, LLMProvider] = {}
_MAX_CACHE_SIZE = 32


def _make_cache_key(config: Dict[str, Any]) -> str:
    """Build a deterministic cache key without exposing full secrets.

    Uses the first 8 characters of the API key only — enough to distinguish
    different credentials without storing the full key in memory as a key
    string.  Includes model_name so that different models from the same
    provider+credential get separate cache entries.
    """
    provider = config.get("llm_provider", "openai").lower()
    if provider == "xai":
        provider = "grok"
    api_key = config.get("openai_api_key", "") or config.get("api_key", "") or ""
    api_prefix = api_key[:8]
    base_url = config.get("openai_base_url") or config.get("base_url") or ""
    model_name = config.get("openai_model_name", "") or config.get("model_name", "") or ""
    return f"{provider}:{api_prefix}:{base_url}:{model_name}"


def _evict_one() -> None:
    """Remove the single oldest cache entry when the cache is full.

    Python dicts preserve insertion order (Python 3.7+), so the first key
    is the oldest entry.  This is a FIFO strategy — good enough for a
    bounded cache of modest size (32 entries).
    """
    if len(_provider_cache) >= _MAX_CACHE_SIZE:
        try:
            _provider_cache.pop(next(iter(_provider_cache)))
        except StopIteration:
            pass


def clear_provider_cache() -> None:
    """Drop all cached provider instances.

    Exposed primarily for test isolation; under normal operation the cache
    is self-managing.
    """
    _provider_cache.clear()


def get_llm_provider(config: Dict[str, Any]) -> LLMProvider:
    """Factory function to get (or retrieve from cache) an LLM provider.

    Instances are cached by (provider_name, api_key_prefix, base_url).
    Reusing cached instances avoids redundant creation of HTTP clients and
    connection pools, preventing socket exhaustion under high concurrency.

    When the underlying config for a bot changes (different provider, key,
    or base URL) the cache key automatically differs and a new instance is
    created, so there is no staleness issue.

    Args:
        config (Dict[str, Any]): The part of the bot configuration relevant
            to the LLM.

    Returns:
        LLMProvider: An instance of a concrete LLMProvider subclass.

    Raises:
        ValueError: If the specified provider is not supported.
    """
    cache_key = _make_cache_key(config)
    cached = _provider_cache.get(cache_key)
    if cached is not None:
        return cached

    provider_name = config.get("llm_provider", "openai").lower()
    if provider_name == "xai":
        provider_name = "grok"

    provider_config = dict(config)
    if provider_name in PROVIDER_BASE_URLS:
        if not provider_config.get("openai_base_url") and not provider_config.get("base_url"):
            provider_config["openai_base_url"] = PROVIDER_BASE_URLS[provider_name]

    provider_class = PROVIDER_MAP.get(provider_name)

    if not provider_class:
        raise ValueError(f"Unsupported LLM provider: '{provider_name}'. "
                         f"Supported providers are: {list(PROVIDER_MAP.keys())}")

    provider = provider_class(provider_config)

    # Only cache successfully-created instances (errors propagate up).
    _evict_one()
    _provider_cache[cache_key] = provider

    return provider
