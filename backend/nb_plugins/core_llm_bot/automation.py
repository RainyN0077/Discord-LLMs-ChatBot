from typing import Any, Dict, Optional

from app.handlers.automation import (
    track_auto_interject as _track_auto_interject,
    track_repeat_parrot as _track_repeat_parrot,
    reset_channel_automation_state as _reset_channel_automation_state,
)
from .event_shim import MessageContext


def track_auto_interject(
    message_ctx: MessageContext,
    bot_config: Dict[str, Any],
    auto_message_counts: Dict[int, int],
) -> bool:
    return _track_auto_interject(message_ctx, bot_config, auto_message_counts)


def track_repeat_parrot(
    message_ctx: MessageContext,
    bot_config: Dict[str, Any],
    repeat_streaks: Dict[int, Dict[str, Any]],
) -> Optional[str]:
    return _track_repeat_parrot(message_ctx, bot_config, repeat_streaks)


def reset_channel_automation_state(
    channel_id: int,
    auto_message_counts: Dict[int, int],
    repeat_streaks: Dict[int, Dict[str, Any]],
) -> None:
    _reset_channel_automation_state(channel_id, auto_message_counts, repeat_streaks)
