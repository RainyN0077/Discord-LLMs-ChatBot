"""Post-Process Star (AstrBot v4.26.2).

Handles <memory> and <user_info> tags in LLM responses, bridging to the
management layer's knowledge base via internal HTTP API.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict

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
        """Process response text for knowledge tags."""
        result = event.get_result()
        if not result or not hasattr(result, "message"):
            return
        text = result.message
        if not isinstance(text, str) or not text:
            return

        # Strip <memory> tags
        for match in MEMORY_TAG_RE.finditer(text):
            memory_content = match.group(1).strip()
            if memory_content:
                logger.debug("Memory tag found: %s...", memory_content[:80])
                # TODO: POST to internal API for ingestion

        # Strip <user_info> tags
        for match in USER_INFO_TAG_RE.finditer(text):
            inner_text = match.group(1).strip()
            if inner_text:
                parsed = self._parse_user_info_fields(inner_text)
                if parsed.get("content"):
                    logger.debug("User_info tag found: keywords=%s", parsed.get("keywords", "")[:80])
                    # TODO: POST to internal API for world book

        # Clean tags from text
        cleaned = MEMORY_TAG_RE.sub('', text)
        cleaned = USER_INFO_TAG_RE.sub('', cleaned)
        result.message = cleaned.strip()
