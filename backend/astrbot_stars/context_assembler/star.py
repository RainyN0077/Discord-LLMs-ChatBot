"""Context Assembler Star (AstrBot v4.26.2).

Builds full LLM context: system prompt resolution, history building,
memory/persona injection.

Ported from app/handlers/context_assembler.py.
"""

import logging
from typing import Any, Dict, List

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class ContextAssembler(star.Star):
    """Builds full LLM context (system prompt + history + user message)."""

    name = "context_assembler"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)

    @staticmethod
    def _resolve_system_prompt(config: Dict[str, Any], event: AstrMessageEvent) -> str:
        """Resolve effective system prompt with role/scoped overrides."""
        base_prompt = config.get("system_prompt", "You are a helpful assistant.")
        bot_nickname = config.get("bot_nickname", "Bot")

        # Role-based config
        role_config = config.get("role_based_config", {})
        if role_config:
            user_id = event.get_sender_id()
            for role_cfg in role_config.values():
                if role_cfg.get("id") == user_id:
                    if role_cfg.get("system_prompt"):
                        base_prompt = role_cfg["system_prompt"]
                    break

        # Scoped prompts
        scoped = config.get("scoped_prompts", {"guilds": {}, "channels": {}})
        guild_id = event.get_group_id()
        channel_id = event.get_session_id()

        if guild_id and guild_id in scoped.get("guilds", {}):
            guild_prompt = scoped["guilds"][guild_id].get("system_prompt", "")
            if guild_prompt:
                base_prompt = guild_prompt
        if channel_id and channel_id in scoped.get("channels", {}):
            channel_prompt = scoped["channels"][channel_id].get("system_prompt", "")
            if channel_prompt:
                base_prompt = channel_prompt

        return base_prompt.strip()

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Assemble context before LLM processing."""
        config = self.context.get_config()

        # Resolve system prompt
        system_prompt = self._resolve_system_prompt(config, event)

        # Build conversation history via AstrBot's conversation manager
        try:
            history = await self.context.conversation_manager.get_history(
                uid=str(event.unified_msg_origin),
                limit=config.get("channel_context_settings", {}).get("message_limit", 10),
            )
        except Exception:
            history = []

        # Store assembled context in event extras
        event.set_extra("system_prompt", system_prompt)
        event.set_extra("history", history)

        logger.debug("Context assembled: prompt_len=%d, history_len=%d",
                     len(system_prompt), len(history))
