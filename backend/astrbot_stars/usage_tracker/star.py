"""Usage Tracker Star (AstrBot v4.26.2)."""

import logging
from typing import Any, Dict, Optional

import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class UsageTracker(star.Star):
    """Records LLM token usage to management layer."""

    name = "usage_tracker"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Hook for usage tracking during message processing."""
        pass  # Deferred: track usage after LLM response
