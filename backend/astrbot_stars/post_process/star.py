"""Post-Process Star (AstrBot v4.26.2).

Handles <memory> and <user_info> tags in LLM responses, bridging to the
management layer's knowledge base via internal HTTP API.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)

MEMORY_TAG_RE = re.compile(r'<memory>(.*?)</memory>', re.DOTALL)
USER_INFO_TAG_RE = re.compile(r'<user_info\b(.*?)</user_info>', re.DOTALL)


class PostProcess(star.Star):
    """Post-processes LLM responses to extract and ingest knowledge tags."""

    name = "post_process"
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
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._session.close())
                else:
                    loop.run_until_complete(self._session.close())
            except Exception:
                logger.debug("Failed to close aiohttp session on cleanup")

    async def _call_api(self, endpoint: str, method: str = "POST",
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
            logger.debug("PostProcess API %s %s: %s", method, endpoint, e)
            return {}

    @staticmethod
    def _parse_user_info_fields(inner_text: str) -> Dict[str, Any]:
        result = {"id": None, "keywords": "", "content": ""}
        tag_match = re.match(r'^([^>]*)>?\s*(.*)', inner_text, re.DOTALL)
        if not tag_match:
            return result
        attrs_text = tag_match.group(1).strip()
        result["content"] = tag_match.group(2).strip()
        id_match = re.search(r'id\s*=\s*"([^"]*)"', attrs_text)
        if id_match:
            result["id"] = id_match.group(1)
        kw_match = re.search(r'keywords\s*=\s*"([^"]*)"', attrs_text)
        if kw_match:
            result["keywords"] = kw_match.group(1)
        return result

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Process response text for knowledge tags.

        Extracts <memory> and <user_info> tags, ingests them via the
        management-layer knowledge API, and strips the tags from the
        final response text.

        Never blocks the main pipeline — ingest failures are logged
        and the tags are still stripped from the response.
        """
        result = event.get_result()
        if not result or not hasattr(result, "message"):
            return
        text = result.message
        if not isinstance(text, str) or not text:
            return

        # ---- Collect sender/channel info from event ----
        # TODO: verify AstrBot API — event.get_sender_id() etc. should be available.
        user_id = event.get_sender_id() if hasattr(event, "get_sender_id") else "unknown"
        user_name = event.get_sender_name() if hasattr(event, "get_sender_name") else ""
        channel_id = event.get_group_id() if hasattr(event, "get_group_id") else ""
        if not channel_id:
            channel_id = event.get_session_id() if hasattr(event, "get_session_id") else ""
        timestamp = datetime.now(timezone.utc).isoformat()

        cleaned = text

        # ---- Process <memory> tags ----
        for match in MEMORY_TAG_RE.finditer(cleaned):
            memory_content = match.group(1).strip()
            if not memory_content:
                continue
            logger.debug("Memory tag found: %s...", memory_content[:80])
            try:
                await self._call_api(
                    "knowledge/ingest",
                    payload={
                        "type": "memory",
                        "content": memory_content,
                        "timestamp": timestamp,
                        "user_id": user_id,
                        "user_name": user_name,
                        "source": "ai_tag",
                        "channel_id": channel_id,
                    },
                )
            except Exception as e:
                # Ingest failure never blocks the response.
                logger.warning("Failed to ingest <memory> tag: %s", e)

        # ---- Process <user_info> tags ----
        for match in USER_INFO_TAG_RE.finditer(cleaned):
            inner_text = match.group(1).strip()
            if not inner_text:
                continue
            parsed = self._parse_user_info_fields(inner_text)
            content = parsed.get("content", "")
            if not content:
                continue
            keywords = parsed.get("keywords", "")
            linked_user_id = parsed.get("id")
            logger.debug("User_info tag found: keywords=%s", keywords[:80])
            try:
                await self._call_api(
                    "knowledge/ingest",
                    payload={
                        "type": "world_book",
                        "keywords": keywords,
                        "content": content,
                        "linked_user_id": linked_user_id,
                        "source": "ai_tag",
                    },
                )
            except Exception as e:
                logger.warning("Failed to ingest <user_info> tag: %s", e)

        # ---- Strip all tags from the final response text ----
        cleaned = MEMORY_TAG_RE.sub('', cleaned)
        cleaned = USER_INFO_TAG_RE.sub('', cleaned)
        result.message = cleaned.strip()
