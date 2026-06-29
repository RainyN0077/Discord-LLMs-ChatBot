"""Repeat-Parrot Star (AstrBot v4.26.2).

Detects N consecutive identical messages from different users and echoes back.
"""

import logging
from typing import Any, Dict

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class RepeatParrot(star.Star):
    """Detects message repetition streaks and echoes back."""

    name = "repeat_parrot"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        self._streaks: Dict[str, Dict[str, Any]] = {}

    def _check_repeat(self, channel_id: str, user_id: str, text: str,
                      config: Dict[str, Any]) -> str:
        if not config.get("repeat_parrot_enabled", False):
            return ""
        threshold = int(config.get("repeat_parrot_threshold", 3))
        case_sensitive = bool(config.get("repeat_parrot_case_sensitive", False))
        trim_ws = bool(config.get("repeat_parrot_trim_whitespace", True))
        min_length = int(config.get("repeat_parrot_min_length", 2))
        require_multi = bool(config.get("repeat_parrot_require_multiple_users", True))

        if len(text.strip()) < min_length:
            return ""

        normalized = text.strip() if trim_ws else text
        if not case_sensitive:
            normalized = normalized.lower()

        streak = self._streaks.get(channel_id, {"count": 0, "text": "", "users": set()})
        if normalized == streak["text"]:
            streak["count"] += 1
            streak["users"].add(user_id)
        else:
            streak = {"count": 1, "text": normalized, "users": {user_id}}

        self._streaks[channel_id] = streak

        if streak["count"] >= threshold:
            if not require_multi or len(streak["users"]) >= 2:
                self._streaks[channel_id] = {"count": 0, "text": "", "users": set()}
                return text
        return ""

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        config = self.context.get_config()
        channel_id = event.get_group_id()
        user_id = event.get_sender_id()
        text = event.get_message_str()
        result = self._check_repeat(channel_id, user_id, text, config)
        if result:
            logger.debug("Repeat-parrot triggered in channel %s", channel_id)
