"""Knowledge Bridge Star (AstrBot v4.26.2).

Bridges to the management layer's knowledge base for memory recall,
ingestion, and world book management via internal HTTP API.
"""

import logging
from typing import Any, Dict

import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class KnowledgeBridge(star.Star):
    """Memory recall/ingest bridge to management layer."""

    name = "knowledge_bridge"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)

    async def _call_api(self, endpoint: str, method: str = "GET",
                        payload: Dict[str, Any] = None) -> Dict[str, Any]:
        config = self.context.get_config()
        internal = config.get("internal_api", {})
        base_url = internal.get("base_url", "http://127.0.0.1:8093/internal")
        token = internal.get("secret_token", "")
        bot_id = config.get("bot_id", "")

        url = f"{base_url}/{bot_id}/{endpoint}"
        headers = {"X-Internal-Token": token, "X-Bot-Id": bot_id}

        try:
            async with aiohttp.ClientSession() as session:
                if method == "POST":
                    async with session.post(url, json=payload or {}, headers=headers,
                                            timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        return await resp.json() if resp.status == 200 else {}
                else:
                    async with session.get(url, headers=headers,
                                           timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        return await resp.json() if resp.status == 200 else {}
        except Exception as e:
            logger.debug("Knowledge API %s %s: %s", method, endpoint, e)
            return {}

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Hook for knowledge recall during message processing."""
        config = self.context.get_config()
        query = event.get_message_str()

        from urllib.parse import quote
        result = await self._call_api(
            f"knowledge/recall?query={quote(query, safe='')}"
        )
        memories = result.get("memories", [])
        if memories:
            logger.debug("Recalled %d memories for query", len(memories))
