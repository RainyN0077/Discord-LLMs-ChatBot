# backend/app/bot.py
import asyncio
import json
import logging
import os
import re
import redis
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, AsyncGenerator

import discord
from discord.ext import commands

from .utils import TokenCalculator, download_image, split_message
from .usage_tracker import usage_tracker
from .core_logic.persona_manager import determine_bot_persona, build_system_prompt, get_highest_configured_role
from .core_logic.context_builder import build_context_history, format_user_message_for_llm
from .core_logic.usage_manager import UsageManager
from .core_logic.knowledge_manager import knowledge_manager # Import the singleton instance
from .llm_providers.factory import get_llm_provider
from plugins.manager import PluginManager

logger = logging.getLogger(__name__)

# --- [增强] 更健壮的Redis连接逻辑 ---
redis_client = None
try:
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    
    # 尝试连接 Redis
    _redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    _redis_client.ping()
    redis_client = _redis_client
    logger.info(f"Successfully connected to Redis at {REDIS_HOST}:{REDIS_PORT}")

except redis.exceptions.ConnectionError as e:
    logger.error(f"Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}. Error: {e}")
    # 检查环境变量，决定是“快速失败”还是“静默退化”
    if os.getenv('FAIL_ON_REDIS_ERROR', 'false').lower() == 'true':
        logger.critical("FAIL_ON_REDIS_ERROR is true. Terminating application.")
        # 抛出一个明确的异常，这将阻止 bot.start() 的执行
        raise ConnectionAbortedError("Failed to connect to Redis. Aborting.")
    else:
        # 创建一个模拟客户端以允许在没有 Redis 的情况下进行开发
        class MockRedis:
            def set(self, *args, **kwargs): return True
        redis_client = MockRedis()
        logger.warning("FAIL_ON_REDIS_ERROR is not set to true. Using a mock Redis client. CONCURRENCY PROTECTION IS DISABLED.")


from pathlib import Path

