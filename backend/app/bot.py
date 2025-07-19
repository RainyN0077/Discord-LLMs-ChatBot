# backend/app/bot.py
import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, AsyncGenerator

import discord
from discord.ext import commands

import openai
import google.generativeai as genai
import anthropic

from .utils import TokenCalculator, download_image, split_message
from .usage_tracker import usage_tracker
from .core_logic.persona_manager import determine_bot_persona, build_system_prompt, get_highest_configured_role
from .core_logic.context_builder import build_context_history, format_user_message_for_llm
from .core_logic.quota_manager import check_and_reset_quota, check_pre_request_quota, update_post_request_usage
from ..plugins.manager import PluginManager

logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"
bot_instance = None
current_config = {}
token_calculator = TokenCalculator()

def load_bot_config():
    global current_config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding='utf-8') as f:
            current_config = json.load(f)
    return current_config

def collect_image_urls(msg):
    """收集消息中的所有图片URL"""
    return [attachment.url for attachment in msg.attachments 
            if attachment.content_type and attachment.content_type.startswith('image/')]

async def get_llm_response(config: Dict[str, Any], messages: List[Dict[str, str]], images: List[bytes] = None) -> AsyncGenerator[Tuple[str, str], None]:
    """统一的LLM调用接口，支持流式和非流式响应"""
    provider = config.get("llm_provider", "openai")
    model = config.get("model_name", "gpt-4o")
    api_key = config.get("api_key")
    base_url = config.get("base_url")
    stream = config.get("stream_response", True)
    custom_params = {param["name"]: param["value"] for param in config.get("custom_parameters", [])}
    
    try:
        if provider == "openai":
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            
            # 处理图片
            if images:
                last_message = messages[-1]
                content = [{"type": "text", "text": last_message["content"]}]
                for img_bytes in images:
                    import base64
                    img_b64 = base64.b64encode(img_bytes).decode('utf-8')
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                    })
                messages[-1] = {"role": last_message["role"], "content": content}
            
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=stream,
                **custom_params
            )
            
            if stream:
                full_response = ""
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield "partial", full_response
                yield "final", full_response
            else:
                content = response.choices[0].message.content
                yield "final", content
                
        elif provider == "google":
            genai.configure(api_key=api_key)
            model_instance = genai.GenerativeModel(model)
            
            # 构建内容
            prompt_parts = []
            for msg in messages:
                role_prefix = "Human: " if msg["role"] == "user" else "Assistant: "
                prompt_parts.append(f"{role_prefix}{msg['content']}")
            
            prompt = "\n\n".join(prompt_parts)
            
            # 处理图片
            generation_input = [prompt]
            if images:
                import PIL.Image
                import io
                for img_bytes in images:
                    img = PIL.Image.open(io.BytesIO(img_bytes))
                    generation_input.append(img)
            
            if stream:
                response = model_instance.generate_content(generation_input, stream=True, **custom_params)
                full_response = ""
                for chunk in response:
                    if chunk.text:
                        full_response += chunk.text
                        yield "partial", full_response
                yield "final", full_response
            else:
                response = model_instance.generate_content(generation_input, **custom_params)
                yield "final", response.text
                
        elif provider == "anthropic":
            client = anthropic.Anthropic(api_key=api_key)
            
            # 处理图片
            if images:
                last_message = messages[-1]
                content = [{"type": "text", "text": last_message["content"]}]
                for img_bytes in images:
                    import base64
                    img_b64 = base64.b64encode(img_bytes).decode('utf-8')
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": img_b64
                        }
                    })
                messages[-1] = {"role": last_message["role"], "content": content}
            
            if stream:
                with client.messages.stream(
                    model=model,
                    messages=messages,
                    max_tokens=4096,
                    **custom_params
                ) as stream:
                    full_response = ""
                    for text in stream.text_stream:
                        full_response += text
                        yield "partial", full_response
                yield "final", full_response
            else:
                response = client.messages.create(
                    model=model,
                    messages=messages,
                    max_tokens=4096,
                    **custom_params
                )
                yield "final", response.content[0].text
                
    except Exception as e:
        logger.error(f"LLM API error: {e}", exc_info=True)
        yield "final", f"Sorry, I encountered an error: {str(e)}"

