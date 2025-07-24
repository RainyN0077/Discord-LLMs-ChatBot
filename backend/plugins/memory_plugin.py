from app.core_logic.knowledge_manager import knowledge_manager
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
import discord
import re

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
                    "description": "Adds a new entry to the world book. Use this to record factual information, lore, or settings that can be triggered by keywords. IMPORTANT: If the knowledge is about a specific person, provide their name in 'subject_of_knowledge'. For general facts (e.g., 'Tokyo is the capital of Japan'), leave it empty.",
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
                            },
                            "subject_of_knowledge": {
                                "type": "string",
                                "description": "The name of the person this knowledge is about. Leave empty for general facts."
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

    def add_to_memory(self, content: str, user_id: str, user_name: str) -> str:
        """
        Adds a new piece of information to the long-term memory.
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            memory_id = knowledge_manager.add_memory(
                content=content,
                timestamp=timestamp,
                user_id=user_id,
                user_name=user_name,
                source="对话"
            )
            # Return a simple, neutral message to avoid confusing the LLM into a loop.
            # The detailed log is already printed on the server side if needed.
            return "OK"
        except Exception as e:
            logger.error(f"Error in add_to_memory tool: {e}", exc_info=True)
            # Return a descriptive error for the LLM's context, but keep it simple.
            return f"Error: {e}"

    def _get_cleaned_string_list(self, data: Any) -> List[str]:
        """Safely converts a string or list of strings into a cleaned list of lowercased strings."""
        if not data:
            return []
        if isinstance(data, str):
            # Replace full-width Chinese commas with half-width English commas before splitting
            normalized_data = data.replace('，', ',')
            return [item.strip().lower() for item in normalized_data.split(',') if item.strip()]
        if isinstance(data, list):
            return [str(item).strip().lower() for item in data if str(item).strip()]
        return []

    def add_to_world_book(self, keywords: str, content: str, subject_of_knowledge: Optional[str] = None, message: Optional[discord.Message] = None, config: Optional[Dict[str, Any]] = None) -> str:
        """
        Adds a new entry to the world book, trying to link it to a user if a subject is provided.
        """
        if not message or not config:
            return "Error: Could not add to world book because message context or config is missing."

        linked_user_id = None
        user_search_log = ""

        if subject_of_knowledge:
            subject_name_lower = subject_of_knowledge.lower().strip()
            found_user = None

            # 1. Check mentions first (most accurate)
            for user in message.mentions:
                if user.name.lower() == subject_name_lower or (hasattr(user, 'nick') and user.nick and user.nick.lower() == subject_name_lower):
                    found_user = user
                    break
            
            # 2. If not in mentions, search the guild members by name/nickname
            if not found_user and message.guild:
                for member in message.guild.members:
                    if member.name.lower() == subject_name_lower or (member.nick and member.nick.lower() == subject_name_lower):
                        found_user = member
                        break

            # 3. If still not found, search by user persona name or trigger keywords
            if not found_user:
                user_personas = config.get("user_personas", {})
                for uid, persona_data in user_personas.items():
                    names_to_check = self._get_cleaned_string_list(persona_data.get('name'))
                    triggers_to_check = self._get_cleaned_string_list(persona_data.get('trigger_keywords'))

                    if subject_name_lower in names_to_check or subject_name_lower in triggers_to_check:
                        if message.guild:
                           found_user = message.guild.get_member(int(uid))
                        if found_user:
                            break
            
            if found_user:
                linked_user_id = str(found_user.id)
                user_search_log = f"Knowledge successfully linked to user '{found_user.display_name}' (ID: {linked_user_id}) based on subject '{subject_of_knowledge}'."
            else:
                user_search_log = f"Could not find a user matching '{subject_of_knowledge}'. Entry will be saved as general knowledge."

        try:
            entry_id = knowledge_manager.add_world_book_entry(
                keywords=keywords,
                content=content,
                linked_user_id=linked_user_id
            )
            success_message = f"Successfully added to world book with ID: {entry_id}."
            return f"{success_message} {user_search_log}".strip()
        except Exception as e:
            return f"Error adding to world book: {e}"