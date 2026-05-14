# backend/app/bot.py
import asyncio
import json
import logging
import os
import re
import redis
import socket
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TextIO, Tuple, AsyncGenerator

import discord
from discord.ext import commands

from .utils import TokenCalculator, split_message, transform_memories_for_prompt, matches_trigger_keywords
from .usage_tracker import usage_tracker
from .core_logic.usage_manager import UsageManager
from .core_logic.knowledge_manager import get_knowledge_manager
from .debug_capture_store import add_capture
from .llm_providers.factory import get_llm_provider
from .ocr_service import (
    is_multimodal_llm,
)
from plugins.manager import PluginManager
from .handlers.automation import track_auto_interject, track_repeat_parrot, reset_channel_automation_state
from .handlers.image_processor import collect_and_download_images, process_ocr_for_images, collect_image_descriptors
from .handlers.context_assembler import build_full_context
from .handlers.message_queue import MessageQueue

logger = logging.getLogger(__name__)

try:
    import fcntl  # type: ignore[attr-defined]
except ImportError:
    fcntl = None

try:
    import msvcrt  # type: ignore[attr-defined]
except ImportError:
    msvcrt = None

INSTANCE_ID = os.getenv("BOT_INSTANCE_ID") or f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"

# --- Hardened Redis connection handling ---
redis_client = None
try:
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    
    # 灏濊瘯杩炴帴 Redis
    _redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    _redis_client.ping()
    redis_client = _redis_client
    logger.info(f"[instance={INSTANCE_ID}] Successfully connected to Redis at {REDIS_HOST}:{REDIS_PORT}")

except redis.exceptions.ConnectionError as e:
    logger.error(f"[instance={INSTANCE_ID}] Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}. Error: {e}")
    # Check the environment flag to decide between fail-fast and mock fallback behavior.
    if os.getenv('FAIL_ON_REDIS_ERROR', 'false').lower() == 'true':
        logger.critical(f"[instance={INSTANCE_ID}] FAIL_ON_REDIS_ERROR is true. Terminating application.")
        # Raising an explicit exception here prevents bot.start() from running.
        raise RuntimeError("Redis connection failed.")
    else:
        # Use a minimal mock client so local development can continue without Redis.
        class MockRedis:
            def __init__(self):
                self._store = {}
            def set(self, key, value, *args, **kwargs):
                self._store[key] = value
                return True
            def get(self, key):
                return self._store.get(key)
            def ping(self):
                return True
            def delete(self, key):
                return self._store.pop(key, None) is not None
            def exists(self, key):
                return key in self._store
        redis_client = MockRedis()
        logger.warning(f"[instance={INSTANCE_ID}] FAIL_ON_REDIS_ERROR is not set to true. Using a mock Redis client. CONCURRENCY PROTECTION IS DISABLED.")


from pathlib import Path
from .config_cache import load_config, DATA_DIR

def _get_bot_lock_path(bot_id: str):
    return DATA_DIR / f"discord_bot_{bot_id}.lock"
bot_instance = None
token_calculator = TokenCalculator()


def _try_acquire_bot_process_lock(bot_id: str = "main") -> Optional[TextIO]:
    lock_file = _get_bot_lock_path(bot_id); lock_file.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_file, "a+", encoding="utf-8")
    try:
        handle.seek(0)
        if not handle.read(1):
            handle.write(" ")
            handle.flush()
        handle.seek(0)

        if os.name == "nt":
            if msvcrt is None:
                raise RuntimeError("msvcrt is required to guard the Discord bot process on Windows.")
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        elif fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            raise RuntimeError("No supported file locking primitive is available for Discord bot startup.")

        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        return handle
    except OSError:
        handle.close()
        return None
    except Exception:
        handle.close()
        raise