async def run_bot(memory_cutoffs: Dict[int, datetime], user_usage_tracker: Dict[int, Dict[str, Any]]):
    global bot_instance
    
    config = load_bot_config()
    discord_token = config.get("discord_token")
    
    if not discord_token:
        logger.error("Discord token not found in configuration")
        return
    
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)
    bot_instance = bot
    
    plugin_manager = PluginManager(config.get("plugins", {}), get_llm_response)
    
    @bot.event
    async def on_ready():
        logger.info(f'{bot.user} has connected to Discord!')
    
    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return
        
        config = load_bot_config()
        
        # 检查插件触发
        plugin_result = await plugin_manager.process_message(message, config)
        if plugin_result is True:
            return
        
        injected_data = None
        if isinstance(plugin_result, tuple) and plugin_result[0] == 'append':
            injected_data = "\n".join(plugin_result[1])
        
        # 检查触发条件
        trigger_keywords = config.get("trigger_keywords", [])
        is_mentioned = bot.user in message.mentions
        is_reply_to_bot = (message.reference and 
                          isinstance(message.reference.resolved, discord.Message) and 
                          message.reference.resolved.author == bot.user)
        has_trigger_keyword = any(keyword.lower() in message.content.lower() for keyword in trigger_keywords)
        
        if not (is_mentioned or is_reply_to_bot or has_trigger_keyword):
            return
        
        # 收集图片 - 修改后的逻辑
        image_urls = collect_image_urls(message)
        
        # 如果是回复消息，也收集被回复消息的图片
        if message.reference and isinstance(message.reference.resolved, discord.Message):
            replied_msg = message.reference.resolved
            replied_images = collect_image_urls(replied_msg)
            image_urls.extend(replied_images)
            
            if replied_images:
                logger.info(f"Found {len(replied_images)} images in replied message from {replied_msg.author}")
        
        # 下载图片
        images = []
        for url in image_urls:
            img_data = await download_image(url)
            if img_data:
                images.append(img_data)
                logger.info(f"Successfully downloaded image from {url}")
        
        # 获取用户角色配置
        role_name, role_config = None, None
        if isinstance(message.author, discord.Member):
            role_name, role_config = get_highest_configured_role(message.author, config.get("role_based_config", {})) or (None, None)
        
        # 检查配额
        if role_config:
            user_usage = check_and_reset_quota(message.author.id, role_config, user_usage_tracker)
            
            cutoff_timestamp = memory_cutoffs.get(message.channel.id)
            history_messages, history_for_llm = await build_context_history(bot, config, message, cutoff_timestamp)
            
            specific_persona_prompt, situational_prompt, active_directives_log = determine_bot_persona(
                config, str(message.channel.id), str(message.guild.id) if message.guild else None, role_name, role_config
            )
            
            system_prompt = build_system_prompt(config, specific_persona_prompt, situational_prompt, message, history_messages, active_directives_log)
            final_formatted_content = format_user_message_for_llm(message, bot, config, role_config, injected_data)
            
            quota_error = await check_pre_request_quota(message, role_config, user_usage, token_calculator, config, system_prompt, history_for_llm, final_formatted_content)
            if quota_error:
                await message.reply(quota_error, mention_author=False)
                return
        
        # 构建消息历史
        cutoff_timestamp = memory_cutoffs.get(message.channel.id)
        history_messages, history_for_llm = await build_context_history(bot, config, message, cutoff_timestamp)
        
        # 确定机器人人设
        specific_persona_prompt, situational_prompt, active_directives_log = determine_bot_persona(
            config, str(message.channel.id), str(message.guild.id) if message.guild else None, role_name, role_config
        )
        
        system_prompt = build_system_prompt(config, specific_persona_prompt, situational_prompt, message, history_messages, active_directives_log)
        final_formatted_content = format_user_message_for_llm(message, bot, config, role_config, injected_data)
        
        # 构建完整的消息列表
        llm_messages = [{"role": "system", "content": system_prompt}] + history_for_llm + [{"role": "user", "content": final_formatted_content}]
        
        # 记录使用量
        provider = config.get("llm_provider")
        model = config.get("model_name")
        
        input_text = system_prompt + json.dumps(history_for_llm) + final_formatted_content
        input_tokens = token_calculator.get_token_count(input_text, provider, model)
        
        await usage_tracker.record_usage(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=0,  # 会在响应后更新
            user_id=str(message.author.id),
            user_name=message.author.name,
            user_display_name=message.author.display_name,
            role_id=str(role_config.get('id')) if role_config else None,
            role_name=role_name,
            channel_id=str(message.channel.id),
            channel_name=message.channel.name,
            guild_id=str(message.guild.id) if message.guild else None,
            guild_name=message.guild.name if message.guild else None
        )
        
        # 发送响应
        try:
            if config.get("stream_response", True):
                response_message = None
                full_response = ""
                
                async for response_type, content in get_llm_response(config, llm_messages, images):
                    if response_type == "partial":
                        content_chunks = split_message(content, 2000)
                        current_chunk = content_chunks[0] if content_chunks else ""
                        
                        if response_message is None:
                            if current_chunk.strip():
                                response_message = await message.reply(current_chunk, mention_author=False)
                        else:
                            if current_chunk != response_message.content:
                                try:
                                    await response_message.edit(content=current_chunk)
                                except discord.errors.HTTPException:
                                    pass
                    
                    elif response_type == "final":
                        full_response = content
                        
                        if response_message:
                            content_chunks = split_message(content, 2000)
                            await response_message.edit(content=content_chunks[0])
                            
                            for chunk in content_chunks[1:]:
                                await message.channel.send(chunk)
                        else:
                            content_chunks = split_message(content, 2000)
                            for chunk in content_chunks:
                                await message.channel.send(chunk)
            else:
                full_response = ""
                async for response_type, content in get_llm_response(config, llm_messages, images):
                    if response_type == "final":
                        full_response = content
                        break
                
                content_chunks = split_message(full_response, 2000)
                for chunk in content_chunks:
                    await message.reply(chunk, mention_author=False)
            
            # 更新输出token统计
            output_tokens = token_calculator.get_token_count(full_response, provider, model)
            await usage_tracker.record_usage(
                provider=provider,
                model=model,
                input_tokens=0,
                output_tokens=output_tokens,
                user_id=str(message.author.id),
                user_name=message.author.name,
                user_display_name=message.author.display_name,
                role_id=str(role_config.get('id')) if role_config else None,
                role_name=role_name,
                channel_id=str(message.channel.id),
                channel_name=message.channel.name,
                guild_id=str(message.guild.id) if message.guild else None,
                guild_name=message.guild.name if message.guild else None
            )
            
            # 更新用户配额
            if role_config:
                update_post_request_usage(message.author.id, user_usage_tracker, token_calculator, config, system_prompt, history_for_llm, final_formatted_content, full_response)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            error_msg = config.get("blocked_prompt_response", "Sorry, I encountered an error processing your request.").format(reason=str(e))
            await message.reply(error_msg, mention_author=False)
    
    try:
        await bot.start(discord_token)
    except Exception as e:
        logger.error(f"Bot failed to start: {e}", exc_info=True)
    finally:
        if not bot.is_closed():
            await bot.close()
