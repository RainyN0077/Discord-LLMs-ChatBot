"""Interaction Recorder Star (AstrBot v4.26.2)."""

import logging
from typing import Any, Dict

import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class InteractionRecorder(star.Star):
    """Records user messages and bot replies to management layer."""

    name = "interaction_recorder"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Record incoming user message."""
        config = self.context.get_config()
        internal = config.get("internal_api", {})
        if not internal:
            return
        # Deferred: POST to internal API for interaction recording
