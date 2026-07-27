import logging
from typing import Any, Dict, List, Optional

from nonebot.adapters.discord import Bot, MessageEvent

from app.core_shared import (
    get_redis,
    token_calculator,
    strip_dsml_tool_blocks,
    strip_thinking_sections,
    contains_dsml_tool_blocks,
)
from app.debug_capture_store import add_capture
from app.llm_providers.factory import get_llm_provider
from app.ocr_service import is_multimodal_llm
from app.utils import split_message, transform_memories_for_prompt
from app.core_logic.usage_manager import UsageManager

from app.ports.platform_message import PlatformMessage
from .context import build_full_context
from .rendering import render_streaming_response, _render_streaming_response_old
from .automation import reset_channel_automation_state

logger = logging.getLogger(__name__)


async def execute_llm_pipeline(
    bot: Bot,
    event: MessageEvent,
    message_ctx: PlatformMessage,
    trigger_sources: List[str],
    injected_data: Optional[str],
    plugin_append_blocks: List[str],
    instance: Any,
    auto_message_counts: Dict[int, int],
    repeat_streaks: Dict[int, Dict[str, Any]],
) -> None:
    from app.handlers.image_processor import collect_and_download_images, process_ocr_for_images

    config = instance.config
    knowledge_manager = instance._knowledge_manager
    usage_tracker = instance._usage_tracker
    plugin_manager = instance._plugin_manager
    memory_cutoffs = instance.memory_cutoffs

    lock_key = f"discord:message_lock:{message_ctx.id}"
    is_lock_acquired = get_redis().set(lock_key, "processing", nx=True, ex=60)
    if not is_lock_acquired:
        logger.info(f"Message {message_ctx.id} already being processed. Skipping.")
        return

    logger.info(f"Processing message {message_ctx.id} for bot '{instance.bot_id}'.")

    runtime = getattr(instance, '_runtime', None)

    try:
        if runtime is not None:
            await runtime.trigger_typing_indicator(channel_id=str(getattr(event, 'channel_id', '')))
        else:
            await bot.trigger_typing_indicator(channel_id=event.channel_id)
    except Exception:
        pass

    downloaded_images = await collect_and_download_images(message_ctx)
    llm_images = [item["bytes"] for item in downloaded_images]

    system_prompt, final_formatted_content, history_for_llm, history_messages, role_name, role_config = await build_full_context(
        bot, config, message_ctx, memory_cutoffs, injected_data
    )

    if downloaded_images and not is_multimodal_llm(config):
        final_formatted_content = await process_ocr_for_images(downloaded_images, config, final_formatted_content)

    if knowledge_manager:
        try:
            recall_top_k = max(1, min(50, int(config.get("auto_memory_recall_top_k", 12))))
        except (TypeError, ValueError):
            recall_top_k = 12
        try:
            recall_char_limit = max(300, min(20000, int(config.get("auto_memory_recall_char_limit", 2200))))
        except (TypeError, ValueError):
            recall_char_limit = 2200
        try:
            recall_max_age_days = max(1, min(3650, int(config.get("auto_memory_recall_max_age_days", 365))))
        except (TypeError, ValueError):
            recall_max_age_days = 365
        relevant_memories = await knowledge_manager.get_relevant_memories(
            query_text=message_ctx.content or "",
            top_k=recall_top_k, char_limit=recall_char_limit, max_age_days=recall_max_age_days,
            config=config,
        )
        if relevant_memories:
            transformed_memories = transform_memories_for_prompt(relevant_memories, target_timezone_str='UTC')
            memory_knowledge = "\n".join(transformed_memories)
            system_prompt = f"<knowledge>\n<long_term_memory>\n{memory_knowledge}\n</long_term_memory>\n</knowledge>\n\n{system_prompt}"
            logger.info("Injected %s relevant memories for bot '%s'.", len(transformed_memories), instance.bot_id)

    role_config = _resolve_role_config(bot, event, config)
    usage_manager = getattr(instance, '_usage_manager', None)
    if usage_manager is None:
        instance._usage_manager = UsageManager(token_calculator)
        usage_manager = instance._usage_manager

    if role_config:
        user_usage = await usage_manager.check_quota_and_get_usage(message_ctx.author.id, role_config)
        estimated_input_tokens = token_calculator.get_token_count_for_messages(
            [{"role": "system", "content": system_prompt}] + history_for_llm + [{"role": "user", "content": final_formatted_content}],
            config.get("llm_provider"), config.get("model_name")
        )
        quota_error = await usage_manager.check_pre_request_quota(message_ctx.author.id, role_config, user_usage, estimated_input_tokens)
        if quota_error:
            reset_channel_automation_state(message_ctx.channel.id, auto_message_counts, repeat_streaks)
            if runtime is not None:
                await runtime.send_message(
                    channel_id=str(getattr(message_ctx.channel, 'id', '')),
                    content=quota_error,
                    reply_to_message_id=str(getattr(message_ctx, 'id', None)),
                )
            else:
                await bot.send(event, quota_error, reply_message=True)
            return

    llm_messages = [{"role": "system", "content": system_prompt}] + history_for_llm + [{"role": "user", "content": final_formatted_content}]
    usage_data = None

    try:
        full_response = ""

        tools = plugin_manager.get_all_tools() if plugin_manager else []
        tool_functions = plugin_manager.get_all_tool_functions(message_ctx, config) if plugin_manager else {}
        used_tools_in_attempt = False

        pool = None
        from app.app_context import AppContext
        pool = AppContext.get().provider_pool

        try:
            logger.info(f"Attempting LLM call for message {message_ctx.id} with {len(tools)} tools.")
            if pool is not None:
                response_gen_with_tools = await pool.execute(
                    config, llm_messages, llm_images if is_multimodal_llm(config) else None,
                    tools=tools, tool_functions=tool_functions,
                )
            else:
                llm_provider = get_llm_provider(config)
                response_gen_with_tools = llm_provider.get_response_stream(
                    llm_messages, llm_images if is_multimodal_llm(config) else None,
                    tools=tools, tool_functions=tool_functions
                )
            if runtime is not None:
                full_response, usage_data = await render_streaming_response(
                    runtime, str(getattr(event, 'channel_id', '')), response_gen_with_tools,
                    reply_to_message_id=str(getattr(message_ctx, 'id', None)),
                )
            else:
                full_response, usage_data = await _render_streaming_response_old(bot, event, response_gen_with_tools)
            used_tools_in_attempt = bool(tools)
        except Exception as e:
            error_str = str(e).lower()
            if 'malformed' in error_str or 'tool_code' in error_str or 'function_call' in error_str:
                logger.warning(f"Malformed tool call for message {message_ctx.id}. Retrying without tools. Error: {e}")
                if pool is not None:
                    response_gen_no_tools = await pool.execute(
                        config, llm_messages, llm_images if is_multimodal_llm(config) else None,
                        tools=[], tool_functions={},
                    )
                else:
                    llm_provider = get_llm_provider(config)
                    response_gen_no_tools = llm_provider.get_response_stream(
                        llm_messages, llm_images if is_multimodal_llm(config) else None, tools=[], tool_functions={}
                    )
                if runtime is not None:
                    full_response, usage_data = await render_streaming_response(
                        runtime, str(getattr(event, 'channel_id', '')), response_gen_no_tools,
                        reply_to_message_id=str(getattr(message_ctx, 'id', None)),
                    )
                else:
                    full_response, usage_data = await _render_streaming_response_old(bot, event, response_gen_no_tools)
            else:
                raise e

        if used_tools_in_attempt and contains_dsml_tool_blocks(full_response):
            logger.warning(f"Detected leaked DSML tool blocks in message {message_ctx.id}. Retrying without tools.")
            if pool is not None:
                response_gen_no_tools = await pool.execute(
                    config, llm_messages, llm_images if is_multimodal_llm(config) else None,
                    tools=[], tool_functions={},
                )
            else:
                llm_provider = get_llm_provider(config)
                response_gen_no_tools = llm_provider.get_response_stream(
                    llm_messages, llm_images if is_multimodal_llm(config) else None, tools=[], tool_functions={}
                )
            if runtime is not None:
                full_response, usage_data = await render_streaming_response(
                    runtime, str(getattr(event, 'channel_id', '')), response_gen_no_tools,
                    reply_to_message_id=str(getattr(message_ctx, 'id', None)),
                )
            else:
                full_response, usage_data = await _render_streaming_response_old(bot, event, response_gen_no_tools)

        error_reason = None
        if not full_response or not full_response.strip():
            error_reason = "LLM returned an empty response."
        elif full_response.startswith("LLM_PROVIDER_ERROR:"):
            error_reason = full_response

        if error_reason:
            logger.error(f"Response error for user '{message_ctx.author.name}': {error_reason}")
            error_msg_template = config.get("blocked_prompt_response", "Sorry, an error occurred: {reason}")
            final_error_msg = error_msg_template.format(reason=error_reason)
            reset_channel_automation_state(message_ctx.channel.id, auto_message_counts, repeat_streaks)
            if runtime is not None:
                await runtime.send_message(
                    channel_id=str(getattr(message_ctx.channel, 'id', '')),
                    content=final_error_msg,
                    reply_to_message_id=str(getattr(message_ctx, 'id', None)),
                )
            else:
                await bot.send(event, final_error_msg, reply_message=True)
            return

        cleaned_response = await _process_knowledge_tags_adapted(
            bot, event, message_ctx, full_response, config
        )
        cleaned_response = strip_dsml_tool_blocks(cleaned_response)
        cleaned_response = strip_thinking_sections(cleaned_response)

        await add_capture({
            "trigger_message_id": str(message_ctx.id),
            "channel_id": str(message_ctx.channel.id),
            "guild_id": str(message_ctx.guild.id) if message_ctx.guild else None,
            "user_id": str(message_ctx.author.id),
            "user_name": message_ctx.author.name,
            "user_display_name": getattr(message_ctx.author, "display_name", message_ctx.author.name),
            "trigger_sources": trigger_sources,
            "plugin_outputs": plugin_append_blocks,
            "raw_user_message": str(message_ctx.content or ""),
            "formatted_user_request": final_formatted_content,
            "system_prompt": system_prompt,
            "history_for_llm": history_for_llm,
            "llm_messages": llm_messages,
            "intermediate_llm_responses": [],
            "raw_llm_response": full_response,
            "cleaned_llm_response": cleaned_response,
            "usage": usage_data,
            "provider": str(config.get("llm_provider", "")),
            "model": str(config.get("model_name", "")),
        })

        # NOTE: runtime is already acquired earlier

        final_chunks = split_message(cleaned_response, 2000)
        for i, chunk in enumerate(final_chunks):
            if not chunk.strip():
                continue
            if i == 0:
                if runtime is not None:
                    try:
                        await runtime.send_message(
                            channel_id=str(getattr(message_ctx.channel, 'id', '')),
                            content=chunk,
                            reply_to_message_id=str(getattr(message_ctx, 'id', None)),
                        )
                    except Exception as reply_err:
                        if "Unknown message" in str(reply_err) or "MESSAGE_REFERENCE_UNKNOWN" in str(reply_err):
                            logger.warning(f"Original message deleted, sending without reply: {reply_err}")
                            await runtime.send_message(
                                channel_id=str(getattr(message_ctx.channel, 'id', '')),
                                content=chunk,
                            )
                        else:
                            raise
                else:
                    try:
                        await bot.send(event, chunk, reply_message=True)
                    except Exception as reply_err:
                        if "Unknown message" in str(reply_err) or "MESSAGE_REFERENCE_UNKNOWN" in str(reply_err):
                            logger.warning(f"Original message deleted, sending without reply: {reply_err}")
                            await bot.send_to(channel_id=event.channel_id, message=chunk)
                        else:
                            raise
            else:
                if runtime is not None:
                    await runtime.send_message(
                        channel_id=str(getattr(message_ctx.channel, 'id', '')),
                        content=chunk,
                    )
                else:
                    await bot.send_to(channel_id=event.channel_id, message=chunk)

        reset_channel_automation_state(message_ctx.channel.id, auto_message_counts, repeat_streaks)

        await _record_bot_interaction(
            bot, config, message_ctx, cleaned_response, trigger_sources, downloaded_images
        )

        if usage_data:
            input_tokens = usage_data.get("input_tokens", 0)
            output_tokens = usage_data.get("output_tokens", 0)
            logger.info(f"Using official usage data: Input={input_tokens}, Output={output_tokens}")
        else:
            input_tokens = token_calculator.get_token_count_for_messages(llm_messages, config.get("llm_provider"), config.get("model_name"))
            output_tokens = token_calculator.get_token_count(full_response, config.get("llm_provider"), config.get("model_name"))
            logger.warning(f"No usage data from provider. Using estimated tokens: Input={input_tokens}, Output={output_tokens}")

        if usage_tracker:
            role_id_for_log = role_config.get('id') if role_config else None
            role_name_for_log = role_config.get('title') if role_config else None
            await usage_tracker.record_usage(
                provider=config.get("llm_provider"), model=config.get("model_name"),
                input_tokens=input_tokens, output_tokens=output_tokens,
                user_id=str(message_ctx.author.id), user_name=message_ctx.author.name,
                user_display_name=message_ctx.author.display_name,
                role_id=role_id_for_log, role_name=role_name_for_log,
                channel_id=str(message_ctx.channel.id), channel_name=getattr(message_ctx.channel, 'name', ''),
                guild_id=str(message_ctx.guild.id) if message_ctx.guild else None,
                guild_name=message_ctx.guild.name if message_ctx.guild and hasattr(message_ctx.guild, 'name') else None
            )
        if role_config:
            await usage_manager.update_post_request_usage(
                user_id=message_ctx.author.id, input_tokens=input_tokens, output_tokens=output_tokens
            )

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        error_msg = config.get("blocked_prompt_response", "Sorry, an error occurred: {reason}").format(reason="Internal Server Error")
        reset_channel_automation_state(message_ctx.channel.id, auto_message_counts, repeat_streaks)
        try:
            if runtime is not None:
                await runtime.send_message(
                    channel_id=str(getattr(message_ctx.channel, 'id', '')),
                    content=error_msg,
                    reply_to_message_id=str(getattr(message_ctx, 'id', None)),
                )
            else:
                await bot.send(event, error_msg, reply_message=True)
        except Exception as send_err:
            logger.warning(f"Failed to send error reply: {send_err}")
            try:
                if runtime is not None:
                    await runtime.send_message(
                        channel_id=str(getattr(message_ctx.channel, 'id', '')),
                        content=error_msg,
                    )
                else:
                    await bot.send_to(channel_id=event.channel_id, message=error_msg)
            except Exception:
                logger.error("Failed to send error reply without reply reference, giving up")


