import asyncio
import logging
from typing import Any, Dict, List, Optional

from nonebot import on_message
from nonebot.adapters.discord import Bot, MessageEvent
from nonebot.internal.adapter.bot import Bot as BaseBot

from app.feature_flags import is_flag_enabled
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


async def _on_discord_message_new(bot: Bot, event: MessageEvent):
    """新事件处理路径：通过 PlatformAdapter + MessageBus."""
    from app.app_context import AppContext

    ctx = AppContext.get()
    if ctx.message_bus is None:
        logger.warning("MessageBus not initialized, falling back to old path")
        await _on_discord_message_old(bot, event)
        return

    # 注入 Bot 实例到 Runtime（NoneBotRuntime 需要 _bot 才能发送消息）
    instance = _bot_instance_map.get(_resolve_bot_id(bot))
    runtime = getattr(instance, '_runtime', None) if instance else None
    if runtime is not None and hasattr(runtime, 'attach_bot'):
        runtime.attach_bot(bot)

    handled = await ctx.message_bus.publish_event(event, "discord")
    if not handled:
        logger.debug("MessageBus could not route event, falling back to old path")
        await _on_discord_message_old(bot, event)


# 保留旧路径函数，供 fallback 使用
async def _on_discord_message_old(bot: Bot, event: MessageEvent):
    """旧事件处理路径（原 _on_discord_message 逻辑）."""
    if event.author and event.author.id == getattr(bot, "self_id", None):
        return

    message_ctx = event_to_message_context(event, bot)
    instance = _bot_instance_map.get(_resolve_bot_id(bot))
    if not instance:
        logger.warning(f"No bot instance registered for bot {_get_bot_id(bot)}")
        return

    config = instance.config

    guild_id = str(event.guild_id) if getattr(event, 'guild_id', None) else None
    channel_id = str(event.channel_id)
    user_id = str(event.author.id) if event.author else None

    async def _record_interaction(trigger_source: str):
        ih_config = config.get("interaction_history", {})
        if not ih_config.get("enabled", True):
            return
        try:
            from app.core_logic.interaction_recorder import get_interaction_recorder
            recorder = get_interaction_recorder()
            member_name = (getattr(event.author, 'display_name', None)
                           or getattr(event.author, 'name', None)
                           or user_id or "")
            role_id = "default"
            if guild_id and hasattr(event, 'author') and hasattr(event.author, 'roles'):
                for r in reversed(list(getattr(event.author, 'roles', []))):
                    role_id = str(r.id)
                    break
            content = str(getattr(event, 'content', '') or '')
            attachments = []
            for att in getattr(event, 'attachments', []) or []:
                if hasattr(att, 'url'):
                    attachments.append(str(att.url))
            bot_id_str = _resolve_bot_id(bot)
            await recorder.record_message(
                bot_id=bot_id_str,
                guild_id=guild_id or "dm",
                channel_id=channel_id,
                member_id=user_id or "unknown",
                member_name=member_name,
                role_id=role_id,
                content=content,
                message_id=str(getattr(event, 'message_id', '') or ''),
                attachments=attachments,
                is_bot_reply=False,
                trigger_source=trigger_source,
            )
        except Exception:
            logger.debug("Failed to record interaction", exc_info=True)

    if user_id and config.get("user_options", {}).get("enabled"):
        from app.core_logic.user_options_manager import is_user_blocked_from_response
        block_result = is_user_blocked_from_response(config, guild_id, channel_id, user_id)
        if block_result:
            logger.info(f"[uo:gate] BLOCKED user={user_id} channel={channel_id} guild={guild_id}")
            await _record_interaction("blocked")
            return

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
            await _record_interaction("plugin_consumed")
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
        await _record_interaction("parrot")
        return

    if not (normal_triggered or auto_interject_triggered or plugin_append_triggered):
        await _record_interaction("none")
        return

    trigger_sources: List[str] = []
    if normal_triggered:
        trigger_sources.append("normal")
    if auto_interject_triggered:
        trigger_sources.append("auto_interject")
    if plugin_append_triggered:
        trigger_sources.append("plugin_append")

    trigger_source_str = ",".join(trigger_sources) if trigger_sources else "unknown"
    await _record_interaction(trigger_source_str)

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
        instance = _bot_instance_map.get(resolved_id)
        if not instance:
            logger.warning(f"[uo:handler] instance for bot {resolved_id} not found, skipping queued message")
            return
        await execute_llm_pipeline(
            bot=ctx["bot"],
            event=ctx["event"],
            message_ctx=ctx["message_ctx"],
            trigger_sources=ctx["trigger_sources"],
            injected_data=ctx["injected_data"],
            plugin_append_blocks=ctx["plugin_append_blocks"],
            instance=instance,
            auto_message_counts=_auto_message_counts,
            repeat_streaks=_repeat_streaks,
        )

    queue = _get_queue(resolved_id)
    task = asyncio.create_task(queue.process_channel(channel_id_str, _handler))
    _channel_processors[processor_key] = task
    task.add_done_callback(lambda t, k=processor_key: _channel_processors.pop(k, None))
    logger.info(f"Started queue processor for channel {channel_id_str} (bot {resolved_id})")


@_matcher.handle()
async def _on_discord_message(bot: Bot, event: MessageEvent):
    """消息入口 — 根据 Feature Flag 路由到新/旧路径."""
    if is_flag_enabled("USE_MESSAGE_BUS"):
        await _on_discord_message_new(bot, event)
    else:
        await _on_discord_message_old(bot, event)


def register_main_matcher():
    pass
