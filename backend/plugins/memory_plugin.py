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
    """
    
    async def handle_message(self, message: discord.Message, bot_config: Dict[str, Any]) -> Optional[Tuple[str, List[str]] | bool]:
        return None

    def get_tools(self, bot_config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        knowledge_source_mode = bot_config.get("behavior", {}).get("knowledge_source_mode", "static_portrait")

        if knowledge_source_mode == 'dynamic_learning':
            return self.get_dynamic_mode_tools()
        else:
            return self.get_static_mode_tools()

    def get_static_mode_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function", "function": {
                    "name": "add_to_memory", "description": "Adds a new piece of information to the long-term memory for conversational recall.",
                    "parameters": {"type": "object", "properties": {"content": {"type": "string", "description": "The information to be remembered."}}, "required": ["content"]}
                }
            },
            {
                "type": "function", "function": {
                    "name": "add_to_world_book", "description": "Adds a new entry to the world book for general facts or lore.",
                    "parameters": {
                        "type": "object", "properties": {
                            "keywords": {"type": "string", "description": "Comma-separated keywords that trigger this entry."},
                            "content": {"type": "string", "description": "The content to be injected into the context."},
                            "subject_of_knowledge": {"type": "string", "description": "Optional: Name of a third-party this knowledge is about."}
                        }, "required": ["keywords", "content"]
                    }
                }
            }
        ]

    def get_dynamic_mode_tools(self) -> List[Dict[str, Any]]:
        return [
            # World Book Tools
            {
                "type": "function", "function": {
                    "name": "create_or_update_user_portrait", "description": "Creates or updates a user's portrait. Use this to manage all structured knowledge about specific users.",
                    "parameters": {
                        "type": "object", "properties": {
                            "user_id": {"type": "string", "description": "The Discord User ID of the person this portrait is about."},
                            "core_content": {"type": "string", "description": "The main descriptive text about the user. Replaces existing content."},
                            "keywords_to_add": {"type": "array", "items": {"type": "string"}, "description": "A list of general keywords to add."}, "keywords_to_remove": {"type": "array", "items": {"type": "string"}, "description": "A list of general keywords to remove."},
                            "aliases_to_add": {"type": "array", "items": {"type": "string"}, "description": "A list of nicknames or aliases to add for the user."}, "aliases_to_remove": {"type": "array", "items": {"type": "string"}, "description": "A list of nicknames or aliases to remove."},
                            "triggers_to_add": {"type": "array", "items": {"type": "string"}, "description": "A list of dedicated trigger words to add."}, "triggers_to_remove": {"type": "array", "items": {"type": "string"}, "description": "A list of dedicated trigger words to remove."}
                        }, "required": ["user_id"]
                    }
                }
            },
            {
                "type": "function", "function": {
                    "name": "find_user_portrait", "description": "Finds a user's portrait by their User ID.",
                    "parameters": {"type": "object", "properties": {"user_id": {"type": "string", "description": "The Discord User ID to search for."}}, "required": ["user_id"]}
                }
            },
            # Memory Bank Tools
            {
                "type": "function", "function": {
                    "name": "add_to_memory", "description": "Adds a new conversational note or event to the memory bank.",
                    "parameters": {"type": "object", "properties": {"content": {"type": "string", "description": "The information to be remembered."}}, "required": ["content"]}
                }
            },
            {
                "type": "function", "function": {
                    "name": "find_memories", "description": "Searches the memory bank for entries matching a query.",
                    "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "The keyword or topic to search for in memories."}}, "required": ["query"]}
                }
            },
            {
                "type": "function", "function": {
                    "name": "update_memory", "description": "Updates an existing memory entry by its ID. Get the ID from `find_memories`.",
                    "parameters": { "type": "object", "properties": {
                            "memory_id": {"type": "integer", "description": "The ID of the memory to update."},
                            "new_content": {"type": "string", "description": "The new content for the memory."}
                        }, "required": ["memory_id", "new_content"]
                    }
                }
            },
            {
                "type": "function", "function": {
                    "name": "delete_memory", "description": "Deletes an existing memory entry by its ID. Use with caution.",
                    "parameters": {"type": "object", "properties": {"memory_id": {"type": "integer", "description": "The ID of the memory to delete."}}, "required": ["memory_id"]}
                }
            }
        ]

    def get_tool_functions(self) -> Dict[str, callable]:
        return {
            "add_to_memory": self.add_to_memory,
            "add_to_world_book": self.add_to_world_book,
            "create_or_update_user_portrait": self.create_or_update_user_portrait,
            "find_user_portrait": self.find_user_portrait,
            "find_memories": self.find_memories,
            "update_memory": self.update_memory,
            "delete_memory": self.delete_memory
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

    # --- Memory Bank Functions ---
    def add_to_memory(self, content: str, message: Optional[discord.Message] = None, config: Optional[Dict[str, Any]] = None) -> str:
        if not message or not config: return json.dumps({"status": "error", "message": "Missing context."})
        
        try:
            threshold = config.get("behavior", {}).get("memory_dedup_threshold", 0.0)
            if threshold > 0:
                all_memories = knowledge_manager.get_all_memories()
                if self._is_duplicate(content, all_memories, threshold, 'content'):
                    return json.dumps({"status": "duplicate_found", "message": "A similar memory entry already exists."})

            timestamp = datetime.now(timezone.utc).isoformat()
            memory_id = knowledge_manager.add_memory(content=content, timestamp=timestamp, user_id=str(message.author.id), user_name=message.author.display_name, source="对话")
            return json.dumps({"status": "success", "id": memory_id, "message": f"Successfully added to memory with ID: {memory_id}."})
        except Exception as e:
            logger.error(f"Error in add_to_memory tool: {e}", exc_info=True)
            return json.dumps({"status": "error", "message": str(e)})
    
    def find_memories(self, query: str) -> str:
        try:
            all_memories = knowledge_manager.get_all_memories()
            # Simple text search in content
            matching_memories = [m for m in all_memories if query.lower() in m['content'].lower()]
            if not matching_memories:
                return "No memories found matching the query."
            results = [f"ID: {m['id']}, Content: {m['content']}" for m in matching_memories]
            return "\n".join(results)
        except Exception as e:
            logger.error(f"Error in find_memories tool: {e}", exc_info=True)
            return f"Error finding memories: {e}"

    def update_memory(self, memory_id: int, new_content: str) -> str:
        try:
            success = knowledge_manager.update_memory(memory_id, new_content)
            return f"Successfully updated memory {memory_id}." if success else f"Failed to update memory {memory_id} (not found?)."
        except Exception as e:
            logger.error(f"Error in update_memory tool: {e}", exc_info=True)
            return f"Error updating memory: {e}"
            
    def delete_memory(self, memory_id: int) -> str:
        try:
            success = knowledge_manager.delete_memory(memory_id)
            return f"Successfully deleted memory {memory_id}." if success else f"Failed to delete memory {memory_id} (not found?)."
        except Exception as e:
            logger.error(f"Error in delete_memory tool: {e}", exc_info=True)
            return f"Error deleting memory: {e}"

    # --- World Book / Portrait Functions ---
    def add_to_world_book(self, keywords: str, content: str, subject_of_knowledge: Optional[str] = None, message: Optional[discord.Message] = None, config: Optional[Dict[str, Any]] = None) -> str:
        if not message or not config: return json.dumps({"status": "error", "message": "Missing context."})
        
        try:
            threshold = config.get("behavior", {}).get("world_book_dedup_threshold", 0.0)
            if threshold > 0:
                all_entries = knowledge_manager.get_all_world_book_entries()
                if self._is_duplicate(content, all_entries, threshold, 'content'):
                    return json.dumps({"status": "duplicate_found", "message": "A similar world book entry already exists."})

            linked_user_id = None
            if subject_of_knowledge:
                # (user search logic can be reused here if needed)
                pass
            
            entry_id = knowledge_manager.add_world_book_entry(keywords=keywords, content=content, linked_user_id=linked_user_id)
            return json.dumps({"status": "success", "id": entry_id, "message": f"Successfully added to world book with ID: {entry_id}."})
        except Exception as e:
            logger.error(f"Error in add_to_world_book tool: {e}", exc_info=True)
            return json.dumps({"status": "error", "message": str(e)})

    def find_user_portrait(self, user_id: str) -> str:
        try:
            entries = knowledge_manager.get_world_book_entries_for_user(user_id)
            if not entries:
                return f"No portrait found for user ID {user_id}."
            
            portraits = []
            for entry in entries:
                try:
                    content_data = json.loads(entry['content'])
                    portraits.append(f"Portrait ID: {entry['id']}\nKeywords: {entry['keywords']}\nContent: {json.dumps(content_data, indent=2, ensure_ascii=False)}")
                except (json.JSONDecodeError, TypeError):
                    portraits.append(f"Portrait ID: {entry['id']} (unstructured)\nKeywords: {entry['keywords']}\nContent: {entry['content']}")
            return "\n---\n".join(portraits)
        except Exception as e:
            logger.error(f"Error finding portrait for user {user_id}: {e}", exc_info=True)
            return f"Error finding portrait: {e}"

    def create_or_update_user_portrait(self, user_id: str, core_content: Optional[str] = None, 
                                     keywords_to_add: List[str] = [], keywords_to_remove: List[str] = [],
                                     aliases_to_add: List[str] = [], aliases_to_remove: List[str] = [],
                                     triggers_to_add: List[str] = [], triggers_to_remove: List[str] = []) -> str:
        try:
            entries = knowledge_manager.get_world_book_entries_for_user(user_id)
            target_entry = None
            content_data = {}
            
            for entry in entries:
                try:
                    data = json.loads(entry['content'])
                    if isinstance(data, dict) and 'schema_version' in data:
                        target_entry = entry
                        content_data = data
                        break
                except (json.JSONDecodeError, TypeError):
                    continue
            
            if not target_entry and entries:
                target_entry = entries[0]
                try:
                    content_data = json.loads(target_entry['content'])
                    if not isinstance(content_data, dict): content_data = {"core_content": target_entry['content']}
                except (json.JSONDecodeError, TypeError):
                    content_data = {"core_content": target_entry['content']}

            if 'schema_version' not in content_data:
                content_data = {"schema_version": 1, "aliases": [], "triggers": [], "core_content": content_data.get("core_content", "")}
            
            if core_content is not None: content_data['core_content'] = core_content
            
            content_data['aliases'] = list(dict.fromkeys([a for a in content_data.get('aliases', []) if a not in aliases_to_remove] + aliases_to_add))
            content_data['triggers'] = list(dict.fromkeys([t for t in content_data.get('triggers', []) if t not in triggers_to_remove] + triggers_to_add))

            final_keywords = set((target_entry['keywords'] if target_entry else "").split(','))
            final_keywords.update(keywords_to_add)
            final_keywords.difference_update(keywords_to_remove)
            final_keywords.discard('')
            
            final_keywords_str = ", ".join(sorted(list(final_keywords)))
            final_content_str = json.dumps(content_data, ensure_ascii=False, indent=2)

            if target_entry:
                knowledge_manager.update_world_book_entry(entry_id=target_entry['id'], keywords=final_keywords_str, content=final_content_str, enabled=True, linked_user_id=user_id)
                return f"Successfully updated portrait for user ID {user_id}."
            else:
                knowledge_manager.add_world_book_entry(keywords=final_keywords_str, content=final_content_str, linked_user_id=user_id)
                return f"Successfully created new portrait for user ID {user_id}."

        except Exception as e:
            logger.error(f"Error in create_or_update_user_portrait: {e}", exc_info=True)
            return f"An error occurred: {e}"