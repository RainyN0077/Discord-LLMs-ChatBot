import logging
import re
from datetime import timezone
from typing import Any, Dict

from .core_shared import (
    INSTANCE_ID,
    token_calculator,
    strip_thinking_sections,
    strip_dsml_tool_blocks,
    contains_dsml_tool_blocks,
    _parse_user_info_fields,
    _try_acquire_bot_process_lock,
    _release_bot_process_lock,
)
from .core_logic.knowledge_manager import get_knowledge_manager

logger = logging.getLogger(__name__)


async def process_knowledge_tags(message: Any, text: str, bot_config: Dict[str, Any]) -> str:
    if not text:
        return text

    cleaned_text = text

    if '<memory>' in text:
        memories_to_add = re.findall(r'<memory>(.*?)</memory>', text, re.DOTALL)
        for memory_content in memories_to_add:
            stripped_content = memory_content.strip()
            if stripped_content:
                timestamp = getattr(message, 'created_at', None)
                if timestamp:
                    timestamp = timestamp.astimezone(timezone.utc).isoformat()
                user_id = str(getattr(message.author, 'id', 'unknown'))
                user_name = getattr(message.author, 'name', 'unknown')
                try:
                    ingest_result = get_knowledge_manager().ingest_memory_candidate(
                        content=stripped_content,
                        timestamp=timestamp,
                        user_id=user_id,
                        user_name=user_name,
                        source='ai_tag',
                        config=bot_config,
                        channel_id=str(getattr(message.channel, 'id', '')),
                    )
                    status = ingest_result.get("status")
                    if status == "promoted":
                        logger.info("Promoted memory candidate from <memory> tag by '%s' as memory ID: %s",
                                   user_name, ingest_result.get("memory_id"))
                    elif status == "staged":
                        logger.info("Staged memory candidate from <memory> tag by '%s' (candidate ID: %s).",
                                   user_name, ingest_result.get("candidate_id"))
                except Exception as e:
                    logger.error(f"Error adding memory from tag by '{user_name}': {e}", exc_info=True)
        cleaned_text = re.sub(r'<memory>.*?</memory>', '', cleaned_text, flags=re.DOTALL)

    if '<user_info' in cleaned_text:
        user_info_tags = re.findall(r'<user_info\b(.*?)</user_info>', cleaned_text, re.DOTALL)
        for inner_text in user_info_tags:
            inner_text = inner_text.strip()
            if not inner_text:
                continue
            parsed = _parse_user_info_fields(inner_text)
            if not parsed:
                continue
            uid = parsed.get("id")
            keywords = parsed.get("keywords", "")
            content = parsed.get("content", "")
            if not content.strip():
                continue
            try:
                get_knowledge_manager().add_world_book_entry(
                    keywords=keywords,
                    content=content,
                    linked_user_id=uid,
                    source="ai_tag",
                )
                logger.info("Added world book entry from <user_info> tag: user=%s, keywords=%s",
                           uid or "none", keywords[:80])
            except Exception as e:
                logger.error(f"Error adding world book entry from <user_info> tag: {e}", exc_info=True)
        cleaned_text = re.sub(r'<user_info\b.*?</user_info>', '', cleaned_text, flags=re.DOTALL)

    return cleaned_text.strip()
