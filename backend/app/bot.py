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
from typing import Any, Dict, List, Optional, Tuple, AsyncGenerator

import discord
from discord.ext import commands

from .utils import TokenCalculator, download_image, split_message, transform_memories_for_prompt, matches_trigger_keywords
from .usage_tracker import usage_tracker
from .core_logic.persona_manager import determine_bot_persona, build_system_prompt, get_highest_configured_role
from .core_logic.context_builder import build_context_history, format_user_message_for_llm
from .core_logic.usage_manager import UsageManager
from .core_logic.knowledge_manager import knowledge_manager # Import the singleton instance
from .debug_capture_store import add_capture
from .llm_providers.factory import get_llm_provider
from plugins.manager import PluginManager

logger = logging.getLogger(__name__)

INSTANCE_ID = os.getenv("BOT_INSTANCE_ID") or f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"

# --- [澧炲己] 鏇村仴澹殑Redis杩炴帴閫昏緫 ---
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
    # 妫€鏌ョ幆澧冨彉閲忥紝鍐冲畾鏄€滃揩閫熷け璐モ€濊繕鏄€滈潤榛橀€€鍖栤€?
    if os.getenv('FAIL_ON_REDIS_ERROR', 'false').lower() == 'true':
        logger.critical(f"[instance={INSTANCE_ID}] FAIL_ON_REDIS_ERROR is true. Terminating application.")
        # 鎶涘嚭涓€涓槑纭殑寮傚父锛岃繖灏嗛樆姝?bot.start() 鐨勬墽琛?
        raise ConnectionAbortedError("Failed to connect to Redis. Aborting.")
    else:
        # 鍒涘缓涓€涓ā鎷熷鎴风浠ュ厑璁稿湪娌℃湁 Redis 鐨勬儏鍐典笅杩涜寮€鍙?
        class MockRedis:
            def set(self, *args, **kwargs): return True
        redis_client = MockRedis()
        logger.warning(f"[instance={INSTANCE_ID}] FAIL_ON_REDIS_ERROR is not set to true. Using a mock Redis client. CONCURRENCY PROTECTION IS DISABLED.")


from pathlib import Path

# --- [鏍稿績淇敼] 鍜?main.py 淇濇寔涓€鑷? 鎸囧悜鏂扮殑 data 鐩綍 ---
DATA_DIR = Path.cwd() / "data"
CONFIG_FILE = DATA_DIR / "config.json"
bot_instance = None
current_config = {}
token_calculator = TokenCalculator()

def load_bot_config():
    global current_config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding='utf-8') as f:
            current_config = json.load(f)
    return current_config

def collect_image_urls(msg: discord.Message) -> List[str]:
    """
    鏀堕泦娑堟伅涓殑鎵€鏈夎瑙夊唴瀹筓RL锛屽寘鎷檮浠躲€佸祵鍏ュ浘鐗囥€佽创绾稿拰鑷畾涔夎〃鎯呫€?
    """
    urls = []
    # 1. 浠庨檮浠朵腑鏀堕泦 (閫傜敤浜庣敤鎴风洿鎺ヤ笂浼犵殑鏂囦欢)
    for attachment in msg.attachments:
        if attachment.content_type and attachment.content_type.startswith('image/'):
            urls.append(attachment.url)
    
    # 2. 浠庡祵鍏ュ唴瀹逛腑鏀堕泦 (閫傜敤浜庣矘璐寸殑鍥剧墖/GIF閾炬帴, 鎴栨煇浜涚壒娈婃儏鍐?
    for embed in msg.embeds:
        # 妫€鏌?embed 鐨勪富鍥剧墖
        if embed.image and embed.image.url:
            urls.append(embed.image.url)
        # 妫€鏌?embed 鐨勭缉鐣ュ浘 (鏈変簺閾炬帴鍙樉绀虹缉鐣ュ浘)
        if embed.thumbnail and embed.thumbnail.url:
            urls.append(embed.thumbnail.url)
    
    # 3. 浠庤创绾镐腑鏀堕泦
    for sticker in msg.stickers:
        urls.append(sticker.url)

    # 4. 浠庤嚜瀹氫箟琛ㄦ儏涓敹闆?
    # 浣跨敤姝ｅ垯琛ㄨ揪寮忎粠娑堟伅鍐呭涓煡鎵捐〃鎯咃紝骞朵娇鐢?discord.py 宸ュ叿绫昏繘琛岃В鏋?
    emoji_matches = re.finditer(r'<a?:\w+:\d+>', msg.content)
    for match in emoji_matches:
        try:
            # PartialEmoji.from_str 鏄粠 <a:name:id> 鏍煎紡瀹夊叏瑙ｆ瀽琛ㄦ儏鐨勬纭柟娉?
            emoji = discord.PartialEmoji.from_str(match.group(0))
            if emoji.url:
                urls.append(str(emoji.url))
        except Exception as e:
            logger.warning(f"Could not parse emoji from string '{match.group(0)}': {e}")
            
    # 浣跨敤 dict.fromkeys 鏉ュ幓閲嶏紝鍚屾椂淇濇寔鍘熷椤哄簭
    return list(dict.fromkeys(urls))



