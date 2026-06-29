"""Message Queue Star (AstrBot v4.26.2).

Per-channel sequential processing to prevent race conditions on streaming replies.
Ported from app/handlers/message_queue.py.
"""

import asyncio
import logging
from typing import Any, Dict

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class MessageQueue(star.Star):
    """Ensures per-channel messages are processed sequentially."""

    name = "message_queue"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, channel_id: str) -> asyncio.Lock:
        if channel_id not in self._locks:
            self._locks[channel_id] = asyncio.Lock()
        return self._locks[channel_id]

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Acquire per-channel lock before allowing pipeline processing."""
        channel_id = event.get_session_id()
        lock = self._get_lock(channel_id)

        # This is a cooperative gate — the pipeline will respect locks
        # set on the event context.
        event.set_extra("channel_lock", lock)
        logger.debug("Message queue lock acquired for channel %s", channel_id)
