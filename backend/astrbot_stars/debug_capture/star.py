"""Debug Capture Star (AstrBot v4.26.2)."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class DebugCapture(star.Star):
    """Captures LLM pipeline state for debugging."""

    name = "debug_capture"
    author = "Discord-LLMs-ChatBot"

    _captures: Dict[str, List[Dict[str, Any]]] = {}
    _max_captures: int = 50

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Capture pipeline state."""
        pass  # Deferred: full capture implementation

    @staticmethod
    def get_captures(channel_id: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        if channel_id:
            captures = DebugCapture._captures.get(channel_id, [])
        else:
            captures = []
            for caps in DebugCapture._captures.values():
                captures.extend(caps)
        captures.sort(key=lambda c: c.get("timestamp", ""), reverse=True)
        return captures[:limit]
