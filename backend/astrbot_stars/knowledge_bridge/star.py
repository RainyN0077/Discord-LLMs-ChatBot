"""Knowledge Bridge Star (AstrBot v4.26.2).

Bridges to the management layer's knowledge base for memory recall,
ingestion, and world book management via internal HTTP API.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote

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
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared aiohttp client session (connection pool reuse)."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def __del__(self) -> None:
        """Best-effort cleanup of the shared session on star destruction."""
        if self._session is not None and not self._session.closed:
            # aiohttp session can be closed in __del__ in simple cases;
            # in advanced usage AstrBot's lifecycle should call terminate().
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._session.close())
                else:
                    loop.run_until_complete(self._session.close())
            except Exception:
                logger.debug("Failed to close aiohttp session on cleanup")

    async def _call_api(self, endpoint: str, method: str = "GET",
                        payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call the management-layer internal API with connection-pool reuse."""
        config = self.context.get_config()
        internal = config.get("internal_api", {})
        base_url = internal.get("base_url", "http://127.0.0.1:8093/internal")
        token = internal.get("secret_token", "")
        bot_id = config.get("bot_id", "")

        url = f"{base_url}/{bot_id}/{endpoint}"
        headers = {"X-Internal-Token": token, "X-Bot-Id": bot_id}

        try:
            session = await self._get_session()
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
        """Hook for knowledge recall during message processing.

        Retrieves relevant memories from the knowledge base via IPC, and
        injects them into the event extras for downstream stars
        (e.g. context_assembler) to consume.

        Never blocks the main pipeline — on any failure, sets
        ``event.set_extra("memories", [])`` and logs a warning.
        """
        config = self.context.get_config()
        query = event.get_message_str()

        # Early exit for empty queries — no point hitting the API
        if not query:
            event.set_extra("memories", [])
            return

        # ---- Parse recall parameters from config with safe bounds ----
        # Pattern matches pipeline.py lines 71-81 for consistent bounds.
        try:
            recall_top_k = max(1, min(50, int(config.get("knowledge", {}).get(
                "recall_top_k", config.get("auto_memory_recall_top_k", 12)))))
        except (TypeError, ValueError):
            recall_top_k = 12
            logger.debug("Fell back to default recall_top_k=12")

        try:
            recall_char_limit = max(300, min(20000, int(config.get("knowledge", {}).get(
                "recall_char_limit", config.get("auto_memory_recall_char_limit", 2200)))))
        except (TypeError, ValueError):
            recall_char_limit = 2200
            logger.debug("Fell back to default recall_char_limit=2200")

        try:
            recall_max_age_days = max(1, min(3650, int(config.get("knowledge", {}).get(
                "recall_max_age_days", config.get("auto_memory_recall_max_age_days", 365)))))
        except (TypeError, ValueError):
            recall_max_age_days = 365
            logger.debug("Fell back to default recall_max_age_days=365")

        # ---- Build recall query with all parameters ----
        endpoint = (
            f"knowledge/recall"
            f"?query={quote(query, safe='')}"
            f"&top_k={recall_top_k}"
            f"&char_limit={recall_char_limit}"
            f"&max_age_days={recall_max_age_days}"
        )

        # ---- Recall with error degradation ----
        # _call_api already returns {} on HTTP/network errors, but we add
        # an outer try/except for defence-in-depth against unexpected issues.
        try:
            result = await self._call_api(endpoint)
            memories: List[Dict[str, Any]] = result.get("memories", [])
        except Exception as e:
            logger.warning("Knowledge recall failed, falling back to empty memories: %s", e)
            memories = []

        # ---- Inject into event extras for downstream stars ----
        # TODO: verify AstrBot API — event.set_extra should be available.
        event.set_extra("memories", memories)

        if memories:
            logger.info("Recalled %d memories for query (%d chars, top_k=%d, "
                        "char_limit=%d, max_age_days=%d)",
                        len(memories), len(query),
                        recall_top_k, recall_char_limit, recall_max_age_days)
        else:
            logger.debug("No memories recalled for query (%d chars)", len(query))
