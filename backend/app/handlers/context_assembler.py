import logging
from typing import Any, Dict, List, Optional, Tuple

import discord

from ..core_logic.persona_manager import determine_bot_persona, build_system_prompt, get_highest_configured_role
from ..core_logic.context_builder import build_context_history, format_user_message_for_llm

logger = logging.getLogger(__name__)


async def build_full_context(
    bot: Any,
    config: Dict[str, Any],
    message: Any,
    memory_cutoffs: Dict[int, Any],
    injected_data: Optional[str] = None,
) -> Tuple[str, str, List[Dict[str, str]], List[Any], Optional[str], Optional[Dict[str, Any]]]:
    role_name, role_config = None, None
    if isinstance(message.author, discord.Member):
        role_name, role_config = get_highest_configured_role(
            message.author, config.get("role_based_config", {})
        ) or (None, None)

    cutoff_timestamp = memory_cutoffs.get(message.channel.id)
    history_messages, history_for_llm = await build_context_history(bot, config, message, cutoff_timestamp)

    specific_persona_prompt, situational_prompt, active_directives_log = determine_bot_persona(
        config,
        str(message.channel.id),
        str(message.guild.id) if message.guild else None,
        role_name,
        role_config,
    )

    system_prompt = await build_system_prompt(
        bot, config, specific_persona_prompt, situational_prompt, message, active_directives_log
    )

    final_formatted_content = format_user_message_for_llm(
        message, bot, config, role_config, injected_data
    )

    return system_prompt, final_formatted_content, history_for_llm, history_messages, role_name, role_config
