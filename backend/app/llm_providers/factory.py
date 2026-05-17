# backend/app/llm_providers/factory.py
from typing import Any, Dict, Type

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

PROVIDER_BASE_URLS: Dict[str, str] = {
    "deepseek": "https://api.deepseek.com",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "volcengine": "https://ark.cn-beijing.volces.com/api/v3",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "stepfun": "https://api.stepfun.com/v1",
}

def get_llm_provider(config: Dict[str, Any]) -> LLMProvider:
    """
    Factory function to get an instance of the appropriate LLM provider.

    Args:
        config (Dict[str, Any]): The part of the bot configuration relevant to the LLM.

    Returns:
        LLMProvider: An instance of a concrete LLMProvider subclass.

    Raises:
        ValueError: If the specified provider is not supported.
    """
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
                         
    return provider_class(provider_config)
