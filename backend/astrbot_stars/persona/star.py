"""Persona Star (AstrBot v4.26.2).

Retrieves and injects user persona data into the LLM context.
"""

import logging
from typing import Any, Dict

import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class Persona(star.Star):
    """Retrieves user persona from management layer."""

    name = "persona"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Inject persona for the message sender."""
        config = self.context.get_config()
        internal = config.get("internal_api", {})
        if not internal:
            return

        user_id = event.get_sender_id()
        base_url = internal.get("base_url", "http://127.0.0.1:8093/internal")
        token = internal.get("secret_token", "")
        bot_id = config.get("bot_id", "")

        try:
            async with aiohttp.ClientSession() as session:
                url = f"{base_url}/{bot_id}/persona/{user_id}"
                headers = {"X-Internal-Token": token, "X-Bot-Id": bot_id}
                async with session.get(url, headers=headers,
                                       timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        persona_data = await resp.json()
                        event.set_extra("user_persona", persona_data)
        except Exception as e:
            logger.debug("Persona fetch failed: %s", e)
