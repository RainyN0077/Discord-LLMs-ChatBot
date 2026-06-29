"""OCR Image Star (AstrBot v4.26.2).

Handles image attachment extraction and download for LLM vision/OCR.
"""

import logging
from typing import Any, Dict, List

import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class OCRImage(star.Star):
    """Processes image attachments for LLM consumption."""

    name = "ocr_image"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Extract images from message attachments."""
        images = await self._extract_images(event)
        if images:
            event.set_extra("downloaded_images", images)
            logger.debug("Extracted %d images from message", len(images))

    async def _extract_images(self, event: AstrMessageEvent) -> List[Dict[str, Any]]:
        images = []
        msg_obj = getattr(event, "message_obj", None)
        if not msg_obj:
            return images

        raw_msg = getattr(msg_obj, "raw_message", None)
        if not raw_msg:
            return images

        attachments = getattr(raw_msg, "attachments", []) or []
        for att in attachments:
            content_type = getattr(att, "content_type", "") or ""
            url = getattr(att, "url", "") or ""
            filename = getattr(att, "filename", "") or ""

            if not url:
                continue
            is_image = content_type.startswith("image/") or any(
                filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"]
            )
            if is_image:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                            if resp.status == 200:
                                images.append({
                                    "url": url, "bytes": await resp.read(),
                                    "filename": filename, "content_type": content_type,
                                })
                except Exception as e:
                    logger.warning("Failed to download image %s: %s", url, e)
        return images