def _release_bot_process_lock(handle: Optional[TextIO], bot_id: str = "main") -> None:
    if not handle:
        return

    try:
        handle.seek(0)
        handle.truncate()
        handle.write("")
        handle.flush()
        handle.seek(0)

        if os.name == "nt":
            if msvcrt is not None:
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        elif fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        logger.warning("Failed to release Discord bot process lock cleanly.", exc_info=True)
    finally:
        handle.close()

def load_bot_config():
    return load_config()

async def process_knowledge_tags(message: discord.Message, text: str, bot_config: Dict[str, Any]) -> str:
    """
    Finds <memory> and <user_info> tags in the text, stores their content appropriately,
    and returns the text with the tags removed.
    """
    if not text:
        return text

    cleaned_text = text

    # --- <memory> tag handling ---
    if '<memory>' in text:
        memories_to_add = re.findall(r'<memory>(.*?)</memory>', text, re.DOTALL)
        for memory_content in memories_to_add:
            stripped_content = memory_content.strip()
            if stripped_content:
                timestamp = message.created_at.astimezone(timezone.utc).isoformat()
                user_id = str(message.author.id)
                user_name = message.author.name
                try:
                    ingest_result = get_knowledge_manager().ingest_memory_candidate(
                        content=stripped_content,
                        timestamp=timestamp,
                        user_id=user_id,
                        user_name=user_name,
                        source='ai_tag',
                        config=bot_config,
                        channel_id=str(message.channel.id),
                    )
                    status = ingest_result.get("status")
                    if status == "promoted":
                        logger.info(
                            "Promoted memory candidate from <memory> tag by '%s' as memory ID: %s",
                            user_name,
                            ingest_result.get("memory_id"),
                        )
                    elif status == "staged":
                        logger.info(
                            "Staged memory candidate from <memory> tag by '%s' (candidate ID: %s).",
                            user_name,
                            ingest_result.get("candidate_id"),
                        )
                    elif status == "duplicate_existing":
                        logger.info(
                            "Memory tag by '%s' matched existing memory ID: %s",
                            user_name,
                            ingest_result.get("memory_id"),
                        )
                    else:
                        logger.info(
                            "Memory tag by '%s' skipped with status '%s': '%s...'",
                            user_name,
                            status,
                            stripped_content[:50],
                        )
                except Exception as e:
                    logger.error(f"Error adding memory from tag by '{user_name}': {e}", exc_info=True)
        cleaned_text = re.sub(r'<memory>.*?</memory>', '', cleaned_text, flags=re.DOTALL)

    # --- <user_info> tag handling ---
    if '<user_info' in cleaned_text:
        from .core_logic.user_validator import validate_user_id
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
            if uid is not None:
                if message.guild:
                    member = await validate_user_id(uid, message.guild)
                    if member is None:
                        logger.warning(
                            "User ID %s from <user_info> tag not found in guild, skipping",
                            uid,
                        )
                        uid = uid
                    else:
                        uid = str(member.id)
                        logger.info(
                            "Validated user ID %s (%s) from <user_info> tag",
                            uid,
                            member.display_name,
                        )
            try:
                get_knowledge_manager().add_world_book_entry(
                    keywords=keywords,
                    content=content,
                    linked_user_id=uid,
                    source="ai_tag",
                )
                logger.info(
                    "Added world book entry from <user_info> tag: user=%s, keywords=%s",
                    uid or "none",
                    keywords[:80],
                )
            except Exception as e:
                logger.error(f"Error adding world book entry from <user_info> tag: {e}", exc_info=True)
        cleaned_text = re.sub(r'<user_info\b.*?</user_info>', '', cleaned_text, flags=re.DOTALL)

    return cleaned_text.strip()


