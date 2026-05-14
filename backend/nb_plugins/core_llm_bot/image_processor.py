from typing import Any, Dict, Optional

from .event_shim import MessageContext
from app.handlers.image_processor import collect_and_download_images as _collect_and_download_images
from app.handlers.image_processor import process_ocr_for_images as _process_ocr_for_images


async def collect_and_download_images(message_ctx: MessageContext) -> list:
    return await _collect_and_download_images(message_ctx)


async def process_ocr_for_images(downloaded_images: list, config: Dict[str, Any], final_formatted_content: str) -> str:
    return await _process_ocr_for_images(downloaded_images, config, final_formatted_content)
