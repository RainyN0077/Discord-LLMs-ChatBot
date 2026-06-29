"""Auto-Interject Star (AstrBot v4.26.2).

Triggers the bot to spontaneously join conversations after N messages.
"""

import logging
from typing import Any, Dict

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class AutoInterject(star.Star):
    """Counts messages and triggers LLM response after threshold."""

    name = "auto_interject"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        self._counts: Dict[str, int] = {}

    def _is_triggered(self, channel_id: str, text: str, config: Dict[str, Any]) -> bool:
        if not config.get("auto_interject_enabled", False):
            return False
        interval = int(config.get("auto_interject_interval", 20))
        min_length = int(config.get("auto_interject_min_length", 0))

        current = self._counts.get(channel_id, 0) + 1
        self._counts[channel_id] = current

        if current < interval:
            return False
        if min_length > 0 and len(text.strip()) < min_length:
            return False
        self._counts[channel_id] = 0
        return True

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        config = self.context.get_config()
        channel_id = event.get_group_id()
        text = event.get_message_str()
        if self._is_triggered(channel_id, text, config):
            logger.debug("Auto-interject triggered in channel %s", channel_id)