# --- [核心修改] 和 main.py 保持一致, 指向新的 data 目录 ---
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
    收集消息中的所有视觉内容URL，包括附件、嵌入图片、贴纸和自定义表情。
    """
    urls = []
    # 1. 从附件中收集 (适用于用户直接上传的文件)
    for attachment in msg.attachments:
        if attachment.content_type and attachment.content_type.startswith('image/'):
            urls.append(attachment.url)
    
    # 2. 从嵌入内容中收集 (适用于粘贴的图片/GIF链接, 或某些特殊情况)
    for embed in msg.embeds:
        # 检查 embed 的主图片
        if embed.image and embed.image.url:
            urls.append(embed.image.url)
        # 检查 embed 的缩略图 (有些链接只显示缩略图)
        if embed.thumbnail and embed.thumbnail.url:
            urls.append(embed.thumbnail.url)
    
    # 3. 从贴纸中收集
    for sticker in msg.stickers:
        urls.append(sticker.url)

    # 4. 从自定义表情中收集
    # 使用正则表达式从消息内容中查找表情，并使用 discord.py 工具类进行解析
    emoji_matches = re.finditer(r'<a?:\w+:\d+>', msg.content)
    for match in emoji_matches:
        try:
            # PartialEmoji.from_str 是从 <a:name:id> 格式安全解析表情的正确方法
            emoji = discord.PartialEmoji.from_str(match.group(0))
            if emoji.url:
                urls.append(str(emoji.url))
        except Exception as e:
            logger.warning(f"Could not parse emoji from string '{match.group(0)}': {e}")
            
    # 使用 dict.fromkeys 来去重，同时保持原始顺序
    return list(dict.fromkeys(urls))



async def run_bot(memory_cutoffs: Dict[int, datetime]):
    global bot_instance
    
    config = load_bot_config()
    discord_token = config.get("discord_token")
    
    if not discord_token or not isinstance(discord_token, str) or len(discord_token) < 50:
        logger.critical("FATAL: Discord token is missing, invalid, or too short in config.json. Bot cannot start.")
        # 在异步上下文中，抛出异常是终止启动的明确方式
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
        logger.info(f"Plugin triggered LLM call with {len(messages)} messages.")
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

        logger.info(f"LLM response for plugin: {full_response[:100]}...")
        return full_response

    plugin_manager = PluginManager(config.get("plugins", {}), get_llm_response)
    knowledge_manager.init_db() # Ensure DB is ready
    usage_manager = UsageManager(token_calculator)

    @bot.event
    async def on_ready():
        logger.info(f'{bot.user} has connected to Discord!')
    
    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return

        # --- [BUG修复] 将配置加载移到函数顶部 ---
        # 确保在任何需要配置的操作之前加载它
        config = load_bot_config()
        
        # 插件处理
        plugin_result = await plugin_manager.process_message(message, config)
        if plugin_result is True:
            return  # 插件已经处理了消息并希望停止后续逻辑
        
        injected_data = None
        if isinstance(plugin_result, tuple) and plugin_result[0] == 'append':
            injected_data = "\n".join(plugin_result[1])

        # --- [逻辑修正] 先检查触发条件，再获取锁 ---
        trigger_keywords = config.get("trigger_keywords", [])
        is_mentioned = bot.user in message.mentions
        is_reply_to_bot = (message.reference and
                           isinstance(message.reference.resolved, discord.Message) and
                           message.reference.resolved.author == bot.user)
        has_trigger_keyword = any(keyword.lower() in message.content.lower() for keyword in trigger_keywords)

        # 如果不是触发消息，则直接忽略
        if not (is_mentioned or is_reply_to_bot or has_trigger_keyword):
            return

        # --- 分布式锁逻辑 ---
        # 只有在确认消息是发给bot时，才进行加锁操作
        lock_key = f"discord:message_lock:{message.id}"
        is_lock_acquired = redis_client.set(lock_key, "processing", nx=True, ex=60)
        
        if not is_lock_acquired:
            logger.info(f"Triggering message {message.id} is already being processed. Skipping.")
            return
        
        logger.info(f"Acquired lock for triggering message {message.id}. Processing...")
        
        # 图片收集
        image_urls = collect_image_urls(message)
        if message.reference and isinstance(message.reference.resolved, discord.Message):
            replied_msg = message.reference.resolved
            replied_images = collect_image_urls(replied_msg)
            image_urls.extend(replied_images)
            if replied_images:
                logger.info(f"Found {len(replied_images)} images in replied message from {replied_msg.author}")
        images = []
        unique_image_urls = list(dict.fromkeys(image_urls))
        for url in unique_image_urls:
            img_data = await download_image(url)
            if img_data:
                images.append(img_data)
                logger.info(f"Successfully downloaded image from {url}")
        
        # 核心逻辑：上下文、人设、配额
        role_name, role_config = (None, None); 
        if isinstance(message.author, discord.Member):
            role_name, role_config = get_highest_configured_role(message.author, config.get("role_based_config", {})) or (None, None)
        
        cutoff_timestamp = memory_cutoffs.get(message.channel.id)
        history_messages, history_for_llm = await build_context_history(bot, config, message, cutoff_timestamp)
        specific_persona_prompt, situational_prompt, active_directives_log = determine_bot_persona(config, str(message.channel.id), str(message.guild.id) if message.guild else None, role_name, role_config)
        system_prompt = build_system_prompt(config, specific_persona_prompt, situational_prompt, message, history_messages, active_directives_log)
        final_formatted_content = format_user_message_for_llm(message, bot, config, role_config, injected_data)
        
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
                await message.reply(quota_error, mention_author=False)
                return

        llm_messages = [{"role": "system", "content": system_prompt}] + history_for_llm + [{"role": "user", "content": final_formatted_content}]
        provider, model = config.get("llm_provider"), config.get("model_name")
        # Placeholder for usage data. Will be updated by the generator if available.
        usage_data = None
        
        try:
            async with message.channel.typing():
                full_response = ""
                response_message = None
                llm_provider = get_llm_provider(config)
                tools = plugin_manager.get_all_tools()
                tool_functions = plugin_manager.get_all_tool_functions()

                response_generator = llm_provider.get_response_stream(
                    llm_messages, images, tools=tools, tool_functions=tool_functions
                )

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
                        full_response = data
                    elif response_type == "usage":
                        usage_data = data
                
                error_reason = None
                if not full_response or not full_response.strip():
                    error_reason = "LLM returned an empty response."
                elif full_response.startswith("LLM_PROVIDER_ERROR:"):
                    error_reason = full_response
                
                if error_reason:
                    logger.error(f"Response error for user '{message.author.name}': {error_reason}")
                    error_msg_template = config.get("blocked_prompt_response", "Sorry, an error occurred: {reason}")
                    final_error_msg = error_msg_template.format(reason=error_reason)
                    if response_message:
                        await response_message.edit(content=final_error_msg)
                    else:
                        await message.reply(final_error_msg, mention_author=False)
                    return

                if response_message:
                    final_chunks = split_message(full_response, 2000)
                    await response_message.edit(content=final_chunks[0] if final_chunks else "")
                    for chunk in final_chunks[1:]:
                        await message.channel.send(chunk)
                else:
                    final_chunks = split_message(full_response, 2000)
                    for i, chunk in enumerate(final_chunks):
                        if i == 0 and chunk.strip():
                            await message.reply(chunk, mention_author=False)
                        elif i > 0:
                            await message.channel.send(chunk)

            # --- [NEW] Token Calculation Logic ---
            if usage_data:
                input_tokens = usage_data.get("input_tokens", 0)
                output_tokens = usage_data.get("output_tokens", 0)
                logger.info(f"Using official usage data: Input={input_tokens}, Output={output_tokens}")
            else:
                # Fallback to estimation
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
            await message.reply(error_msg, mention_author=False)
    
    try:
        await bot.start(discord_token)
    except ValueError as e: # 捕获我们自己抛出的异常
        logger.critical(f"Terminating due to configuration error: {e}")
    except discord.errors.LoginFailure:
        logger.critical("FATAL: Login failed. The provided Discord token is incorrect. Please check your config.json.")
    except Exception as e:
        logger.error(f"Bot failed to start: {e}", exc_info=True)
    finally:
        if not bot.is_closed():
            await bot.close()