def _parse_user_info_fields(inner_text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    pos = 0
    while pos < len(inner_text):
        eq_pos = inner_text.find('=', pos)
        if eq_pos == -1:
            break
        key = inner_text[pos:eq_pos].strip()
        if key not in ("id", "keywords", "content"):
            break
        val_start = eq_pos + 1
        if key == "content":
            result["content"] = inner_text[val_start:]
            break
        next_semi = inner_text.find(';', val_start)
        if next_semi == -1:
            result[key] = inner_text[val_start:].strip()
            break
        val = inner_text[val_start:next_semi]
        result[key] = val.strip()
        pos = next_semi + 1
    return result


def strip_thinking_sections(text: str) -> str:
    """Remove any leaked internal thinking blocks from model output."""
    if not text:
        return text
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.IGNORECASE | re.DOTALL)
    return cleaned.strip()


def strip_dsml_tool_blocks(text: str) -> str:
    """Remove leaked DSML function-call blocks from model output."""
    if not text:
        return text
    cleaned = text
    # 1) Remove full function_calls blocks (supports styles like `< | DSML | ... >` and `< / | DSML | ... >`).
    cleaned = re.sub(
        r"<\s*/?\s*\|\s*DSML\s*\|\s*function_calls\s*>[\s\S]*?<\s*/?\s*\|\s*DSML\s*\|\s*function_calls\s*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # 2) Remove any remaining lines containing DSML tags to avoid inline parameter leaks.
    cleaned = re.sub(
        r"(?im)^[^\n\r]*<\s*/?\s*\|\s*DSML\s*\|[^\n\r]*$",
        "",
        cleaned,
    )
    # 3) Defensive pass for malformed inline DSML tags.
    cleaned = re.sub(
        r"<\s*/?\s*\|\s*DSML\s*\|[^>]*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def contains_dsml_tool_blocks(text: str) -> bool:
    if not text:
        return False
    return bool(
        re.search(
            r"<\s*/?\s*\|\s*DSML\s*\|\s*(function_calls|invoke|parameter)\b",
            text,
            flags=re.IGNORECASE,
        )
    )


async def run_bot(memory_cutoffs: Dict[int, datetime]):
    global bot_instance
    logger.info(f"[instance={INSTANCE_ID}] run_bot starting.")
    
    config = load_bot_config()
    discord_token = config.get("discord_token")
    
    if not discord_token or not isinstance(discord_token, str) or len(discord_token) < 50:
        logger.critical("FATAL: Discord token is missing, invalid, or too short in config.json. Bot cannot start.")
        # In async startup code, raising an exception is the clearest way to abort launch.
        raise ValueError("Invalid Discord token provided.")

    if os.getenv("DISCORD_BOT_AUTOSTART", "true").strip().lower() not in {"1", "true", "yes", "on"}:
        logger.info(f"[instance={INSTANCE_ID}] DISCORD_BOT_AUTOSTART is disabled. Skipping Discord bot startup.")
        return

    bot_process_lock: Optional[TextIO] = None
    for attempt in range(15):
        bot_process_lock = _try_acquire_bot_process_lock('main')
        if bot_process_lock is not None:
            logger.info(f"[instance={INSTANCE_ID}] Acquired Discord bot process lock on attempt {attempt + 1}.")
            break

        if attempt == 0:
            logger.warning(
                f"[instance={INSTANCE_ID}] Another app.main process is already holding the Discord bot lock. "
                "Waiting briefly before giving up."
            )
        await asyncio.sleep(1)

    if bot_process_lock is None:
        logger.warning(
            f"[instance={INSTANCE_ID}] Could not acquire the Discord bot process lock after retries. "
            "This process will keep the API server alive but will not connect a second Discord bot instance."
        )
        return
    
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)
    bot_instance = bot
    
    # Initialize managers
    # This function needs to be defined within the bot's execution scope
    # so it can access the correct LLM provider instance.
    async def get_llm_response(messages: List[Dict[str, Any]], images: Optional[List[Dict[str, bytes]]] = None) -> str:
        """
        An inner helper function to get a non-streaming LLM response for plugins.
        """
        logger.info(f"[instance={INSTANCE_ID}] Plugin triggered LLM call with {len(messages)} messages.")
        # Use the existing llm_provider instance from the current bot session
        llm_provider = get_llm_provider(config)
        
        full_response = ""
        try:
            # Use get_response_stream and iterate to get the final result
            response_generator = llm_provider.get_response_stream(messages, images, tools=[], tool_functions={})
            async for response_type, data in response_generator:
                if response_type == "final":
                    full_response = data
                    break
        except Exception as e:
            logger.error(f"Error getting LLM response for plugin: {e}", exc_info=True)
            return f"LLM_PROVIDER_ERROR: {e}"

        logger.info(f"[instance={INSTANCE_ID}] LLM response for plugin: {full_response[:100]}...")
        return full_response

    plugin_manager = PluginManager(config.get("plugins", {}), get_llm_response)
    knowledge_mgr = get_knowledge_manager()
    usage_manager = UsageManager(token_calculator)
    auto_message_counts: Dict[int, int] = {}
    repeat_streaks: Dict[int, Dict[str, Any]] = {}

    def _reset_channel_automation_state(channel_id: int) -> None:
        reset_channel_automation_state(channel_id, auto_message_counts, repeat_streaks)

    def _track_auto_interject_call(message: discord.Message, bot_config: Dict[str, Any]) -> bool:
        return track_auto_interject(message, bot_config, auto_message_counts)

    def _track_repeat_parrot_call(message: discord.Message, bot_config: Dict[str, Any]) -> Optional[str]:
        return track_repeat_parrot(message, bot_config, repeat_streaks)

    @bot.event
    async def on_ready():
        logger.info(f"[instance={INSTANCE_ID}] {bot.user} has connected to Discord!")

    message_queue = MessageQueue()
    _channel_processors: Dict[str, asyncio.Task] = {}

    async def _handle_triggered_message(ctx: dict) -> None:
        message: discord.Message = ctx["message"]
        trigger_sources: List[str] = ctx["trigger_sources"]
        injected_data: Optional[str] = ctx["injected_data"]
        plugin_append_blocks: List[str] = ctx["plugin_append_blocks"]

        lock_key = f"discord:message_lock:{message.id}"
        is_lock_acquired = redis_client.set(lock_key, "processing", nx=True, ex=60)
        if not is_lock_acquired:
            logger.info(f"[instance={INSTANCE_ID}] Triggering message {message.id} is already being processed. Skipping.")
            return

        logger.info(f"[instance={INSTANCE_ID}] Acquired lock for triggering message {message.id}. Processing...")

        config = load_bot_config()

        downloaded_images = await collect_and_download_images(message)
        llm_images = [item["bytes"] for item in downloaded_images]

        system_prompt, final_formatted_content, history_for_llm, history_messages, role_name, role_config = await build_full_context(
            bot, config, message, memory_cutoffs, injected_data
        )

        if downloaded_images and not is_multimodal_llm(config):
            final_formatted_content = await process_ocr_for_images(downloaded_images, config, final_formatted_content)

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
        relevant_memories = await get_knowledge_manager().get_relevant_memories(
            query_text=message.content or "",
            top_k=recall_top_k,
            char_limit=recall_char_limit,
            max_age_days=recall_max_age_days,
            config=config,
        )
        if relevant_memories:
            transformed_memories = transform_memories_for_prompt(relevant_memories, target_timezone_str='UTC')
            memory_knowledge = "\n".join(transformed_memories)
            system_prompt = f"<knowledge>\n<long_term_memory>\n{memory_knowledge}\n</long_term_memory>\n</knowledge>\n\n{system_prompt}"
            logger.info(
                "[instance=%s] Injected %s relevant memories into the system prompt (top_k=%s, char_limit=%s).",
                INSTANCE_ID,
                len(transformed_memories),
                recall_top_k,
                recall_char_limit,
            )

        if role_config:
            user_usage = await usage_manager.check_quota_and_get_usage(message.author.id, role_config)
            estimated_input_tokens = token_calculator.get_token_count_for_messages(
                [{"role": "system", "content": system_prompt}] + history_for_llm + [{"role": "user", "content": final_formatted_content}],
                config.get("llm_provider"),
                config.get("model_name")
            )
            quota_error = await usage_manager.check_pre_request_quota(message.author.id, role_config, user_usage, estimated_input_tokens)
            if quota_error:
                _reset_channel_automation_state(message.channel.id)
                await message.reply(quota_error, mention_author=False)
                return

        llm_messages = [{"role": "system", "content": system_prompt}] + history_for_llm + [{"role": "user", "content": final_formatted_content}]
        usage_data = None

        try:
            full_response = ""
            usage_data = None
            final_response_stages: List[str] = []

            async with message.channel.typing():
                response_message = None

                async def _render_llm_response(
                    response_generator: AsyncGenerator[Tuple[str, Any], None]
                ) -> Tuple[str, Optional[Dict[str, int]], List[str]]:
                    nonlocal response_message
                    _full_response = ""
                    _usage_data = None
                    _final_responses: List[str] = []
                    async for response_type, data in response_generator:
                        if response_type == "partial":
                            content_chunks = split_message(data, 2000)
                            current_chunk = content_chunks[0] if content_chunks else ""
                            if response_message is None and current_chunk.strip():
                                response_message = await message.reply(current_chunk, mention_author=False)
                            elif response_message and current_chunk and current_chunk != response_message.content:
                                try:
                                    await response_message.edit(content=current_chunk)
                                except discord.errors.HTTPException: pass
                        elif response_type == "final":
                            _full_response = str(data or "")
                            _final_responses.append(_full_response)
                        elif response_type == "usage":
                            _usage_data = data
                    return _full_response, _usage_data, _final_responses

                llm_provider = get_llm_provider(config)
                tools = plugin_manager.get_all_tools()
                tool_functions = plugin_manager.get_all_tool_functions(message, config)
                used_tools_in_attempt = False
                try:
                    logger.info(f"[instance={INSTANCE_ID}] Attempting LLM call for message {message.id} with {len(tools)} tools enabled.")
                    response_gen_with_tools = llm_provider.get_response_stream(
                        llm_messages, llm_images if is_multimodal_llm(config) else None, tools=tools, tool_functions=tool_functions
                    )
                    full_response, usage_data, final_response_stages = await _render_llm_response(response_gen_with_tools)
                    used_tools_in_attempt = bool(tools)
                except Exception as e:
                    error_str = str(e).lower()
                    if 'malformed' in error_str or 'tool_code' in error_str or 'function_call' in error_str:
                        logger.warning(f"Malformed tool call from LLM for message {message.id}. Retrying without tools. Original error: {e}")
                        response_gen_no_tools = llm_provider.get_response_stream(
                            llm_messages, llm_images if is_multimodal_llm(config) else None, tools=[], tool_functions={}
                        )
                        full_response, usage_data, final_response_stages = await _render_llm_response(response_gen_no_tools)
                    else:
                        raise e

                if used_tools_in_attempt and contains_dsml_tool_blocks(full_response):
                    logger.warning(
                        f"[instance={INSTANCE_ID}] Detected leaked DSML tool blocks in message {message.id}. Retrying without tools."
                    )
                    response_gen_no_tools = llm_provider.get_response_stream(
                        llm_messages, llm_images if is_multimodal_llm(config) else None, tools=[], tool_functions={}
                    )
                    full_response, usage_data, final_response_stages = await _render_llm_response(response_gen_no_tools)

                error_reason = None
                if not full_response or not full_response.strip():
                    error_reason = "LLM returned an empty response."
                elif full_response.startswith("LLM_PROVIDER_ERROR:"):
                    error_reason = full_response

                if error_reason:
                    logger.error(f"Response error for user '{message.author.name}': {error_reason}")
                    error_msg_template = config.get("blocked_prompt_response", "Sorry, an error occurred: {reason}")
                    final_error_msg = error_msg_template.format(reason=error_reason)
                    _reset_channel_automation_state(message.channel.id)
                    if response_message:
                        await response_message.edit(content=final_error_msg)
                    else:
                        await message.reply(final_error_msg, mention_author=False)
                    return

                cleaned_response = await process_knowledge_tags(message, full_response, config)
                cleaned_response = strip_dsml_tool_blocks(cleaned_response)
                cleaned_response = strip_thinking_sections(cleaned_response)

                await add_capture({
                    "trigger_message_id": str(message.id),
                    "channel_id": str(message.channel.id),
                    "guild_id": str(message.guild.id) if message.guild else None,
                    "user_id": str(message.author.id),
                    "user_name": message.author.name,
                    "user_display_name": getattr(message.author, "display_name", message.author.name),
                    "trigger_sources": trigger_sources,
                    "plugin_outputs": plugin_append_blocks,
                    "raw_user_message": str(message.content or ""),
                    "formatted_user_request": final_formatted_content,
                    "system_prompt": system_prompt,
                    "history_for_llm": history_for_llm,
                    "llm_messages": llm_messages,
                    "intermediate_llm_responses": final_response_stages[:-1],
                    "raw_llm_response": full_response,
                    "cleaned_llm_response": cleaned_response,
                    "usage": usage_data,
                    "provider": str(config.get("llm_provider", "")),
                    "model": str(config.get("model_name", "")),
                })

                if response_message:
                    final_chunks = split_message(cleaned_response, 2000)
                    await response_message.edit(content=final_chunks[0] if final_chunks else "")
                    for chunk in final_chunks[1:]:
                        await message.channel.send(chunk)
                else:
                    final_chunks = split_message(cleaned_response, 2000)
                    for i, chunk in enumerate(final_chunks):
                        if i == 0 and chunk.strip():
                            await message.reply(chunk, mention_author=False)
                        elif i > 0:
                            await message.channel.send(chunk)

                _reset_channel_automation_state(message.channel.id)

            if usage_data:
                input_tokens = usage_data.get("input_tokens", 0)
                output_tokens = usage_data.get("output_tokens", 0)
                logger.info(f"[instance={INSTANCE_ID}] Using official usage data: Input={input_tokens}, Output={output_tokens}")
            else:
                provider, model = config.get("llm_provider"), config.get("model_name")
                input_tokens = token_calculator.get_token_count_for_messages(llm_messages, provider, model)
                output_tokens = token_calculator.get_token_count(full_response, provider, model)
                logger.warning(f"No usage data from provider. Using estimated tokens: Input={input_tokens}, Output={output_tokens}")

            await usage_tracker.record_usage(
                provider=config.get("llm_provider"), model=config.get("model_name"),
                input_tokens=input_tokens, output_tokens=output_tokens,
                user_id=str(message.author.id), user_name=message.author.name,
                user_display_name=message.author.display_name,
                role_id=role_config.get('id') if role_config else None, role_name=role_name,
                channel_id=str(message.channel.id), channel_name=message.channel.name,
                guild_id=str(message.guild.id) if message.guild else None,
                guild_name=message.guild.name if message.guild else None
            )

            if role_config:
                await usage_manager.update_post_request_usage(
                    user_id=message.author.id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens
                )

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            error_msg = config.get("blocked_prompt_response", "Sorry, an error occurred: {reason}").format(reason="Internal Server Error")
            _reset_channel_automation_state(message.channel.id)
            await message.reply(error_msg, mention_author=False)

    async def _ensure_channel_processor(channel_id_str: str) -> None:
        if channel_id_str in _channel_processors and not _channel_processors[channel_id_str].done():
            return
        cid = channel_id_str
        task = asyncio.create_task(
            message_queue.process_channel(cid, _handle_triggered_message)
        )
        _channel_processors[cid] = task
        task.add_done_callback(lambda t, c=cid: _channel_processors.pop(c, None))
        logger.info(f"[instance={INSTANCE_ID}] Started queue processor for channel {cid}")

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return

        config = load_bot_config()
        auto_interject_triggered = _track_auto_interject_call(message, config)
        repeat_parrot_content = _track_repeat_parrot_call(message, config)

        trigger_keywords = config.get("trigger_keywords", [])
        trigger_match_mode = config.get("trigger_match_mode", "contains")
        trigger_case_sensitive = bool(config.get("trigger_case_sensitive", False))
        is_mentioned = bot.user in message.mentions
        is_reply_to_bot = (
            message.reference
            and isinstance(message.reference.resolved, discord.Message)
            and message.reference.resolved.author == bot.user
        )
        has_trigger_keyword = matches_trigger_keywords(
            message.content,
            trigger_keywords,
            match_mode=trigger_match_mode,
            case_sensitive=trigger_case_sensitive,
        )
        normal_triggered = is_mentioned or is_reply_to_bot or has_trigger_keyword

        plugin_runtime_config = dict(config)
        plugin_runtime_config["_runtime_normal_triggered"] = normal_triggered
        plugin_result = await plugin_manager.process_message(message, plugin_runtime_config)
        if plugin_result is True:
            return

        plugin_append_blocks: List[str] = []
        injected_data = None
        plugin_append_triggered = False
        if isinstance(plugin_result, tuple) and plugin_result[0] == 'append':
            plugin_append_blocks = [str(item) for item in plugin_result[1] if str(item).strip()]
            injected_data = "\n".join(plugin_append_blocks)
            plugin_append_triggered = bool(plugin_append_blocks)

        if not normal_triggered and repeat_parrot_content:
            await message.channel.send(repeat_parrot_content)
            logger.info(f"[instance={INSTANCE_ID}] Repeat parrot triggered in channel {message.channel.id} after repeated content.")
            _reset_channel_automation_state(message.channel.id)
            return

        if not (normal_triggered or auto_interject_triggered or plugin_append_triggered):
            return

        if plugin_append_triggered and not (normal_triggered or auto_interject_triggered):
            logger.info(f"[instance={INSTANCE_ID}] Continuing due to plugin append trigger for message {message.id}.")

        if auto_interject_triggered and not normal_triggered:
            logger.info(f"[instance={INSTANCE_ID}] Auto interject triggered in channel {message.channel.id} after configured interval.")

        trigger_sources: List[str] = []
        if normal_triggered:
            trigger_sources.append("normal")
        if auto_interject_triggered:
            trigger_sources.append("auto_interject")
        if plugin_append_triggered:
            trigger_sources.append("plugin_append")

        channel_id_str = str(message.channel.id)
        ctx = {
            "message": message,
            "trigger_sources": trigger_sources,
            "injected_data": injected_data,
            "plugin_append_blocks": plugin_append_blocks,
        }

        enqueued = await message_queue.enqueue(channel_id_str, ctx)
        if not enqueued:
            await message.reply("Bot is busy, please try later.", mention_author=False)
            return

        await _ensure_channel_processor(channel_id_str)
    
    try:
        await bot.start(discord_token)
    except asyncio.CancelledError:
        logger.info(f"[instance={INSTANCE_ID}] Discord bot task cancelled.")
        raise
    except ValueError as e:  # Catch the explicit configuration error raised above.
        logger.critical(f"[instance={INSTANCE_ID}] Terminating due to configuration error: {e}")
    except discord.errors.LoginFailure:
        logger.critical(f"[instance={INSTANCE_ID}] FATAL: Login failed. The provided Discord token is incorrect. Please check your config.json.")
    except Exception as e:
        logger.error(f"[instance={INSTANCE_ID}] Bot failed to start: {e}", exc_info=True)
    finally:
        if not bot.is_closed():
            await bot.close()
        _release_bot_process_lock(bot_process_lock, 'main')


async def run_bot_instance(instance) -> None:
    """Bridge function: delegates to the BotInstance's _run_discord() method."""
    await instance._run_discord()


