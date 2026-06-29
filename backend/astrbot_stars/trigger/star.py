"""Trigger Detection Star (AstrBot v4.26.2).

Determines whether the bot should respond to an incoming message.
Handles: @mention, reply-to-bot, keyword matching.
Auto-interject and repeat-parrot are in separate stars.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class TriggerCheck(star.Star):
    """Detects whether the bot should wake and respond to a message."""

    name = "trigger_check"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)

    # ------------------------------------------------------------------
    # Keyword matching
    # ------------------------------------------------------------------

    @staticmethod
    def _matches_keywords(
        text: str,
        keywords: List[str],
        match_mode: str = "contains",
        case_sensitive: bool = False,
    ) -> bool:
        if not keywords:
            return False
        compare_text = text if case_sensitive else text.lower()

        for kw in keywords:
            compare_kw = kw if case_sensitive else kw.lower()
            if match_mode == "contains" and compare_kw in compare_text:
                return True
            elif match_mode == "exact" and compare_text == compare_kw:
                return True
            elif match_mode == "starts_with" and compare_text.startswith(compare_kw):
                return True
            elif match_mode == "regex":
                try:
                    flags = 0 if case_sensitive else re.IGNORECASE
                    if re.search(kw, text, flags):
                        return True
                except re.error:
                    logger.warning("Invalid regex keyword: %s", kw)
        return False

    # ------------------------------------------------------------------
    # Wake detection
    # ------------------------------------------------------------------

    def _check_should_wake(self, event: AstrMessageEvent, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Determine if the bot should wake and the trigger source."""
        # @mention
        if event.is_at_or_wake_command:
            return True, "mention"

        # Reply-to-bot
        raw_msg = getattr(event, "message_obj", None)
        if raw_msg and hasattr(raw_msg, "raw_message"):
            msg = raw_msg.raw_message
            if hasattr(msg, "reference") and msg.reference:
                ref = msg.reference
                if hasattr(ref, "resolved") and ref.resolved:
                    resolved = ref.resolved
                    bot_id = str(event.get_self_id())
                    if hasattr(resolved, "author") and resolved.author:
                        if bot_id and str(getattr(resolved.author, "id", "")) == bot_id:
                            return True, "reply"

        # Keyword matching
        keywords = config.get("trigger_keywords", [])
        match_mode = config.get("trigger_match_mode", "contains")
        case_sensitive = bool(config.get("trigger_case_sensitive", False))
        text = event.get_message_str()

        if self._matches_keywords(text, keywords, match_mode, case_sensitive):
            return True, "keyword"

        return False, ""

    # ------------------------------------------------------------------
    # User block check
    # ------------------------------------------------------------------

    async def _check_user_blocked(self, event: AstrMessageEvent, config: Dict[str, Any]) -> bool:
        user_options = config.get("user_options", {})
        if not user_options.get("enabled", False):
            return False
        return False  # Implement via internal API

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Check if this message should wake the bot."""
        config = self._get_config(event)
        if not config:
            return

        if await self._check_user_blocked(event, config):
            return

        should_wake, trigger_source = self._check_should_wake(event, config)
        if not should_wake:
            return

        event.set_extra("trigger_source", trigger_source)
        logger.debug("TriggerCheck woke bot: source=%s", trigger_source)

    def _get_config(self, event: AstrMessageEvent) -> Dict[str, Any]:
        try:
            return self.context.get_config(umo=event.unified_msg_origin)
        except Exception:
            return {}