def process_memory_tags(message: discord.Message, text: str, bot_config: Dict[str, Any]) -> str:
    """
    Finds <memory> tags in the text, saves the content with metadata to long-term memory,
    and returns the text with the tags removed.
    """
    if not text or '<memory>' not in text:
        return text

    # Use a non-greedy regex to find all memory tags
    # re.DOTALL allows '.' to match newlines within the tag content
    memories_to_add = re.findall(r'<memory>(.*?)</memory>', text, re.DOTALL)
    
    for memory_content in memories_to_add:
        stripped_content = memory_content.strip()
        if stripped_content:
            # Use the message's creation time for accurate timestamping
            timestamp = message.created_at.astimezone(timezone.utc).isoformat()
            user_id = str(message.author.id)
            user_name = message.author.name
            
            try:
                ingest_result = knowledge_manager.ingest_memory_candidate(
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

    # Remove the tags from the text for the final response
    cleaned_text = re.sub(r'<memory>.*?</memory>', '', text, flags=re.DOTALL).strip()
    return cleaned_text


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
    cleaned = re.sub(
        r"<\s*\|\s*DSML\s*\|\s*function_calls\s*>.*?<\s*/\s*\|\s*DSML\s*\|\s*function_calls\s*>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return cleaned.strip()


def contains_dsml_tool_blocks(text: str) -> bool:
    if not text:
        return False
    return bool(
        re.search(
            r"<\s*\|\s*DSML\s*\|\s*(function_calls|invoke|parameter)\s*>",
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
        # 鍦ㄥ紓姝ヤ笂涓嬫枃涓紝鎶涘嚭寮傚父鏄粓姝㈠惎鍔ㄧ殑鏄庣‘鏂瑰紡
        raise ValueError("Invalid Discord token provided.")
    
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
    knowledge_manager.init_db() # Ensure DB is ready
    usage_manager = UsageManager(token_calculator)
    auto_message_counts: Dict[int, int] = {}
    repeat_streaks: Dict[int, Dict[str, Any]] = {}

    def _reset_channel_automation_state(channel_id: int) -> None:
        auto_message_counts[channel_id] = 0
        repeat_streaks.pop(channel_id, None)

    def _track_auto_interject(message: discord.Message, bot_config: Dict[str, Any]) -> bool:
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

    def _normalize_repeat_content(message: discord.Message, bot_config: Dict[str, Any]) -> Optional[Tuple[str, str]]:
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

    def _track_repeat_parrot(message: discord.Message, bot_config: Dict[str, Any]) -> Optional[str]:
        if not bot_config.get("repeat_parrot_enabled", False):
            return None

        normalized_content = _normalize_repeat_content(message, bot_config)
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

    @bot.event
    async def on_ready():
        logger.info(f"[instance={INSTANCE_ID}] {bot.user} has connected to Discord!")
    
    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return

        # --- [BUG淇] 灏嗛厤缃姞杞界Щ鍒板嚱鏁伴《閮?---
        # 纭繚鍦ㄤ换浣曢渶瑕侀厤缃殑鎿嶄綔涔嬪墠鍔犺浇瀹?
        config = load_bot_config()
        auto_interject_triggered = _track_auto_interject(message, config)
        repeat_parrot_content = _track_repeat_parrot(message, config)
        
                # Trigger detection
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

        # Plugin processing (receives runtime trigger state)
        plugin_runtime_config = dict(config)
        plugin_runtime_config["_runtime_normal_triggered"] = normal_triggered
        plugin_result = await plugin_manager.process_message(message, plugin_runtime_config)
        if plugin_result is True:
            return

        injected_data = None
        plugin_append_triggered = False
        if isinstance(plugin_result, tuple) and plugin_result[0] == 'append':
            injected_data = "\n".join(plugin_result[1])
            plugin_append_triggered = bool(plugin_result[1])

        if not normal_triggered and repeat_parrot_content:
            await message.channel.send(repeat_parrot_content)
            logger.info(f"[instance={INSTANCE_ID}] Repeat parrot triggered in channel {message.channel.id} after repeated content.")
            _reset_channel_automation_state(message.channel.id)
            return

        # 濡傛灉涓嶆槸瑙﹀彂娑堟伅锛屽垯鐩存帴蹇界暐
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

        # --- 鍒嗗竷寮忛攣閫昏緫 ---
        # 鍙湁鍦ㄧ‘璁ゆ秷鎭槸鍙戠粰bot鏃讹紝鎵嶈繘琛屽姞閿佹搷浣?
        lock_key = f"discord:message_lock:{message.id}"
        is_lock_acquired = redis_client.set(lock_key, "processing", nx=True, ex=60)
        
        if not is_lock_acquired:
            logger.info(f"[instance={INSTANCE_ID}] Triggering message {message.id} is already being processed. Skipping.")
            return
        
        logger.info(f"[instance={INSTANCE_ID}] Acquired lock for triggering message {message.id}. Processing...")
        
        # 鍥剧墖鏀堕泦
        image_urls = collect_image_urls(message)
        if message.reference and isinstance(message.reference.resolved, discord.Message):
            replied_msg = message.reference.resolved
            replied_images = collect_image_urls(replied_msg)
            image_urls.extend(replied_images)
            if replied_images:
                logger.info(f"[instance={INSTANCE_ID}] Found {len(replied_images)} images in replied message from {replied_msg.author}")
        images = []
        unique_image_urls = list(dict.fromkeys(image_urls))
        for url in unique_image_urls:
            img_data = await download_image(url)
            if img_data:
                images.append(img_data)
                logger.info(f"[instance={INSTANCE_ID}] Successfully downloaded image from {url}")
        
        # 鏍稿績閫昏緫锛氫笂涓嬫枃銆佷汉璁俱€侀厤棰?
        role_name, role_config = (None, None); 
        if isinstance(message.author, discord.Member):
            role_name, role_config = get_highest_configured_role(message.author, config.get("role_based_config", {})) or (None, None)
        
        cutoff_timestamp = memory_cutoffs.get(message.channel.id)
        history_messages, history_for_llm = await build_context_history(bot, config, message, cutoff_timestamp)
        specific_persona_prompt, situational_prompt, active_directives_log = determine_bot_persona(config, str(message.channel.id), str(message.guild.id) if message.guild else None, role_name, role_config)
        system_prompt = await build_system_prompt(bot, config, specific_persona_prompt, situational_prompt, message, active_directives_log)
        final_formatted_content = format_user_message_for_llm(message, bot, config, role_config, injected_data)
        
        # --- [NEW] Memory Retrieval and Injection ---
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
        relevant_memories = knowledge_manager.get_relevant_memories(
            query_text=message.content or "",
            top_k=recall_top_k,
            char_limit=recall_char_limit,
            max_age_days=recall_max_age_days,
        )
        if relevant_memories:
            # We don't know the Discord user's timezone, so we transform using UTC as a neutral default.
            # The important part is that manually added memories with specific times are preserved correctly.
            transformed_memories = transform_memories_for_prompt(relevant_memories, target_timezone_str='UTC')
            
            # Combine memories into a single block for the system prompt
            memory_knowledge = "\n".join(transformed_memories)
            
            # Prepend to the system prompt inside a <knowledge> tag
            system_prompt = f"<knowledge>\n<long_term_memory>\n{memory_knowledge}\n</long_term_memory>\n</knowledge>\n\n{system_prompt}"
            logger.info(
                "[instance=%s] Injected %s relevant memories into the system prompt (top_k=%s, char_limit=%s).",
                INSTANCE_ID,
                len(transformed_memories),
                recall_top_k,
                recall_char_limit,
            )
        # --- End of Memory Injection ---

        if role_config:
            user_usage = await usage_manager.check_quota_and_get_usage(message.author.id, role_config)
            
            # Estimate input tokens for pre-check
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
        provider, model = config.get("llm_provider"), config.get("model_name")
        # Placeholder for usage data. Will be updated by the generator if available.
        usage_data = None
        
        try:
            full_response = ""
            usage_data = None
            
            async with message.channel.typing():
                response_message = None

                # Helper function to render the response stream to avoid code duplication
                async def _render_llm_response(response_generator: AsyncGenerator[Tuple[str, Any], None]) -> Tuple[str, Optional[Dict[str, int]]]:
                    nonlocal response_message
                    _full_response = ""
                    _usage_data = None
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
                            _full_response = data
                        elif response_type == "usage":
                            _usage_data = data
                    return _full_response, _usage_data

                llm_provider = get_llm_provider(config)
                tools = plugin_manager.get_all_tools()
                tool_functions = plugin_manager.get_all_tool_functions(message, config)
                used_tools_in_attempt = False
                try:
                    # First attempt: with tools
                    logger.info(f"[instance={INSTANCE_ID}] Attempting LLM call for message {message.id} with {len(tools)} tools enabled.")
                    response_gen_with_tools = llm_provider.get_response_stream(
                        llm_messages, images, tools=tools, tool_functions=tool_functions
                    )
                    full_response, usage_data = await _render_llm_response(response_gen_with_tools)
                    used_tools_in_attempt = bool(tools)
                except Exception as e:
                    error_str = str(e).lower()
                    # Check for keywords indicating a malformed tool call
                    if 'malformed' in error_str or 'tool_code' in error_str or 'function_call' in error_str:
                        logger.warning(f"Malformed tool call from LLM for message {message.id}. Retrying without tools. Original error: {e}")
                        # Second attempt: without tools
                        response_gen_no_tools = llm_provider.get_response_stream(
                            llm_messages, images, tools=[], tool_functions={}
                        )
                        full_response, usage_data = await _render_llm_response(response_gen_no_tools)
                    else:
                        # It's a different error, re-raise it to be caught by the main handler
                        raise e

                if used_tools_in_attempt and contains_dsml_tool_blocks(full_response):
                    logger.warning(
                        f"[instance={INSTANCE_ID}] Detected leaked DSML tool blocks in message {message.id}. Retrying without tools."
                    )
                    response_gen_no_tools = llm_provider.get_response_stream(
                        llm_messages, images, tools=[], tool_functions={}
                    )
                    full_response, usage_data = await _render_llm_response(response_gen_no_tools)

                # --- Response Validation and Finalization ---
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

                cleaned_response = process_memory_tags(message, full_response, config)
                cleaned_response = strip_dsml_tool_blocks(cleaned_response)
                cleaned_response = strip_thinking_sections(cleaned_response)

                add_capture({
                    "trigger_message_id": str(message.id),
                    "channel_id": str(message.channel.id),
                    "guild_id": str(message.guild.id) if message.guild else None,
                    "user_id": str(message.author.id),
                    "user_name": message.author.name,
                    "user_display_name": getattr(message.author, "display_name", message.author.name),
                    "trigger_sources": trigger_sources,
                    "raw_user_message": str(message.content or ""),
                    "formatted_user_request": final_formatted_content,
                    "system_prompt": system_prompt,
                    "history_for_llm": history_for_llm,
                    "llm_messages": llm_messages,
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

            # --- Token Calculation and Usage Recording ---
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
            # [SECURITY] Do not leak detailed exception info to the user.
            # The {reason} placeholder is now only populated for known, safe error types.
            error_msg = config.get("blocked_prompt_response", "Sorry, an error occurred: {reason}").format(reason="Internal Server Error")
            _reset_channel_automation_state(message.channel.id)
            await message.reply(error_msg, mention_author=False)
    
    try:
        await bot.start(discord_token)
    except ValueError as e: # 鎹曡幏鎴戜滑鑷繁鎶涘嚭鐨勫紓甯?
        logger.critical(f"[instance={INSTANCE_ID}] Terminating due to configuration error: {e}")
    except discord.errors.LoginFailure:
        logger.critical(f"[instance={INSTANCE_ID}] FATAL: Login failed. The provided Discord token is incorrect. Please check your config.json.")
    except Exception as e:
        logger.error(f"[instance={INSTANCE_ID}] Bot failed to start: {e}", exc_info=True)
    finally:
        if not bot.is_closed():
            await bot.close()


