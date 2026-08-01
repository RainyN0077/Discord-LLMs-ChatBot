import logging
from typing import Any, Dict, List, Optional, Tuple

from app.ports.platform_message import PlatformMessage
from app.core_logic.persona_manager import (
    build_system_prompt,
    determine_bot_persona,
    get_highest_configured_role,
)
from app.core_logic.context_builder import (
    build_context_history,
    format_user_message_for_llm,
    resolve_prompt_templates,
)

logger = logging.getLogger(__name__)


async def build_full_context(
    bot: Any,
    config: Dict[str, Any],
    message: PlatformMessage,
    memory_cutoffs: Dict[int, Any],
    injected_data: Optional[str] = None,
) -> Tuple[str, str, List[Dict[str, str]], List[PlatformMessage], Optional[str], Optional[Dict[str, Any]]]:
    role_name, role_config = None, None
    if hasattr(message.author, 'roles'):
        role_name, role_config = get_highest_configured_role(
            message.author.roles, config.get("role_based_config", {})
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

    # 读取源：bot_config['prompt_templates']（归一化，非 dict 一律 None → 全链路回退默认）
    templates = resolve_prompt_templates(config)

    system_prompt = await build_system_prompt(
        bot, config, specific_persona_prompt, situational_prompt, message, active_directives_log,
        templates=templates,
    )

    final_formatted_content = await format_user_message_for_llm(
        message, bot, config, role_config, injected_data, templates=templates
    )

    return system_prompt, final_formatted_content, history_for_llm, history_messages, role_name, role_config
