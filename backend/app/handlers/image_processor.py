import asyncio
import logging
from typing import Any, Dict, List, Optional

import discord

from ..ocr_service import get_ocr_timeout_seconds, has_ocr_model_config, extract_ocr_text
from ..utils import download_image

logger = logging.getLogger(__name__)


def collect_image_descriptors(msg: discord.Message, source_label: str) -> List[Dict[str, str]]:
    descriptors: List[Dict[str, str]] = []

    def add_descriptor(url: Optional[str], kind: str) -> None:
        if not url:
            return
        descriptors.append({
            "url": str(url),
            "kind": kind,
            "source": str(source_label),
        })

    for attachment in msg.attachments:
        content_type = str(attachment.content_type or "").lower()
        ct = content_type.split(";")[0].strip()
        if ct and (ct.startswith("image/") or ct in {"application/pdf"}):
            add_descriptor(attachment.url, "attachment")

    for embed in msg.embeds:
        if embed.type == "image" and embed.url:
            add_descriptor(embed.url, "embed")
        elif embed.thumbnail and embed.thumbnail.url:
            add_descriptor(embed.thumbnail.url, "embed_thumbnail")
        elif embed.image and embed.image.url:
            add_descriptor(embed.image.url, "embed_image")

    for sticker in (msg.stickers or []):
        if hasattr(sticker, "url") and sticker.url:
            add_descriptor(sticker.url, "sticker")

    custom_emoji_pattern = r'<(a?:\w+:\d+)>'
    import re
    for match in re.finditer(custom_emoji_pattern, msg.content or ""):
        emoji_str = match.group(1)
        parts = emoji_str.split(":")
        if len(parts) >= 3:
            emoji_id = parts[2]
            animated_prefix = "a_" if parts[0].startswith("a") else ""
            url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png"
            add_descriptor(url, "custom_emoji")

    return descriptors


async def collect_and_download_images(message: discord.Message) -> List[Dict[str, Any]]:
    image_descriptors = collect_image_descriptors(message, "Current message")
    if message.reference and isinstance(message.reference.resolved, discord.Message):
        replied_msg = message.reference.resolved
        replied_images = collect_image_descriptors(replied_msg, f"Replied message from {replied_msg.author}")
        image_descriptors.extend(replied_images)
        if replied_images:
            logger.info(f"Found {len(replied_images)} images in replied message from {replied_msg.author}")

    seen_urls: set = set()
    downloaded_images: List[Dict[str, Any]] = []
    for descriptor in image_descriptors:
        url = descriptor["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        img_data = await download_image(url)
        if img_data:
            downloaded_images.append({**descriptor, "bytes": img_data})
            logger.info(f"Successfully downloaded image from {url}")
    return downloaded_images


async def process_ocr_for_images(
    downloaded_images: List[Dict[str, Any]],
    config: Dict[str, Any],
    final_formatted_content: str,
) -> str:
    image_attachments = [
        {"bytes": img["bytes"], "label": img.get("label", img.get("source", "image"))}
        for img in downloaded_images
    ]
    if has_ocr_model_config(config):
        timeout_seconds = get_ocr_timeout_seconds(config)
        try:
            extraction_task = extract_ocr_text(image_attachments, config)
            if timeout_seconds is None:
                ocr_text, _ = await extraction_task
            else:
                ocr_text, _ = await asyncio.wait_for(extraction_task, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            ocr_text = "OCR timed out. You did not successfully obtain image content. Please reply to the user normally and tell them you cannot see images right now."
        except Exception:
            ocr_text = "OCR failed. You did not successfully obtain image content. Please reply to the user normally and tell them you cannot see images right now."
    else:
        ocr_text = "Images were attached, but OCR is not configured for the current text-only LLM."

    if ocr_text and ocr_text.strip():
        ocr_block = f"[Image OCR Context]\n<ocr_output>\n{ocr_text}\n</ocr_output>"
        return f"{final_formatted_content}\n\n{ocr_block}" if final_formatted_content else ocr_block
    return final_formatted_content
