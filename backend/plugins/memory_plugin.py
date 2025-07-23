from app.core_logic.knowledge_manager import knowledge_manager
from app.main import load_config
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
import discord

from .base import BasePlugin

class MemoryPlugin(BasePlugin):
    """
    A plugin that provides tools for the LLM to interact with long-term memory and the world book.
    This plugin does not handle messages directly but provides functions for the LLM to call.
    """
    
    async def handle_message(self, message: discord.Message, bot_config: Dict[str, Any]) -> Optional[Tuple[str, List[str]] | bool]:
        # This plugin does not get triggered by user messages, it only provides tools.
        return None

    def get_tools(self) -> List[Dict[str, Any]]:
        """Returns the function definitions for the LLM."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "add_to_memory",
                    "description": "Adds a new piece of information to the long-term memory. Use this to remember key facts about the user or conversation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The information to be remembered."
                            }
                        },
                        "required": ["content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "add_to_world_book",
                    "description": "Adds a new entry to the world book. Use this to record factual information, lore, or settings that can be triggered by keywords.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {
                                "type": "string",
                                "description": "A comma-separated list of keywords that trigger this entry."
                            },
                            "content": {
                                "type": "string",
                                "description": "The content to be injected into the context when a keyword is mentioned."
                            }
                        },
                        "required": ["keywords", "content"]
                    }
                }
            }
        ]

    def get_tool_functions(self) -> Dict[str, callable]:
        """Returns the mapping of function names to their implementations."""
        return {
            "add_to_memory": self.add_to_memory,
            "add_to_world_book": self.add_to_world_book
        }

    def add_to_memory(self, content: str) -> str:
        """
        Adds a new piece of information to the long-term memory.
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            config = load_config()
            bot_nickname = config.get('bot_nickname', 'Bot')
            memory_id = knowledge_manager.add_memory(
                content=content,
                timestamp=timestamp,
                user_id="bot",
                user_name=bot_nickname,
                source="对话"
            )
            return f"Successfully added to memory with ID: {memory_id}"
        except Exception as e:
            return f"Error adding to memory: {e}"

    def add_to_world_book(self, keywords: str, content: str) -> str:
        """
        Adds a new entry to the world book.
        """
        try:
            entry_id = knowledge_manager.add_world_book_entry(keywords=keywords, content=content)
            return f"Successfully added to world book with ID: {entry_id}"
        except Exception as e:
            return f"Error adding to world book: {e}"