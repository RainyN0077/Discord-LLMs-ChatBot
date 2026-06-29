"""Streaming Response Star (AstrBot v4.26.2).

Post-processes LLM responses: strips <thinking> sections, DSML tool blocks,
and splits long messages for Discord's 2000-char limit.
"""

import logging
import re
from typing import List

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)

DISCORD_MESSAGE_LIMIT = 2000


class StreamingRespond(star.Star):
    """Cleans and formats LLM responses for Discord."""

    name = "streaming_respond"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)

    @staticmethod
    def strip_thinking_sections(text: str) -> str:
        return re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL).strip()

    @staticmethod
    def contains_dsml_tool_blocks(text: str) -> bool:
        patterns = [r'<function_call>', r'<tool_call>', r'<dsml_', r'<\?xml.*?<function_call']
        return any(re.search(p, text, re.IGNORECASE | re.DOTALL) for p in patterns)

    @staticmethod
    def strip_dsml_tool_blocks(text: str) -> str:
        text = re.sub(r'<\?xml.*?</function_call>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<function_call>.*?</function_call>', '', text, flags=re.DOTALL)
        text = re.sub(r'<tool_call>.*?</tool_call>', '', text, flags=re.DOTALL)
        text = re.sub(r'<dsml_.*?>.*?</dsml_.*?>', '', text, flags=re.DOTALL)
        text = re.sub(r'<\?xml.*?(?=<|$)', '', text, flags=re.DOTALL)
        text = re.sub(r'<function_call>.*?(?=<|$)', '', text, flags=re.DOTALL)
        return text.strip()

    @staticmethod
    def split_message(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> List[str]:
        if len(text) <= limit:
            return [text]
        chunks = []
        remaining = text
        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break
            split_pos = limit
            newline_pos = remaining.rfind('\n', 0, limit)
            if newline_pos > limit // 2:
                split_pos = newline_pos
            else:
                space_pos = remaining.rfind(' ', 0, limit)
                if space_pos > limit // 2:
                    split_pos = space_pos
            chunks.append(remaining[:split_pos])
            remaining = remaining[split_pos:].lstrip()
        return chunks

    @staticmethod
    def clean_response(text: str) -> str:
        text = StreamingRespond.strip_thinking_sections(text)
        text = StreamingRespond.strip_dsml_tool_blocks(text)
        return text.strip()

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Post-process any response in the event."""
        result = event.get_result()
        if result and hasattr(result, "message"):
            msg = result.message
            if isinstance(msg, str):
                result.message = self.clean_response(msg)
