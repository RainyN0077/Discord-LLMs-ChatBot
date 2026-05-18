"""
Monkey-patch for nonebot.adapters.discord to fix ComponentEmoji validation.

Bug: ComponentEmoji.id is defined as required (str | None = Field(...)),
but Discord only sends 'id' for custom emojis, not unicode ones (e.g., 🔗).
This causes pydantic ValidationError for MESSAGE_UPDATE events with button components.

Fixed by making id and name optional, then rebuilding affected models.
"""

import logging

logger = logging.getLogger(__name__)


def apply_component_emoji_fix():
    from nonebot.adapters.discord.api.model import ComponentEmoji
    from nonebot.adapters.discord.api.model import Button, SelectOption, SelectMenu, TextInput, ActionRow

    if not ComponentEmoji.model_fields.get("id") or not ComponentEmoji.model_fields["id"].is_required():
        return

    # Make id and name optional
    ComponentEmoji.model_fields["id"].default = None
    ComponentEmoji.model_fields["name"].default = None

    # Rebuild models that directly reference ComponentEmoji
    ComponentEmoji.model_rebuild(force=True)
    Button.model_rebuild(force=True)
    SelectOption.model_rebuild(force=True)

    # Rebuild models that include Button/SelectMenu/TextInput
    SelectMenu.model_rebuild(force=True)
    TextInput.model_rebuild(force=True)
    ActionRow.model_rebuild(force=True)

    # Rebuild event payloads that use DirectComponent (ActionRow | TextInput)
    from nonebot.adapters.discord.api.models.gateway_events import (
        MessageUpdateBasePayload,
        MessageDeleteBasePayload,
    )
    MessageUpdateBasePayload.model_rebuild(force=True)

    # Rebuild event classes
    from nonebot.adapters.discord.event import (
        MessageUpdateEvent,
        GuildMessageUpdateEvent,
        DirectMessageUpdateEvent,
    )
    MessageUpdateEvent.model_rebuild(force=True)
    GuildMessageUpdateEvent.model_rebuild(force=True)
    DirectMessageUpdateEvent.model_rebuild(force=True)

    logger.info("Applied ComponentEmoji monkey-patch (id/name now optional)")
