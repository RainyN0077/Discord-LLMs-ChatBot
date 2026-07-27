"""Auto-Interject Star (AstrBot v4.26.2).

Triggers the bot to spontaneously join conversations after N messages
in a channel.  Does NOT start an independent LLM call; instead sets event
extras so the main pipeline can respond (D-2).

Design (D-2):
  - Maintains per-channel message counts in memory (resets on restart).
  - When ``count >= interval``, sets ``auto_interject_triggered = True``
    and ``trigger_source = "auto_interject"`` on the event extras.
  - Downstream stars (trigger, LLM pipeline) read these extras and
    respond accordingly.
  - On any exception, resets the channel count to avoid livelock.
"""

import logging
from typing import Any, Dict

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class AutoInterject(star.Star):
    """Counts messages and triggers LLM response after threshold.

    State is maintained per-channel in ``_counts`` (in-memory only,
    lost on restart).  This matches the NoneBot2 legacy behaviour
    (see backend/app/handlers/automation.py).
    """

    name = "auto_interject"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        self._counts: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Trigger logic
    # ------------------------------------------------------------------

    def _is_triggered(
        self, channel_id: str, text: str, config: Dict[str, Any]
    ) -> bool:
        """Check whether the auto-interject threshold has been reached.

        Returns True if the channel's message count >= configured interval
        AND the message meets the minimum length requirement.
        Resets the count to 0 when triggered so the cycle repeats.

        Matches legacy ``track_auto_interject`` behaviour
        (backend/app/handlers/automation.py:7-28):
          1. Minimum length is checked FIRST — short messages are NOT
             counted.
          2. Count is incremented only for messages that pass the
             length check.
          3. Trigger fires when ``count >= interval`` (not ==).

        Config keys (from management-layer ``/config`` endpoint):
          - ``auto_interject_enabled`` (bool)
          - ``auto_interject_interval`` (int, default 20)
          - ``auto_interject_min_length`` (int, default 0)
        """
        if not config.get("auto_interject_enabled", False):
            return False

        try:
            interval = max(1, int(config.get("auto_interject_interval", 20)))
        except (TypeError, ValueError):
            interval = 20

        try:
            min_length = max(0, int(config.get("auto_interject_min_length", 0)))
        except (TypeError, ValueError):
            min_length = 0

        # ---- Min-length check BEFORE counting (legacy compatibility) ----
        # Legacy: if message is too short, return False without incrementing.
        if len(text.strip()) < min_length:
            return False

        # ---- Increment count ----
        current = self._counts.get(channel_id, 0) + 1
        self._counts[channel_id] = current

        # ---- Interval check ----
        if current < interval:
            return False

        # ---- Triggered — reset so the next cycle starts fresh ----
        self._counts[channel_id] = 0
        return True

    def _reset_counts(self, channel_id: str) -> None:
        """Reset the message count for a channel.

        Called on exception to prevent livelock.
        """
        self._counts[channel_id] = 0

    # ------------------------------------------------------------------
    # Handler
    # ------------------------------------------------------------------

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Count messages and set auto-interject extras if threshold reached.

        Pipeline:
          1. Read bot config.
          2. Check trigger state for this channel.
          3. If triggered:
             - Set ``event.set_extra("auto_interject_triggered", True)``
             - Set ``event.set_extra("trigger_source", "auto_interject")``
          4. On any exception: reset channel count and continue.
        """
        channel_id = event.get_group_id()
        if not channel_id:
            return

        try:
            config = self.context.get_config()
            text = event.get_message_str()

            if self._is_triggered(channel_id, text, config):
                # Signal downstream stars to respond without a normal trigger.
                # Design D-2: auto_interject does NOT start an independent
                # LLM call; the main pipeline sees these extras and responds.
                event.set_extra("auto_interject_triggered", True)
                event.set_extra("trigger_source", "auto_interject")
                logger.debug("Auto-interject triggered in channel %s", channel_id)
        except Exception:
            logger.debug("Auto-interject error, resetting count for channel %s", channel_id, exc_info=True)
            self._reset_counts(channel_id)
