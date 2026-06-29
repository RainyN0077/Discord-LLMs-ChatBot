"""Plugin Bridge Star (AstrBot v4.26.2).

Bridges the legacy custom plugin system (plugins/manager.py) to AstrBot.
"""

import logging
from typing import Any, Tuple

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class PluginBridge(star.Star):
    """Bridge to legacy plugin system in management layer."""

    name = "plugin_bridge"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Allow legacy plugins to handle the message.

        Returns ("consumed", None) if handled, ("append", blocks) for injected data,
        or ("none", None) for no match.
        """
        logger.debug("Plugin bridge: checking legacy plugins")
        # Deferred: full bridge via internal API
