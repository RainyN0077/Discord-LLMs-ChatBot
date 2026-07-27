"""Repeat-Parrot Star (AstrBot v4.26.2).

Detects N consecutive identical messages from different users in a channel
and echoes back the repeated content without invoking the LLM.

Design:
  - Maintains per-channel streak state in memory (lost on restart).
  - When ``count >= threshold``, sends the repeated content directly
    and calls ``event.stop_event()`` to block downstream LLM processing.
  - On any exception, resets the channel's streak state.
"""

import logging
from typing import Any, Dict

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class RepeatParrot(star.Star):
    """Detects message repetition streaks and echoes back.

    State is maintained per-channel in ``_streaks`` (in-memory only).
    Each streak tracks:
      - ``count``: number of consecutive identical messages.
      - ``text``: the normalized text being repeated.
      - ``users``: set of user IDs that participated.
      - ``parroted``: whether we already echoed (prevent double-fire).

    Matches legacy behaviour in backend/app/handlers/automation.py.
    """

    name = "repeat_parrot"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        self._streaks: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Trigger logic
    # ------------------------------------------------------------------

    def _check_repeat(
        self, channel_id: str, user_id: str, text: str, config: Dict[str, Any]
    ) -> str:
        """Check if the message completes a repeat-parrot streak.

        Args:
            channel_id: Discord channel (or group) ID.
            user_id: Sender ID for tracking multi-user requirement.
            text: Raw message text.
            config: Bot configuration dict.

        Returns:
            The original text to echo if triggered, or empty string if not.

        Config keys (from management-layer ``/config`` endpoint):
          - ``repeat_parrot_enabled`` (bool)
          - ``repeat_parrot_threshold`` (int, default 3)
          - ``repeat_parrot_case_sensitive`` (bool, default False)
          - ``repeat_parrot_trim_whitespace`` (bool, default True)
          - ``repeat_parrot_min_length`` (int, default 2)
          - ``repeat_parrot_require_multiple_users`` (bool, default True)
        """
        if not config.get("repeat_parrot_enabled", False):
            return ""

        try:
            threshold = max(2, int(config.get("repeat_parrot_threshold", 3)))
        except (TypeError, ValueError):
            threshold = 3

        case_sensitive = bool(config.get("repeat_parrot_case_sensitive", False))
        trim_ws = bool(config.get("repeat_parrot_trim_whitespace", True))

        try:
            min_length = max(0, int(config.get("repeat_parrot_min_length", 2)))
        except (TypeError, ValueError):
            min_length = 2

        require_multi = bool(
            config.get("repeat_parrot_require_multiple_users", True)
        )

        # Minimum length check
        if len(text.strip()) < min_length:
            return ""

        # Normalize text for comparison
        normalized = text.strip() if trim_ws else text
        if not case_sensitive:
            normalized = normalized.lower()

        # Get or initialise streak state for this channel
        streak = self._streaks.get(
            channel_id,
            {"count": 0, "text": "", "users": set(), "parroted": False},
        )

        if normalized == streak["text"] and normalized:
            # Same content — increment streak
            streak["count"] += 1
            streak["users"].add(user_id)
        else:
            # Different content — reset streak
            streak = {
                "count": 1,
                "text": normalized,
                "users": {user_id},
                "parroted": False,
            }

        self._streaks[channel_id] = streak

        # Check threshold
        if streak["count"] >= threshold and not streak["parroted"]:
            has_required_users = (
                len(streak["users"]) >= 2 if require_multi else True
            )
            if has_required_users:
                # Mark as parroted to prevent double-fire
                streak["parroted"] = True
                self._streaks[channel_id] = streak
                return text  # Return original text to echo

        return ""

    # ------------------------------------------------------------------
    # Message sending (AstrBot API abstraction)
    # ------------------------------------------------------------------

    async def _send_and_stop(self, event: AstrMessageEvent, text: str) -> None:
        """Send the repeated content and stop further processing.

        Uses multiple strategies for AstrBot API compatibility.
        """
        # ---- Strategy 1: reply_event ----
        # TODO: verify AstrBot API — self.context.reply_event() availability.
        if hasattr(self.context, "reply_event"):
            try:
                await self.context.reply_event(event, text)
                # Block downstream stars from processing
                self._stop_event(event)
                return
            except Exception as e:
                logger.debug("context.reply_event failed: %s", e)

        # ---- Strategy 2: set result message ----
        # TODO: verify AstrBot API — event.get_result() and .message
        try:
            result = event.get_result()
            if result is not None:
                if hasattr(result, "message"):
                    result.message = text
                elif hasattr(result, "set_message"):
                    result.set_message(text)

                # Chain result to trigger sending
                self._stop_event(event)
                logger.debug("Repeat-parrot set result.message for channel")
                return
        except Exception as e:
            logger.debug("event.get_result().message failed: %s", e)

        # ---- Strategy 3: fallback log ----
        logger.warning(
            "Repeat-parrot triggered but could not send message in channel %s",
            event.get_group_id(),
        )

    @staticmethod
    def _stop_event(event: AstrMessageEvent) -> None:
        """Call event.stop_event() with AttributeError fallback."""
        try:
            event.stop_event()
        except AttributeError:
            # stop_event not available in this AstrBot version
            pass

    @staticmethod
    def _reset_streak(streaks: Dict[str, Dict[str, Any]], channel_id: str) -> None:
        """Fully reset streak state for a channel."""
        streaks[channel_id] = {
            "count": 0,
            "text": "",
            "users": set(),
            "parroted": False,
        }

    # ------------------------------------------------------------------
    # Handler
    # ------------------------------------------------------------------

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Detect message repeats and echo without LLM processing.

        Pipeline:
          1. Read bot config.
          2. Check repeat state for this channel.
          3. If triggered:
             - Send the repeated content.
             - Stop event to block downstream stars.
             - Reset the channel streak.
          4. On any exception: reset streak and continue.
        """
        channel_id = event.get_group_id()
        if not channel_id:
            return

        try:
            config = self.context.get_config()
            user_id = event.get_sender_id()
            text = event.get_message_str()

            result = self._check_repeat(channel_id, user_id, text, config)
            if result:
                logger.debug("Repeat-parrot triggered in channel %s", channel_id)
                await self._send_and_stop(event, result)
                # Reset streak after successful send
                self._reset_streak(self._streaks, channel_id)
        except Exception:
            logger.debug(
                "Repeat-parrot error, resetting streak for channel %s",
                channel_id,
                exc_info=True,
            )
            self._reset_streak(self._streaks, channel_id)
