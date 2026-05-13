from typing import Any, Dict, List, Optional, Tuple
import discord
import logging

logger = logging.getLogger(__name__)


def track_auto_interject(
    message: discord.Message,
    bot_config: Dict[str, Any],
    auto_message_counts: Dict[int, int],
) -> bool:
    if not bot_config.get("auto_interject_enabled", False):
        return False

    try:
        interval = max(1, int(bot_config.get("auto_interject_interval", 20)))
        min_length = max(0, int(bot_config.get("auto_interject_min_length", 0)))
    except (TypeError, ValueError):
        interval = 20
        min_length = 0

    content = (message.content or "").strip()
    if len(content) < min_length:
        return False

    channel_id = message.channel.id
    auto_message_counts[channel_id] = auto_message_counts.get(channel_id, 0) + 1
    return auto_message_counts[channel_id] >= interval


def normalize_repeat_content(
    message: discord.Message,
    bot_config: Dict[str, Any],
) -> Optional[Tuple[str, str]]:
    raw_content = message.content or ""
    trim_whitespace = bool(bot_config.get("repeat_parrot_trim_whitespace", True))
    case_sensitive = bool(bot_config.get("repeat_parrot_case_sensitive", False))

    try:
        min_length = max(0, int(bot_config.get("repeat_parrot_min_length", 2)))
    except (TypeError, ValueError):
        min_length = 2

    comparable_content = raw_content.strip() if trim_whitespace else raw_content
    if len(comparable_content) < min_length:
        return None

    normalized = comparable_content if case_sensitive else comparable_content.lower()
    if not normalized:
        return None

    return comparable_content, normalized


def track_repeat_parrot(
    message: discord.Message,
    bot_config: Dict[str, Any],
    repeat_streaks: Dict[int, Dict[str, Any]],
) -> Optional[str]:
    if not bot_config.get("repeat_parrot_enabled", False):
        return None

    normalized_content = normalize_repeat_content(message, bot_config)
    channel_id = message.channel.id
    if not normalized_content:
        repeat_streaks.pop(channel_id, None)
        return None

    display_content, comparable_content = normalized_content
    previous_state = repeat_streaks.get(channel_id)

    if previous_state and previous_state.get("normalized") == comparable_content:
        previous_state["count"] += 1
        previous_state["user_ids"].add(str(message.author.id))
        state = previous_state
    else:
        state = {
            "normalized": comparable_content,
            "content": display_content,
            "count": 1,
            "user_ids": {str(message.author.id)},
            "parroted": False,
        }
        repeat_streaks[channel_id] = state

    try:
        threshold = max(2, int(bot_config.get("repeat_parrot_threshold", 3)))
    except (TypeError, ValueError):
        threshold = 3

    require_multiple_users = bool(bot_config.get("repeat_parrot_require_multiple_users", True))
    has_required_users = len(state["user_ids"]) >= 2 if require_multiple_users else True

    if not state["parroted"] and state["count"] >= threshold and has_required_users:
        state["parroted"] = True
        return state["content"]

    return None


def reset_channel_automation_state(
    channel_id: int,
    auto_message_counts: Dict[int, int],
    repeat_streaks: Dict[int, Dict[str, Any]],
) -> None:
    auto_message_counts[channel_id] = 0
    repeat_streaks.pop(channel_id, None)
