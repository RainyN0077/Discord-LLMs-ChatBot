"""Memory Tools Star (AstrBot v4.26.2).

Provides LLM tool definitions: add_to_memory, recall_memory, add_to_world_book.
"""

from typing import Any, Dict, List

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter


class MemoryTools(star.Star):
    """Provides memory management tool definitions for the LLM."""

    name = "memory_tools"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)

    @staticmethod
    def get_tool_definitions() -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "add_to_memory",
                    "description": "Remember important facts, user preferences, or notable events.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "Content to remember."},
                            "importance": {
                                "type": "string", "enum": ["low", "medium", "high"],
                                "description": "Importance level.", "default": "medium",
                            },
                        },
                        "required": ["content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "recall_memory",
                    "description": "Search memory for relevant information.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string", "description": "Search query."}},
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_to_world_book",
                    "description": "Add world knowledge for consistent lore/facts.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {"type": "string", "description": "Comma-separated trigger keywords."},
                            "content": {"type": "string", "description": "Knowledge content."},
                        },
                        "required": ["keywords", "content"],
                    },
                },
            },
        ]

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Register tool definitions for this message."""
        pass  # Tools registered via AstrBot's tool manager
