import asyncio
import logging
from typing import Any, Dict, List, Optional

from nonebot import on_message
from nonebot.adapters.discord import Bot, MessageEvent
from nonebot.internal.adapter.bot import Bot as BaseBot

from app.utils import matches_trigger_keywords
from app.handlers.message_queue import MessageQueue
from .event_shim import event_to_message_context, MessageContext
from .automation import track_auto_interject, track_repeat_parrot, reset_channel_automation_state
from .pipeline import execute_llm_pipeline

logger = logging.getLogger(__name__)

_matcher = on_message(priority=10, block=False)

_queues: Dict[str, MessageQueue] = {}
_channel_processors: Dict[str, asyncio.Task] = {}
_auto_message_counts: Dict[int, int] = {}
_repeat_streaks: Dict[int, Dict[str, Any]] = {}

_bot_instance_map: Dict[str, Any] = {}


def get_auto_message_counts() -> Dict[int, int]:
    return _auto_message_counts


def get_repeat_streaks() -> Dict[int, Dict[str, Any]]:
    return _repeat_streaks


def register_bot_instance(bot_id: str, instance: Any) -> None:
    _bot_instance_map[bot_id] = instance


def unregister_bot_instance(bot_id: str) -> None:
    instance = _bot_instance_map.pop(bot_id, None)
    if instance is not None:
        to_remove = [k for k, v in list(_bot_instance_map.items()) if v is instance]
        for k in to_remove:
            _bot_instance_map.pop(k, None)


def _get_bot_id(bot: BaseBot) -> str:
    return str(getattr(bot, "self_id", "unknown"))


def _resolve_bot_id(bot: BaseBot) -> str:
    self_id = str(getattr(bot, "self_id", ""))
    if self_id and self_id in _bot_instance_map:
        return self_id
    bot_token = None
    bot_info = getattr(bot, 'bot_info', None)
    if bot_info is not None:
        bot_token = getattr(bot_info, 'token', None)
    if bot_token:
        for bid, instance in _bot_instance_map.items():
            if getattr(instance, 'config', {}).get("discord_token") == bot_token:
                _bot_instance_map[self_id] = instance
                return bid
    for bid in _bot_instance_map:
        logger.warning("No bot token match for self_id=%s, falling back to first bot '%s'", self_id, bid)
        return bid
    return self_id or "unknown"


@_matcher.handle()
async def _on_discord_message(bot: Bot, event: MessageEvent):
    if event.author and event.author.id == getattr(bot, "self_id", None):
        return

    message_ctx = event_to_message_context(event, bot)
    instance = _bot_instance_map.get(_resolve_bot_id(bot))
    if not instance:
        logger.warning(f"No bot instance registered for bot {_get_bot_id(bot)}")
        return

    config = instance.config

    auto_interject_triggered = track_auto_interject(message_ctx, config, _auto_message_counts)
    repeat_parrot_content = track_repeat_parrot(message_ctx, config, _repeat_streaks)

    trigger_keywords = config.get("trigger_keywords", [])
    trigger_match_mode = config.get("trigger_match_mode", "contains")
    trigger_case_sensitive = bool(config.get("trigger_case_sensitive", False))

    is_mentioned = getattr(event, "to_me", False)
    is_reply_to_bot = (
        getattr(event, "reply", None) is not None
        and getattr(event.reply, "author", None) is not None
        and event.reply.author.id == getattr(bot, "self_id", None)
    )
    has_trigger_keyword = matches_trigger_keywords(
        event.content or "",
        trigger_keywords,
        match_mode=trigger_match_mode,
        case_sensitive=trigger_case_sensitive,
    )
    normal_triggered = is_mentioned or is_reply_to_bot or has_trigger_keyword

    plugin_runtime_config = dict(config)
    plugin_runtime_config["_runtime_normal_triggered"] = normal_triggered
    plugin_manager = getattr(instance, "_plugin_manager", None)
    plugin_result = None
    if plugin_manager:
        plugin_result = await plugin_manager.process_message(message_ctx, plugin_runtime_config)
        if plugin_result is True:
            return

    plugin_append_blocks: List[str] = []
    injected_data = None
    plugin_append_triggered = False
    if isinstance(plugin_result, tuple) and plugin_result[0] == "append":
        plugin_append_blocks = [str(item) for item in plugin_result[1] if str(item).strip()]
        injected_data = "\n".join(plugin_append_blocks)
        plugin_append_triggered = bool(plugin_append_blocks)

    if not normal_triggered and repeat_parrot_content:
        await bot.send_to(
            channel_id=event.channel_id,
            message=repeat_parrot_content,
        )
        logger.info(f"Repeat parrot triggered in channel {event.channel_id}.")
        reset_channel_automation_state(event.channel_id, _auto_message_counts, _repeat_streaks)
        return

    if not (normal_triggered or auto_interject_triggered or plugin_append_triggered):
        return

    trigger_sources: List[str] = []
    if normal_triggered:
        trigger_sources.append("normal")
    if auto_interject_triggered:
        trigger_sources.append("auto_interject")
    if plugin_append_triggered:
        trigger_sources.append("plugin_append")

    channel_id_str = str(event.channel_id)
    queue = _get_queue(_resolve_bot_id(bot))
    ctx = {
        "bot": bot,
        "event": event,
        "message_ctx": message_ctx,
        "trigger_sources": trigger_sources,
        "injected_data": injected_data,
        "plugin_append_blocks": plugin_append_blocks,
    }

    enqueued = await queue.enqueue(channel_id_str, ctx)
    if not enqueued:
        await bot.send(event, "Bot is busy, please try later.", reply_message=True)
        return

    await _ensure_channel_processor(bot, channel_id_str)


def _get_queue(bot_id: str) -> MessageQueue:
    if bot_id not in _queues:
        _queues[bot_id] = MessageQueue()
    return _queues[bot_id]


async def _ensure_channel_processor(bot: Bot, channel_id_str: str) -> None:
    resolved_id = _resolve_bot_id(bot)
    processor_key = f"{resolved_id}:{channel_id_str}"
    if processor_key in _channel_processors and not _channel_processors[processor_key].done():
        return

    async def _handler(ctx: dict) -> None:
        await execute_llm_pipeline(
            bot=ctx["bot"],
            event=ctx["event"],
            message_ctx=ctx["message_ctx"],
            trigger_sources=ctx["trigger_sources"],
            injected_data=ctx["injected_data"],
            plugin_append_blocks=ctx["plugin_append_blocks"],
            instance=_bot_instance_map.get(resolved_id),
            auto_message_counts=_auto_message_counts,
            repeat_streaks=_repeat_streaks,
        )

    queue = _get_queue(resolved_id)
    task = asyncio.create_task(queue.process_channel(channel_id_str, _handler))
    _channel_processors[processor_key] = task
    task.add_done_callback(lambda t, k=processor_key: _channel_processors.pop(k, None))
    logger.info(f"Started queue processor for channel {channel_id_str} (bot {resolved_id})")


def register_main_matcher():
    pass
