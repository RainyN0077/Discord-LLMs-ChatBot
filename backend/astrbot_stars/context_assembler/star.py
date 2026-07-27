"""Context Assembler Star (AstrBot v4.26.2).

Builds full LLM context: system prompt resolution, history building,
memory/persona injection.

Ported from app/handlers/context_assembler.py.
"""

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class ContextAssembler(star.Star):
    """Builds full LLM context (system prompt + history + user message)."""

    name = "context_assembler"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        self._session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # IPC infrastructure (mirrors knowledge_bridge pattern)
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared aiohttp client session (connection pool reuse)."""
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

    async def _call_api(self, endpoint: str) -> Dict[str, Any]:
        """Call the management-layer internal API with connection-pool reuse.

        Returns the JSON response dict on success, or empty dict on any failure.
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
            async with session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                return await resp.json() if resp.status == 200 else {}
        except Exception as e:
            logger.debug("ContextAssembler API GET %s: %s", endpoint, e)
            return {}

    # ------------------------------------------------------------------
    # Config resolution (IPC first, local fallback)
    # ------------------------------------------------------------------

    async def _get_effective_config(self) -> Dict[str, Any]:
        """Get the bot configuration, preferring the management-layer source of truth.

        Tries IPC ``/config`` first; on any failure falls back to local
        ``self.context.get_config()``.
        """
        ipc_config = await self._call_api("config")
        if ipc_config:
            return ipc_config
        return self.context.get_config()

    # ------------------------------------------------------------------
    # Role-based config resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_role_config_from_extra(
        event: AstrMessageEvent,
        role_based_config: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Resolve role-based configuration for the event's author.

        In the AstrBot subprocess we cannot access Discord role objects directly.
        Strategy (in priority order):
          1. Check ``user_role_id`` from event extras (populated by persona star).
          2. Fall back to matching by user_id (for simple single-role setups).
          3. Return None if no match.

        Mirrors backend/nb_plugins/core_llm_bot/pipeline.py _resolve_role_config.
        """
        if not role_based_config:
            return None

        # Priority 1: role_id from event extra (upstream star, e.g. persona)
        role_id = event.get_extra("user_role_id", "") or ""
        if role_id:
            for cfg in role_based_config.values():
                if cfg.get("id") == role_id:
                    return cfg

        # Priority 2: fallback — match by user_id
        # This covers simple setups where role config is mapped to individual users.
        user_id = event.get_sender_id()
        for cfg in role_based_config.values():
            if cfg.get("id") == user_id:
                return cfg

        return None

    # ------------------------------------------------------------------
    # System prompt resolution
    # ------------------------------------------------------------------

    def _resolve_system_prompt(
        self, config: Dict[str, Any], event: AstrMessageEvent
    ) -> str:
        """Resolve the effective system prompt for this event.

        Override priority (highest wins):
          1. Channel-scoped prompt
          2. Guild-scoped prompt
          3. Role-based prompt
          4. Global base prompt
        """
        base_prompt = config.get("system_prompt", "You are a helpful assistant.")

        # Role-based config override
        role_config = config.get("role_based_config", {})
        matched_role = self._resolve_role_config_from_extra(event, role_config)
        if matched_role and matched_role.get("system_prompt"):
            base_prompt = matched_role["system_prompt"]

        # Scoped prompt overrides: channel > guild
        scoped = config.get("scoped_prompts", {"guilds": {}, "channels": {}})
        guild_id = event.get_group_id()
        channel_id = event.get_session_id()

        if guild_id:
            guild_cfg = scoped.get("guilds", {}).get(guild_id, {})
            if guild_cfg.get("system_prompt"):
                base_prompt = guild_cfg["system_prompt"]
        if channel_id:
            channel_cfg = scoped.get("channels", {}).get(channel_id, {})
            if channel_cfg.get("system_prompt"):
                base_prompt = channel_cfg["system_prompt"]

        return base_prompt.strip()

    # ------------------------------------------------------------------
    # Memory injection
    # ------------------------------------------------------------------

    @staticmethod
    def _inject_memories(
        system_prompt: str, memories: List[Dict[str, Any]]
    ) -> str:
        """Inject recalled memories into the system prompt as a knowledge block.

        Format (matches pipeline.py lines 88-90)::

            <knowledge>
            <long_term_memory>
            {memory_content}
            </long_term_memory>
            </knowledge>

            {system_prompt}

        If ``memories`` is empty or all entries are blank, returns the original
        system_prompt unchanged.
        """
        if not memories:
            return system_prompt

        # Extract non-empty content strings from memory entries
        memory_lines: List[str] = []
        for mem in memories:
            content = ""
            if isinstance(mem, dict):
                content = mem.get("content", "") or ""
            elif isinstance(mem, str):
                content = mem
            if content.strip():
                memory_lines.append(content.strip())

        if not memory_lines:
            return system_prompt

        memory_knowledge = "\n".join(memory_lines)
        return (
            f"<knowledge>\n<long_term_memory>\n{memory_knowledge}\n"
            f"</long_term_memory>\n</knowledge>\n\n{system_prompt}"
        )

    # ------------------------------------------------------------------
    # Persona injection
    # ------------------------------------------------------------------

    @staticmethod
    def _inject_persona(
        system_prompt: str, persona: Dict[str, Any]
    ) -> str:
        """Inject user persona data into the system prompt as a participant block.

        Expected ``persona`` dict structure (from persona Star)::

            {
                "prompt": "Core persona description",
                "nickname": "Optional nickname/alias",
                ...
            }

        If ``persona`` is empty or has no prompt, returns the original system_prompt
        unchanged.
        """
        if not persona:
            return system_prompt

        prompt_text = ""
        if isinstance(persona, dict):
            prompt_text = persona.get("prompt", "") or ""
        elif isinstance(persona, str):
            prompt_text = persona

        if not prompt_text.strip():
            return system_prompt

        block = "[Participant Persona]"
        nicknames = persona.get("nickname", "") if isinstance(persona, dict) else ""
        if nicknames:
            block += f"\n- Acceptable Aliases: [{nicknames}]"
        block += f"\n- Core Persona: {prompt_text}"

        return f"{system_prompt}\n\n{block}"

    # ------------------------------------------------------------------
    # History building
    # ------------------------------------------------------------------

    @staticmethod
    def _truncate_history_by_char_limit(
        history: List[Dict[str, str]], char_limit: int
    ) -> List[Dict[str, str]]:
        """Truncate conversation history from the oldest message to fit within char_limit.

        Args:
            history: List of ``{"role": str, "content": str}`` dicts, newest first.
            char_limit: Maximum total characters for all messages.

        Returns:
            Truncated list preserving newest messages (removes oldest first).
        """
        if char_limit <= 0 or not history:
            return history

        # Work from newest (end) → oldest (start) to keep the most recent messages
        total = 0
        kept: List[Dict[str, str]] = []
        for msg in reversed(history):
            content_len = len(msg.get("content", ""))
            if total + content_len > char_limit:
                break
            total += content_len
            kept.append(msg)
        # Restore chronological order
        kept.reverse()
        return kept

    async def _build_history(
        self,
        config: Dict[str, Any],
        event: AstrMessageEvent,
    ) -> List[Dict[str, str]]:
        """Build conversation history respecting context_mode and limits.

        Returns a list of ``{"role": "user"|"assistant", "content": str}`` dicts.
        On any failure (e.g. conversation_manager unavailable) returns an empty list.

        History format::

            [{"role": "user", "content": "..."},
             {"role": "assistant", "content": "..."}]
        """
        context_mode = config.get("context_mode", "channel")
        if context_mode == "none":
            return []

        # Select appropriate settings for the context mode
        if context_mode == "memory":
            settings = config.get("memory_context_settings", {})
        else:  # channel (default)
            settings = config.get("channel_context_settings", {})

        message_limit = int(settings.get("message_limit", 10))
        char_limit = int(settings.get("char_limit", 4000))

        if message_limit <= 0:
            return []

        try:
            # TODO: verify AstrBot API — conversation_manager.get_history()
            # signature and return format expected by downstream stars.
            history = await self.context.conversation_manager.get_history(
                uid=str(event.unified_msg_origin),
                limit=message_limit,
            )
        except Exception as e:
            logger.warning("Failed to get conversation history: %s", e)
            return []

        # Truncate by character limit if needed (oldest messages removed first)
        if char_limit > 0:
            history = self._truncate_history_by_char_limit(history, char_limit)

        return history

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Assemble LLM context before LLM processing.

        Pipeline:
          1. Resolve base system prompt (with role/scoped overrides).
          2. Inject recalled memories from knowledge_bridge.
          3. Inject persona data from persona star.
          4. Build conversation history with context_mode-aware truncation.
          5. Forward plugin append blocks as injected_data extra.
          6. Store assembled context in event extras for downstream stars.
        """
        # Prefer IPC config (management layer source of truth),
        # fall back to local AstrBot config.
        config = await self._get_effective_config()

        # ---- Step 1: Resolve system prompt ----
        system_prompt = self._resolve_system_prompt(config, event)

        # ---- Step 2: Memory injection (from knowledge_bridge) ----
        # knowledge_bridge Star stores memories as event extra.
        memories = event.get_extra("memories", [])
        system_prompt = self._inject_memories(system_prompt, memories)

        # ---- Step 3: Persona injection (from persona Star) ----
        persona = event.get_extra("user_persona", {})
        system_prompt = self._inject_persona(system_prompt, persona)

        # ---- Step 4: Build conversation history ----
        history = await self._build_history(config, event)

        # ---- Step 5: Forward plugin append blocks ----
        # plugin_bridge Star stores append blocks as event extra.
        # Downstream formatter stars read this to inject into user message.
        plugin_append_blocks = event.get_extra("plugin_append_blocks", [])
        if plugin_append_blocks:
            injected_data = "\n".join(
                str(b) for b in plugin_append_blocks if str(b).strip()
            )
            if injected_data:
                event.set_extra("injected_data", injected_data)

        # ---- Step 6: Store assembled context in event extras ----
        # TODO: verify AstrBot API — event.set_extra should be available.
        event.set_extra("system_prompt", system_prompt)
        event.set_extra("history", history)

        logger.debug(
            "Context assembled: prompt_len=%d, history_len=%d, memories=%d",
            len(system_prompt),
            len(history),
            len(memories),
        )
