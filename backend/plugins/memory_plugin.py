from app.core_logic.knowledge_manager import knowledge_manager
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
import discord
import re
import logging
import json
from difflib import SequenceMatcher

from .base import BasePlugin

logger = logging.getLogger(__name__)

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

    def _is_duplicate(self, new_content: str, existing_entries: List[Dict[str, Any]], threshold: float, content_key: str) -> bool:
        """Checks for duplicate content based on a similarity threshold."""
        if not threshold or threshold <= 0:
            return False
        
        for entry in existing_entries:
            existing_content = entry.get(content_key)
            if not existing_content:
                continue
            
            similarity = SequenceMatcher(None, new_content, existing_content).ratio()
            
            if similarity >= threshold:
                logger.info(f"Duplicate found for content '{new_content[:50]}...'. Similarity {similarity:.2f} >= threshold {threshold:.2f} with existing entry ID: {entry.get('id')}")
                return True
                
        return False

    def add_to_memory(self, content: str, message: Optional[discord.Message] = None, config: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        """
        Adds a new piece of information to the long-term memory.
        """
        if not message or not config: return json.dumps({"status": "error", "message": "Missing context."})

        try:
            threshold = config.get("behavior", {}).get("memory_dedup_threshold", 0.0)
            if threshold > 0:
                all_memories = knowledge_manager.get_all_memories()
                if self._is_duplicate(content, all_memories, threshold, 'content'):
                    return json.dumps({"status": "duplicate_found", "message": "A similar memory entry already exists."})

            timestamp = datetime.now(timezone.utc).isoformat()
            memory_id = knowledge_manager.add_memory(
                content=content,
                timestamp=timestamp,
                user_id=str(message.author.id),
                user_name=message.author.display_name,
                source="对话"
            )
            return json.dumps({"status": "success", "id": memory_id, "message": f"Successfully added to memory with ID: {memory_id}."})
        except Exception as e:
            logger.error(f"Error in add_to_memory tool: {e}", exc_info=True)
            return json.dumps({"status": "error", "message": str(e)})

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

    def add_to_world_book(self, keywords: str, content: str, subject_of_knowledge: Optional[str] = None, message: Optional[discord.Message] = None, config: Optional[Dict[str, Any]] = None, user_id: Optional[str] = None, user_name: Optional[str] = None, **kwargs) -> str:
        """
        Adds a new entry to the world book, trying to link it to a user if a subject is provided.
        """
        if not message or not config:
            return json.dumps({"status": "error", "message": "Missing context."})

        try:
            threshold = config.get("behavior", {}).get("world_book_dedup_threshold", 0.0)
            if threshold > 0:
                all_entries = knowledge_manager.get_all_world_book_entries()
                if self._is_duplicate(content, all_entries, threshold, 'content'):
                    return json.dumps({"status": "duplicate_found", "message": "A similar world book entry already exists."})

            linked_user_id = None
            user_search_log = ""

            if subject_of_knowledge:
                subject_name_lower = subject_of_knowledge.lower().strip()
                found_user = None

                for user in message.mentions:
                    if user.name.lower() == subject_name_lower or (hasattr(user, 'nick') and user.nick and user.nick.lower() == subject_name_lower):
                        found_user = user
                        break
                
                if not found_user and message.guild:
                    for member in message.guild.members:
                        if member.name.lower() == subject_name_lower or (member.nick and member.nick.lower() == subject_name_lower):
                            found_user = member
                            break

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
                    user_search_log = f"Knowledge successfully linked to user '{found_user.display_name}' (ID: {linked_user_id})."
                else:
                    user_search_log = f"Could not find a user matching '{subject_of_knowledge}'."

            entry_id = knowledge_manager.add_world_book_entry(
                keywords=keywords,
                content=content,
                linked_user_id=linked_user_id,
                source=f"由 {user_name} (ID: {user_id}) 添加" if user_id and user_name else "未知来源"
            )
            success_message = f"Successfully added to world book with ID: {entry_id}."
            final_message = f"{success_message} {user_search_log}".strip()
            return json.dumps({"status": "success", "id": entry_id, "message": final_message})
        except Exception as e:
            logger.error(f"Error in add_to_world_book tool: {e}", exc_info=True)
            return json.dumps({"status": "error", "message": str(e)})