def _resolve_role_config(bot: Bot, event: MessageEvent, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    role_based = config.get("role_based_config", {})
    if not role_based:
        return None
    author_roles = []
    if hasattr(event, 'author') and hasattr(event.author, 'roles'):
        author_roles = getattr(event.author, 'roles', []) or []
    for role in reversed(author_roles):
        for cfg in role_based.values():
            if cfg.get("id") == str(getattr(role, 'id', '')):
                return cfg
    return None


async def _process_knowledge_tags_adapted(
    bot: Bot,
    event: MessageEvent,
    message_ctx: PlatformMessage,
    text: str,
    bot_config: Dict[str, Any],
) -> str:
    return await process_knowledge_tags_from_context(message_ctx, text, bot_config)


async def process_knowledge_tags_from_context(
    message_ctx: PlatformMessage,
    text: str,
    bot_config: Dict[str, Any],
) -> str:
    if not text:
        return text

    import re
    from app.core_logic.knowledge_manager import get_knowledge_manager

    cleaned_text = text
    knowledge_mgr = get_knowledge_manager()

    if '<memory>' in text:
        memories_to_add = re.findall(r'<memory>(.*?)</memory>', text, re.DOTALL)
        for memory_content in memories_to_add:
            stripped_content = memory_content.strip()
            if stripped_content and knowledge_mgr:
                timestamp = message_ctx.created_at.astimezone(__import__('datetime').timezone.utc).isoformat()
                user_id = str(message_ctx.author.id)
                user_name = message_ctx.author.name
                try:
                    ingest_result = await knowledge_mgr.ingest_memory_candidate(
                        content=stripped_content,
                        timestamp=timestamp,
                        user_id=user_id,
                        user_name=user_name,
                        source='ai_tag',
                        config=bot_config,
                        channel_id=str(message_ctx.channel.id),
                    )
                    status = ingest_result.get("status")
                    if status == "promoted":
                        logger.info("Promoted memory candidate from <memory> tag by '%s' as memory ID: %s", user_name, ingest_result.get("memory_id"))
                    elif status == "staged":
                        logger.info("Staged memory candidate from <memory> tag by '%s' (candidate ID: %s).", user_name, ingest_result.get("candidate_id"))
                except Exception as e:
                    logger.error(f"Error adding memory from tag by '{user_name}': {e}", exc_info=True)
        cleaned_text = re.sub(r'<memory>.*?</memory>', '', cleaned_text, flags=re.DOTALL)

    if '<user_info' in cleaned_text:
        from app.core_shared import _parse_user_info_fields
        user_info_tags = re.findall(r'<user_info\b(.*?)</user_info>', cleaned_text, re.DOTALL)
        for inner_text in user_info_tags:
            inner_text = inner_text.strip()
            if not inner_text:
                continue
            parsed = _parse_user_info_fields(inner_text)
            if not parsed:
                continue
            uid = parsed.get("id")
            keywords = parsed.get("keywords", "")
            content = parsed.get("content", "")
            if not content.strip():
                continue
            try:
                await knowledge_mgr.add_world_book_entry(
                    keywords=keywords,
                    content=content,
                    linked_user_id=uid,
                    source="ai_tag",
                )
                logger.info("Added world book entry from <user_info> tag: user=%s, keywords=%s",
                           uid or "none", keywords[:80])
            except Exception as e:
                logger.error(f"Error adding world book entry from <user_info> tag: {e}", exc_info=True)
        cleaned_text = re.sub(r'<user_info\b.*?</user_info>', '', cleaned_text, flags=re.DOTALL)

    return cleaned_text.strip()


async def _record_bot_interaction(
    bot: Bot,
    config: Dict[str, Any],
    message_ctx: PlatformMessage,
    bot_response: str,
    trigger_sources: List[str],
    downloaded_images: List[Dict[str, Any]],
) -> None:
    ih_config = config.get("interaction_history", {})
    if not ih_config.get("enabled", True):
        return
    try:
        from app.core_logic.interaction_recorder import get_interaction_recorder
        recorder = get_interaction_recorder()

        bot_id = str(getattr(bot, "self_id", "unknown"))
        guild_id = str(message_ctx.guild.id) if message_ctx.guild else "dm"
        channel_id = str(message_ctx.channel.id)

        role_id = "default"
        if message_ctx.guild and hasattr(message_ctx, 'author'):
            if hasattr(message_ctx.author, 'roles'):
                roles_list = getattr(message_ctx.author, 'roles', [])
                if roles_list:
                    role_id = str(roles_list[0])

        trigger_source_str = ",".join(trigger_sources) if trigger_sources else "unknown"

        member_name = getattr(message_ctx.author, "display_name", None) or getattr(message_ctx.author, "name", "") or str(getattr(message_ctx.author, "id", ""))

        await recorder.record_message(
            bot_id=bot_id,
            guild_id=guild_id,
            channel_id=channel_id,
            member_id=str(getattr(message_ctx.author, "id", bot_id)),
            member_name=member_name,
            role_id=role_id,
            content=bot_response,
            message_id="bot_reply_" + str(message_ctx.id),
            attachments=[],
            is_bot_reply=True,
            trigger_source=trigger_source_str,
        )

        if downloaded_images:
            image_bytes_list = []
            for img in downloaded_images:
                img_bytes = img.get("bytes")
                if img_bytes:
                    image_bytes_list.append(img_bytes)
            if image_bytes_list:
                from datetime import datetime, timezone
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                await recorder.record_images(
                    bot_id=bot_id,
                    guild_id=guild_id,
                    channel_id=channel_id,
                    member_id=str(getattr(message_ctx.author, "id", bot_id)),
                    role_id=role_id,
                    date_str=date_str,
                    message_id=str(message_ctx.id),
                    image_data_list=image_bytes_list,
                )
    except Exception:
        logger.debug("Failed to record bot interaction", exc_info=True)
