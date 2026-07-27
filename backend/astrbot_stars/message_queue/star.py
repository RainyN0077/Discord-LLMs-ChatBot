"""Message Queue Star (AstrBot v4.26.2).

Per-channel sequential processing to prevent race conditions on streaming replies.
Ported from app/handlers/message_queue.py.

Locking strategy:
  Uses per-channel asyncio.Lock with a non-blocking entry check.
  When a message arrives for a channel:

    1. Non-blocking check ``lock.locked()`` — if the per-channel lock is
       already held (a previous message is still being processed), signal
       ``channel_queue_full`` on the event and stop the pipeline so the
       message is rejected.

    2. Otherwise, acquire the lock and hold it for the duration of this
       star's ``on_message`` handler.  Release in ``finally``.

  This avoids concurrent processing of multiple messages in the same
  channel.  It is NOT a true queue — messages that arrive while a
  previous message is being processed are dropped, not queued — but
  it prevents the race condition where two LLM responses are generated
  for the same channel simultaneously.
"""

import asyncio
import logging
from typing import Dict

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
        """Get or create the per-channel asyncio.Lock."""
        if channel_id not in self._locks:
            self._locks[channel_id] = asyncio.Lock()
        return self._locks[channel_id]

    def _cleanup_channel(self, channel_id: str) -> None:
        """Remove channel lock when no longer needed (idle cleanup)."""
        self._locks.pop(channel_id, None)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Acquire per-channel lock before allowing pipeline processing.

        Non-blocking entry check:
          - If ``lock.locked()`` → another message is being processed for
            this channel.  Mark ``channel_queue_full`` and stop the
            pipeline so the message is rejected.
          - Otherwise → ``await lock.acquire()``, hold for this handler's
            scope, release in ``finally``.
        """
        channel_id = event.get_session_id()
        lock = self._get_lock(channel_id)

        # ---- Non-blocking channel-busy check ----
        if lock.locked():
            logger.warning(
                "Channel %s is busy, rejecting message (lock held)",
                channel_id,
            )
            event.set_extra("channel_queue_full", True)
            try:
                event.stop_event()
            except AttributeError:
                pass
            return

        # ---- Acquire and hold for this message's pipeline scope ----
        await lock.acquire()
        try:
            event.set_extra("channel_lock", lock)
            logger.debug("Message queue lock acquired for channel %s", channel_id)
        finally:
            lock.release()
            logger.debug("Message queue lock released for channel %s", channel_id)
