import asyncio
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

from .config_cache import load_config, save_config, get_bot_config_path, get_bot_knowledge_path, get_bot_usage_path, DEFAULT_CONFIG, BOTS_DIR

logger = logging.getLogger(__name__)


class BotInstance:
    def __init__(self, bot_id: str):
        self.bot_id = bot_id
        self.config: Dict[str, Any] = {}
        self.platform: str = "discord"
        self.status: str = "stopped"
        self._task: Optional[asyncio.Task] = None
        self._client: Any = None
        self.memory_cutoffs: Dict[int, datetime] = {}
        self.auto_message_counts: Dict[int, int] = {}
        self.started_at: Optional[datetime] = None
        self._usage_tracker = None
        self._knowledge_manager = None
        self._plugin_manager = None
        self._usage_manager = None
        self._bot_process_lock = None

    @property
    def config_dir(self) -> Path:
        return BOTS_DIR / self.bot_id

    @property
    def config_path(self) -> Path:
        return get_bot_config_path(self.bot_id)

    @property
    def knowledge_path(self) -> Path:
        return get_bot_knowledge_path(self.bot_id)

    @property
    def usage_path(self) -> Path:
        return get_bot_usage_path(self.bot_id)

    def load_config(self) -> Dict[str, Any]:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if self.config_path.exists():
            import json
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            from .config_cache import _set_defaults_recursive
            _set_defaults_recursive(DEFAULT_CONFIG, data)
            if not data.get("api_secret_key"):
                data["api_secret_key"] = secrets.token_hex(32)
                logger.warning("api_secret_key was empty in per-bot config, generated a new one")
            global_key = load_config().get("api_secret_key")
            if global_key:
                data["api_secret_key"] = global_key
        else:
            from copy import deepcopy
            data = deepcopy(DEFAULT_CONFIG)
            data["bot_id"] = self.bot_id
            with open(self.config_path, "w", encoding="utf-8") as f:
                import json
                json.dump(data, f, indent=2, ensure_ascii=False)
        self.config = data
        self.config["bot_id"] = self.bot_id
        self.platform = data.get("platform", "discord")
        return self.config

    def save_config(self, config_dict: Dict[str, Any]) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        import json
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
        self.config = config_dict

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.is_running():
            logger.warning(f"Bot '{self.bot_id}' is already running.")
            return
        self.load_config()
        if not self.config.get("enabled", True):
            logger.info(f"Bot '{self.bot_id}' is disabled. Skipping start.")
            return
        self.status = "starting"
        self.started_at = datetime.now(timezone.utc)
        if self.platform == "discord":
            self._task = asyncio.create_task(self._run_discord())
        elif self.platform == "qq":
            self._task = asyncio.create_task(self._run_qq())
        else:
            logger.warning(f"Platform '{self.platform}' not yet implemented for bot '{self.bot_id}'.")
            self.status = "error"
            self.started_at = None
            return

    async def stop(self) -> None:
        if not self.is_running():
            return
        self.status = "stopped"
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self._client = None
        self.started_at = None
        self._usage_tracker = None
        self._knowledge_manager = None
        self._plugin_manager = None
        self._usage_manager = None
        logger.info(f"Bot '{self.bot_id}' stopped.")

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    def to_status_dict(self) -> Dict[str, Any]:
        uptime = None
        if self.started_at and self.is_running():
            uptime = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return {
            "bot_id": self.bot_id,
            "bot_name": self.config.get("bot_name", "Unnamed Bot"),
            "platform": self.platform,
            "enabled": self.config.get("enabled", True),
            "status": self.status,
            "uptime_seconds": uptime,
        }

    async def _run_discord(self):
        import json
        import os
        import re
        import redis
        import socket
        import uuid
        from typing import Tuple, AsyncGenerator

        import discord
        from discord.ext import commands

        from .utils import TokenCalculator, split_message, transform_memories_for_prompt, matches_trigger_keywords
        from .usage_tracker import UsageTracker
        from .core_logic.usage_manager import UsageManager
        from .core_logic.knowledge_manager import KnowledgeManager
        from .debug_capture_store import add_capture
        from .llm_providers.factory import get_llm_provider
        from .ocr_service import is_multimodal_llm
        from plugins.manager import PluginManager
        from .handlers.automation import track_auto_interject, track_repeat_parrot, reset_channel_automation_state
        from .handlers.image_processor import collect_and_download_images, process_ocr_for_images
        from .handlers.context_assembler import build_full_context
        from .handlers.message_queue import MessageQueue
        from .bot import (
            INSTANCE_ID, redis_client, _try_acquire_bot_process_lock,
            _release_bot_process_lock, process_knowledge_tags,
            strip_thinking_sections, strip_dsml_tool_blocks,
            contains_dsml_tool_blocks, token_calculator as shared_token_calc,
        )

        logger.info(f"[instance={INSTANCE_ID}] BotInstance._run_discord starting for bot '{self.bot_id}'.")

        config = self.config
        discord_token = config.get("discord_token")

        if not discord_token or not isinstance(discord_token, str) or len(discord_token) < 50:
            logger.critical(f"FATAL: Discord token is missing for bot '{self.bot_id}'.")
            self.status = "error"
            return

        if os.getenv("DISCORD_BOT_AUTOSTART", "true").strip().lower() not in {"1", "true", "yes", "on"}:
            logger.info(f"DISCORD_BOT_AUTOSTART is disabled. Skipping bot '{self.bot_id}'.")
            return

        bot_process_lock = None
        if not os.getenv("DISCORD_SKIP_PROCESS_LOCK", "").lower() in {"1", "true", "yes"}:
            for attempt in range(15):
                bot_process_lock = _try_acquire_bot_process_lock()
                if bot_process_lock is not None:
                    logger.info(f"[instance={INSTANCE_ID}] Acquired lock on attempt {attempt + 1} for bot '{self.bot_id}'.")
                    break
                if attempt == 0:
                    logger.warning(f"Waiting for process lock for bot '{self.bot_id}'...")
                await asyncio.sleep(1)
            if bot_process_lock is None:
                logger.warning(f"Could not acquire process lock for bot '{self.bot_id}'. Skipping.")
                return
        self._bot_process_lock = bot_process_lock

        intents = discord.Intents.default()
        intents.message_content = True
        bot = commands.Bot(command_prefix='!', intents=intents)
        self._client = bot

        # Per-instance managers
        self._usage_tracker = UsageTracker(data_file=str(self.usage_path))
        self._knowledge_manager = KnowledgeManager(db_path=str(self.knowledge_path))
        self._plugin_manager = PluginManager(config.get("plugins", {}), None)
        self._usage_manager = UsageManager(shared_token_calc)
        repeat_streaks: Dict[int, Dict[str, Any]] = {}

        async def get_llm_response(messages: List[Dict[str, Any]], images=None) -> str:
            logger.info(f"Plugin triggered LLM call for bot '{self.bot_id}' with {len(messages)} messages.")
            llm_provider = get_llm_provider(config)
            full_response = ""
            try:
                response_generator = llm_provider.get_response_stream(messages, images, tools=[], tool_functions={})
                async for response_type, data in response_generator:
                    if response_type == "final":
                        full_response = data
                        break
            except Exception as e:
                logger.error(f"Error getting LLM response for plugin: {e}", exc_info=True)
                return f"LLM_PROVIDER_ERROR: {e}"
            return full_response

        self._plugin_manager = PluginManager(config.get("plugins", {}), get_llm_response)
        _instance = self

        def _reset_channel_automation_state(channel_id: int) -> None:
            reset_channel_automation_state(channel_id, _instance.auto_message_counts, repeat_streaks)

        def _track_auto_interject_call(message, bot_config) -> bool:
            return track_auto_interject(message, bot_config, _instance.auto_message_counts)

        def _track_repeat_parrot_call(message, bot_config) -> Optional[str]:
            return track_repeat_parrot(message, bot_config, repeat_streaks)

        @bot.event
        async def on_ready():
            logger.info(f"[instance={INSTANCE_ID}] {bot.user} has connected for bot '{self.bot_id}'!")

        message_queue = MessageQueue()
        _channel_processors: Dict[str, asyncio.Task] = {}

        async def _handle_triggered_message(ctx: dict) -> None:
            message: discord.Message = ctx["message"]
            trigger_sources: List[str] = ctx["trigger_sources"]
            injected_data: Optional[str] = ctx["injected_data"]
            plugin_append_blocks: List[str] = ctx["plugin_append_blocks"]
            _cfg = _instance.config

            lock_key = f"discord:message_lock:{message.id}"
            is_lock_acquired = redis_client.set(lock_key, "processing", nx=True, ex=60)
            if not is_lock_acquired:
                logger.info(f"Message {message.id} already being processed. Skipping.")
                return

            logger.info(f"Processing message {message.id} for bot '{_instance.bot_id}'.")

            downloaded_images = await collect_and_download_images(message)
            llm_images = [item["bytes"] for item in downloaded_images]

            system_prompt, final_formatted_content, history_for_llm, history_messages, role_name, role_config = await build_full_context(
                bot, _cfg, message, _instance.memory_cutoffs, injected_data
            )

            if downloaded_images and not is_multimodal_llm(_cfg):
                final_formatted_content = await process_ocr_for_images(downloaded_images, _cfg, final_formatted_content)

            try:
                recall_top_k = max(1, min(50, int(_cfg.get("auto_memory_recall_top_k", 12))))
            except (TypeError, ValueError):
                recall_top_k = 12
            try:
                recall_char_limit = max(300, min(20000, int(_cfg.get("auto_memory_recall_char_limit", 2200))))
            except (TypeError, ValueError):
                recall_char_limit = 2200
            try:
                recall_max_age_days = max(1, min(3650, int(_cfg.get("auto_memory_recall_max_age_days", 365))))
            except (TypeError, ValueError):
                recall_max_age_days = 365
            relevant_memories = await _instance._knowledge_manager.get_relevant_memories(
                query_text=message.content or "",
                top_k=recall_top_k, char_limit=recall_char_limit, max_age_days=recall_max_age_days,
                config=_cfg,
            )
            if relevant_memories:
                transformed_memories = transform_memories_for_prompt(relevant_memories, target_timezone_str='UTC')
                memory_knowledge = "\n".join(transformed_memories)
                system_prompt = f"<knowledge>\n<long_term_memory>\n{memory_knowledge}\n</long_term_memory>\n</knowledge>\n\n{system_prompt}"
                logger.info("Injected %s relevant memories for bot '%s'.", len(transformed_memories), _instance.bot_id)

            role_config = _resolve_role_config(message, _cfg)

            if role_config:
                user_usage = await _instance._usage_manager.check_quota_and_get_usage(message.author.id, role_config)
                estimated_input_tokens = shared_token_calc.get_token_count_for_messages(
                    [{"role": "system", "content": system_prompt}] + history_for_llm + [{"role": "user", "content": final_formatted_content}],
                    _cfg.get("llm_provider"), _cfg.get("model_name")
                )
                quota_error = await _instance._usage_manager.check_pre_request_quota(message.author.id, role_config, user_usage, estimated_input_tokens)
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

                    async def _render_llm_response(response_generator: AsyncGenerator) -> Tuple[str, Optional[Dict[str, int]], List[str]]:
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
                                    except discord.errors.HTTPException:
                                        pass
                            elif response_type == "final":
                                _full_response = str(data or "")
                                _final_responses.append(_full_response)
                            elif response_type == "usage":
                                _usage_data = data
                        return _full_response, _usage_data, _final_responses

                    llm_provider = get_llm_provider(_cfg)
                    tools = _instance._plugin_manager.get_all_tools()
                    tool_functions = _instance._plugin_manager.get_all_tool_functions(message, _cfg)
                    used_tools_in_attempt = False
                    try:
                        logger.info(f"Attempting LLM call for message {message.id} with {len(tools)} tools.")
                        response_gen_with_tools = llm_provider.get_response_stream(
                            llm_messages, llm_images if is_multimodal_llm(_cfg) else None,
                            tools=tools, tool_functions=tool_functions
                        )
                        full_response, usage_data, final_response_stages = await _render_llm_response(response_gen_with_tools)
                        used_tools_in_attempt = bool(tools)
                    except Exception as e:
                        error_str = str(e).lower()
                        if 'malformed' in error_str or 'tool_code' in error_str or 'function_call' in error_str:
                            logger.warning(f"Malformed tool call for message {message.id}. Retrying without tools. Error: {e}")
                            response_gen_no_tools = llm_provider.get_response_stream(
                                llm_messages, llm_images if is_multimodal_llm(_cfg) else None, tools=[], tool_functions={}
                            )
                            full_response, usage_data, final_response_stages = await _render_llm_response(response_gen_no_tools)
                        else:
                            raise e

                    if used_tools_in_attempt and contains_dsml_tool_blocks(full_response):
                        logger.warning(f"Detected leaked DSML tool blocks in message {message.id}. Retrying without tools.")
                        response_gen_no_tools = llm_provider.get_response_stream(
                            llm_messages, llm_images if is_multimodal_llm(_cfg) else None, tools=[], tool_functions={}
                        )
                        full_response, usage_data, final_response_stages = await _render_llm_response(response_gen_no_tools)

                    error_reason = None
                    if not full_response or not full_response.strip():
                        error_reason = "LLM returned an empty response."
                    elif full_response.startswith("LLM_PROVIDER_ERROR:"):
                        error_reason = full_response

                    if error_reason:
                        logger.error(f"Response error for user '{message.author.name}': {error_reason}")
                        error_msg_template = _cfg.get("blocked_prompt_response", "Sorry, an error occurred: {reason}")
                        final_error_msg = error_msg_template.format(reason=error_reason)
                        _reset_channel_automation_state(message.channel.id)
                        if response_message:
                            await response_message.edit(content=final_error_msg)
                        else:
                            await message.reply(final_error_msg, mention_author=False)
                        return

                    cleaned_response = await process_knowledge_tags(message, full_response, _cfg)
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
                        "provider": str(_cfg.get("llm_provider", "")),
                        "model": str(_cfg.get("model_name", "")),
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
                    logger.info(f"Using official usage data: Input={input_tokens}, Output={output_tokens}")
                else:
                    input_tokens = shared_token_calc.get_token_count_for_messages(llm_messages, _cfg.get("llm_provider"), _cfg.get("model_name"))
                    output_tokens = shared_token_calc.get_token_count(full_response, _cfg.get("llm_provider"), _cfg.get("model_name"))
                    logger.warning(f"No usage data from provider. Using estimated tokens: Input={input_tokens}, Output={output_tokens}")

                role_id_for_log = role_config.get('id') if role_config else None
                role_name_for_log = role_config.get('title') if role_config else None
                await _instance._usage_tracker.record_usage(
                    provider=_cfg.get("llm_provider"), model=_cfg.get("model_name"),
                    input_tokens=input_tokens, output_tokens=output_tokens,
                    user_id=str(message.author.id), user_name=message.author.name,
                    user_display_name=message.author.display_name,
                    role_id=role_id_for_log, role_name=role_name_for_log,
                    channel_id=str(message.channel.id), channel_name=message.channel.name,
                    guild_id=str(message.guild.id) if message.guild else None,
                    guild_name=message.guild.name if message.guild else None
                )
                if role_config:
                    await _instance._usage_manager.update_post_request_usage(
                        user_id=message.author.id, input_tokens=input_tokens, output_tokens=output_tokens
                    )

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                error_msg = _cfg.get("blocked_prompt_response", "Sorry, an error occurred: {reason}").format(reason="Internal Server Error")
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
            logger.info(f"Started queue processor for channel {cid} for bot '{self.bot_id}'")

        @bot.event
        async def on_message(message):
            nonlocal config
            if message.author == bot.user:
                return

            config = _instance.config
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
                message.content, trigger_keywords,
                match_mode=trigger_match_mode, case_sensitive=trigger_case_sensitive,
            )
            normal_triggered = is_mentioned or is_reply_to_bot or has_trigger_keyword

            plugin_runtime_config = dict(config)
            plugin_runtime_config["_runtime_normal_triggered"] = normal_triggered
            plugin_result = await _instance._plugin_manager.process_message(message, plugin_runtime_config)
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
                logger.info(f"Repeat parrot triggered in channel {message.channel.id} for bot '{_instance.bot_id}'.")
                _reset_channel_automation_state(message.channel.id)
                return

            if not (normal_triggered or auto_interject_triggered or plugin_append_triggered):
                return

            if plugin_append_triggered and not (normal_triggered or auto_interject_triggered):
                logger.info(f"Continuing due to plugin append trigger for message {message.id}.")

            if auto_interject_triggered and not normal_triggered:
                logger.info(f"Auto interject triggered in channel {message.channel.id} for bot '{_instance.bot_id}'.")

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
            self.status = "running"
            await bot.start(discord_token)
        except asyncio.CancelledError:
            logger.info(f"Discord bot task cancelled for bot '{self.bot_id}'.")
            raise
        except ValueError as e:
            logger.critical(f"Configuration error for bot '{self.bot_id}': {e}")
            self.status = "error"
        except discord.errors.LoginFailure:
            logger.critical(f"FATAL: Login failed for bot '{self.bot_id}'. Token incorrect.")
            self.status = "error"
        except Exception as e:
            logger.error(f"Bot '{self.bot_id}' failed to start: {e}", exc_info=True)
            self.status = "error"
        finally:
            if not bot.is_closed():
                await bot.close()
            if bot_process_lock:
                _release_bot_process_lock(bot_process_lock)

    async def _run_qq(self):
        logger.info(f"QQ bot '{self.bot_id}' starting (platform stub).")
        self.status = "running"
        try:
            while True:
                await asyncio.sleep(60)
                if not self.is_running():
                    break
        except asyncio.CancelledError:
            logger.info(f"QQ bot '{self.bot_id}' stopped.")
            raise
        except Exception as e:
            logger.error(f"QQ bot '{self.bot_id}' error: {e}", exc_info=True)
            self.status = "error"


def _resolve_role_config(message, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    role_based = config.get("role_based_config", {})
    if not role_based:
        return None
    if not hasattr(message.author, 'roles'):
        return None
    for role in sorted(message.author.roles, key=lambda r: r.position, reverse=True):
        role_name = role.name
        if role_name in role_based:
            rc = role_based[role_name]
            if isinstance(rc, dict):
                return rc
            if hasattr(rc, 'dict'):
                return rc.dict()
            if hasattr(rc, 'model_dump'):
                return rc.model_dump()
            return None
    return None
