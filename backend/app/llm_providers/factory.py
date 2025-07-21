# backend/app/llm_providers/factory.py
from typing import Any, Dict, Type

from .base import LLMProvider
from .openai_provider import OpenAIProvider
from .google_provider import GoogleProvider
from .anthropic_provider import AnthropicProvider

# A mapping from provider names in the config to their corresponding class.
PROVIDER_MAP: Dict[str, Type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "google": GoogleProvider,
    "anthropic": AnthropicProvider,
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
    
    provider_class = PROVIDER_MAP.get(provider_name)
    
    if not provider_class:
        raise ValueError(f"Unsupported LLM provider: '{provider_name}'. "
                         f"Supported providers are: {list(PROVIDER_MAP.keys())}")
                         
    return provider_class(config)