"""Memory Tools Star (AstrBot v4.26.2).

Provides LLM tool definitions and implementations for:
  - ``add_to_memory``    — remember factual/user information
  - ``recall_memory``    — search stored memories by query
  - ``add_to_world_book`` — record keyword-triggered lore/facts

Tool schemas mirror ``backend/plugins/memory_plugin.py`` (legacy).

Design Decision:
  Tool implementations delegate to the management layer via IPC
  (``/knowledge/ingest`` and ``/knowledge/recall`` endpoints) rather than
  calling the knowledge manager directly in the AstrBot subprocess.
  This keeps the knowledge manager logic centralised in the management layer.

Registration strategy (R9 risk):
  AstrBot's custom tool registration API is unconfirmed. This star uses
  a two-path approach:
    **Path A** (preferred): Register tools via AstrBot's ``register_tool``
    or similar API when available.
    **Path B** (fallback): Pass tool definitions via
    ``event.set_extra("available_tools", tool_defs)`` and annotate the
    calling code with TODO markers.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)

# Timeout for each IPC-based tool execution call.
_TOOL_CALL_TIMEOUT = 15


class MemoryTools(star.Star):
    """Provides memory management tool definitions for the LLM.

    The star is intentionally lightweight in ``on_message`` — it only
    registers tool definitions.  Actual tool execution happens via IPC
    to the management layer's knowledge manager.
    """

    name = "memory_tools"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        self._session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # IPC infrastructure
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared aiohttp client session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def __del__(self) -> None:
        """Best-effort cleanup of the shared session on star destruction."""
        if self._session is not None and not self._session.closed:
            try:
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._session.close())
                else:
                    loop.run_until_complete(self._session.close())
            except Exception:
                logger.debug("Failed to close aiohttp session on cleanup")

    async def _call_api(
        self,
        endpoint: str,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call the management-layer internal API.

        Returns the JSON response dict on success, or empty dict on any
        failure (connection error, timeout, non-200 status).
        """
        config = self.context.get_config()
        internal = config.get("internal_api", {})
        base_url = internal.get("base_url", "http://127.0.0.1:8093/internal")
        token = internal.get("secret_token", "")
        bot_id = config.get("bot_id", "")

        url = f"{base_url}/{bot_id}/{endpoint}"
        headers = {"X-Internal-Token": token, "X-Bot-Id": bot_id}

        try:
            session = await self._get_session()
            timeout = aiohttp.ClientTimeout(total=_TOOL_CALL_TIMEOUT)
            if method == "POST":
                async with session.post(
                    url, json=payload or {}, headers=headers, timeout=timeout
                ) as resp:
                    return await resp.json() if resp.status == 200 else {}
            else:
                async with session.get(
                    url, headers=headers, timeout=timeout
                ) as resp:
                    return await resp.json() if resp.status == 200 else {}
        except Exception as e:
            logger.debug("MemoryTools API %s %s: %s", method, endpoint, e)
            return {}

    # ------------------------------------------------------------------
    # Tool definitions (schema for LLM function calling)
    # ------------------------------------------------------------------

    @staticmethod
    def get_tool_definitions() -> List[Dict[str, Any]]:
        """Return tool schemas matching legacy memory_plugin definitions."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "add_to_memory",
                    "description": (
                        "Adds a new piece of information to the long-term memory. "
                        "Use this to remember key facts about the user or conversation."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The information to be remembered.",
                            },
                            "importance": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                                "description": "Importance level for memory retention.",
                                "default": "medium",
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
                    "description": (
                        "Search the long-term memory for information relevant "
                        "to a query."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query to find relevant memories.",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_to_world_book",
                    "description": (
                        "Adds a new entry to the world book. Use this to record "
                        "factual information, lore, or settings that can be "
                        "triggered by keywords."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {
                                "type": "string",
                                "description": (
                                    "A comma-separated list of keywords that "
                                    "trigger this entry."
                                ),
                            },
                            "content": {
                                "type": "string",
                                "description": (
                                    "The content to be injected into the context "
                                    "when a keyword is mentioned."
                                ),
                            },
                            "subject_of_knowledge": {
                                "type": "string",
                                "description": (
                                    "The name of the person this knowledge is "
                                    "about. Leave empty for general facts."
                                ),
                            },
                        },
                        "required": ["keywords", "content"],
                    },
                },
            },
        ]

    # ------------------------------------------------------------------
    # Tool implementations (IPC-based)
    # ------------------------------------------------------------------

    async def add_to_memory(
        self,
        content: str,
        importance: str = "medium",
        **kwargs: Any,
    ) -> str:
        """Tool implementation: add content to long-term memory via IPC.

        Returns a JSON string with status information.
        """
        if not content or not content.strip():
            return json.dumps({
                "status": "error",
                "message": "Content cannot be empty.",
            })

        # Build the ingest payload matching the /knowledge/ingest endpoint.
        payload: Dict[str, Any] = {
            "type": "memory",
            "content": content.strip(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "tool",
            # Inject context from kwargs if provided by the LLM framework.
            "user_id": kwargs.get("user_id", "unknown"),
            "user_name": kwargs.get("user_name", ""),
            "channel_id": kwargs.get("channel_id", ""),
        }

        result = await self._call_api("knowledge/ingest", method="POST", payload=payload)

        if not result:
            return json.dumps({
                "status": "error",
                "message": "Memory service unavailable.",
            })

        status = result.get("status", "unknown")
        if status in {"promoted", "duplicate_existing"}:
            memory_id = result.get("memory_id")
            return json.dumps({
                "status": "success",
                "id": memory_id,
                "message": f"Memory accepted with ID: {memory_id}.",
            })
        if status == "staged":
            return json.dumps({
                "status": "staged",
                "candidate_id": result.get("candidate_id"),
                "message": "Memory staged in candidate pool; will auto-promote.",
            })
        if status == "cooldown":
            return json.dumps({
                "status": "cooldown",
                "message": "Memory ignored due to cooldown (too frequent).",
            })
        if status == "error":
            return json.dumps(result)

        return json.dumps({
            "status": status or "skipped",
            "message": "Memory was not accepted by quality policy.",
        })

    async def recall_memory(
        self,
        query: str,
        **kwargs: Any,
    ) -> str:
        """Tool implementation: search stored memories via IPC.

        Returns a JSON string with memory results.
        """
        if not query or not query.strip():
            return json.dumps({
                "status": "error",
                "message": "Search query cannot be empty.",
            })

        from urllib.parse import quote

        # Use sensible defaults matching knowledge_bridge star.
        top_k = kwargs.get("top_k", 12)
        char_limit = kwargs.get("char_limit", 2200)
        max_age_days = kwargs.get("max_age_days", 365)

        endpoint = (
            f"knowledge/recall"
            f"?query={quote(query.strip(), safe='')}"
            f"&top_k={top_k}"
            f"&char_limit={char_limit}"
            f"&max_age_days={max_age_days}"
        )

        result = await self._call_api(endpoint, method="GET")

        if not result:
            return json.dumps({
                "status": "error",
                "message": "Memory recall service unavailable.",
            })

        memories = result.get("memories", [])
        if memories:
            # Format memories as readable text for the LLM.
            formatted = "\n\n".join(
                m.get("content", "") for m in memories if m.get("content")
            )
            return json.dumps({
                "status": "success",
                "count": len(memories),
                "memories": formatted,
            })

        return json.dumps({
            "status": "no_results",
            "message": "No relevant memories found.",
        })

    async def add_to_world_book(
        self,
        keywords: str,
        content: str,
        subject_of_knowledge: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Tool implementation: add world book entry via IPC.

        Returns a JSON string with status information.
        """
        if not keywords or not keywords.strip():
            return json.dumps({
                "status": "error",
                "message": "Keywords cannot be empty.",
            })
        if not content or not content.strip():
            return json.dumps({
                "status": "error",
                "message": "Content cannot be empty.",
            })

        payload: Dict[str, Any] = {
            "type": "world_book",
            "keywords": keywords.strip(),
            "content": content.strip(),
            "source": "tool",
            "user_id": kwargs.get("user_id", "unknown"),
            "user_name": kwargs.get("user_name", ""),
            "linked_user_id": None,
        }

        if subject_of_knowledge:
            payload["subject_of_knowledge"] = subject_of_knowledge.strip()

        result = await self._call_api("knowledge/ingest", method="POST", payload=payload)

        if not result:
            return json.dumps({
                "status": "error",
                "message": "World book service unavailable.",
            })

        status = result.get("status", "unknown")
        if status == "added":
            return json.dumps({
                "status": "success",
                "message": "Successfully added to world book.",
            })
        if status == "duplicate_found":
            return json.dumps({
                "status": "duplicate_found",
                "message": "A similar world book entry already exists.",
            })
        if status == "error":
            return json.dumps(result)

        return json.dumps({
            "status": status,
            "message": f"World book entry processed with status: {status}.",
        })

    # ------------------------------------------------------------------
    # Tool execution dispatch
    # ------------------------------------------------------------------

    def get_tool_functions(self) -> Dict[str, Any]:
        """Return the mapping of tool names to async callables.

        This mirrors the legacy ``Plugin.get_tool_functions()`` pattern
        and can be used directly when AstrBot supports custom tool
        registration.

        Returns:
            ``{tool_name: async_callable}`` dict.
        """
        return {
            "add_to_memory": self.add_to_memory,
            "recall_memory": self.recall_memory,
            "add_to_world_book": self.add_to_world_book,
        }

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Register memory tool definitions for the current message context.

        Because AstrBot's custom tool registration API is unconfirmed, this
        star uses ``event.set_extra("available_tools", tool_defs)`` as a
        fallback mechanism.  The upstream star (e.g. LLM provider wrapper or
        context_assembler) can read this extra and register the tools with
        the LLM.

        TODO: verify AstrBot API —
          If AstrBot exposes a ``register_tool(name, func, schema)`` or
          similar mechanism, migrate tool registration out of on_message
          into a dedicated initialisation phase and remove the
          ``available_tools`` extra passthrough.

        The tool definitions are also logged at debug level for visibility.
        """
        tool_defs = self.get_tool_definitions()

        # Path B (fallback): pass through event extras.
        # TODO: Replace with Path A when AstrBot's registration API is known.
        event.set_extra("available_tools", tool_defs)

        logger.debug(
            "MemoryTools: registered %d tool definitions via event extras",
            len(tool_defs),
        )
