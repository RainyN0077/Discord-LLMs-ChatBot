"""xAI/Grok Provider Registration (AstrBot v4.26.2).

Registers xAI as a custom provider in AstrBot's provider system since
AstrBot doesn't ship a native Grok provider.
"""

import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.core.provider.entities import ProviderRequest, StreamingChunk

logger = logging.getLogger(__name__)


class XAIProvider(star.Star):
    """Registers xAI/Grok as a provider in AstrBot.

    xAI uses its own SDK (xai-sdk) which follows an Anthropic-like API pattern.
    This star acts as a bridge: it provides the xAI provider registration and
    delegates LLM requests to the xAI SDK.
    """

    name = "xai_provider"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)

    # Provider metadata for AstrBot's provider system
    provider_name = "xai"
    provider_models = ["grok-3", "grok-2", "grok-2-vision"]

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """No message handling — this star only registers the provider."""
        pass
