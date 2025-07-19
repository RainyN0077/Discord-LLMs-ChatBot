# backend/app/bot.py
import asyncio
import json
import discord
import os
from io import BytesIO
from typing import AsyncGenerator, Dict, List, Any
from datetime import datetime, timezone, timedelta
import logging
from PIL import Image
from .usage_tracker import usage_tracker

import openai
import google.generativeai as genai
import anthropic

from plugins.manager import PluginManager
from .utils import setup_logging, TokenCalculator, split_message, download_image
from .core_logic.persona_manager import get_highest_configured_role, determine_bot_persona, build_system_prompt
from .core_logic.context_builder import build_context_history, format_user_message_for_llm
from .core_logic.quota_manager import check_and_reset_quota, check_pre_request_quota, update_post_request_usage

logger = logging.getLogger(__name__)
CONFIG_FILE = "config.json"

def process_custom_params(params_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    processed_params = {}
    if not isinstance(params_list, list): return {}
    for param in params_list:
        name, param_type, value = param.get('name'), param.get('type'), param.get('value')
        if not name or value is None: continue
        try:
            if param_type == 'number': processed_params[name] = float(value)
            elif param_type == 'boolean': processed_params[name] = str(value).lower() in ['true', '1']
            elif param_type == 'json':
                if isinstance(value, str) and value.strip(): processed_params[name] = json.loads(value)
                elif not isinstance(value, str): processed_params[name] = value
            else: processed_params[name] = str(value)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Could not process custom parameter '{name}'. Invalid value '{value}' for type '{param_type}': {e}")
    return processed_params

async def get_llm_response(config: dict, messages: List[Dict[str, Any]]) -> AsyncGenerator[tuple[str, str], None]:
    provider, api_key, base_url, model, stream = config.get("llm_provider", "openai"), config.get("api_key"), config.get("base_url"), config.get("model_name"), config.get("stream_response", True)
    extra_params = process_custom_params(config.get('custom_parameters', []))
    system_prompt = next((m['content'] for m in messages if m['role'] == 'system'), "")
    user_messages = [m for m in messages if m['role'] != 'system']
    
    # 计算输入tokens
    input_text = json.dumps(messages)
    token_calc = TokenCalculator()
    input_tokens = token_calc.get_token_count(input_text, provider, model)

    async def response_generator():
        if provider == "openai":
            client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url if base_url else None)
            response_stream = await client.chat.completions.create(model=model, messages=messages, stream=stream, **extra_params)
            if stream:
                async for chunk in response_stream:
                    if content := chunk.choices[0].delta.content: yield content
            else: yield response_stream.choices[0].message.content or ""
        elif provider == "google":
            genai.configure(api_key=api_key)
            generation_config = {k: v for k, v in extra_params.items() if k in {'temperature', 'top_p', 'top_k', 'candidate_count', 'max_output_tokens', 'stop_sequences'}}
            model_instance = genai.GenerativeModel(model, system_instruction=system_prompt, generation_config=generation_config)
            google_formatted_messages = []
            for msg in user_messages:
                role = 'model' if msg['role'] == 'assistant' else 'user'
                content_parts = []
                if isinstance(msg['content'], list):
                    for part in msg['content']:
                        if part['type'] == 'text': content_parts.append(part['text'])
                        elif part['type'] == 'image_url' and 'url' in part.get('image_url', {}):
                            if image_data := await download_image(part['image_url']['url']):
                                img = Image.open(BytesIO(image_data)); content_parts.append(img)
                elif isinstance(msg['content'], str): content_parts.append(msg['content'])
                if content_parts: google_formatted_messages.append({'role': role, 'parts': content_parts})
            
            if stream:
                response_stream = await model_instance.generate_content_async(google_formatted_messages, stream=True)
                async for chunk in response_stream:
                    if chunk.parts: 
                        yield chunk.text
                    else:
                        logger.warning(f"Google Gemini stream returned an empty chunk. Prompt might be blocked.")
            else:
                response = await model_instance.generate_content_async(google_formatted_messages)
                
                if not response.candidates:
                    block_reason = "Unknown"
                    try:
                        block_reason = response.prompt_feedback.block_reason.name
                    except Exception:
                        pass
                    logger.warning(f"Google Gemini API returned no candidates. Prompt likely blocked. Reason: {block_reason}. Full feedback: {response.prompt_feedback}")
                    
                    response_template = config.get("blocked_prompt_response", "*(Response was blocked by content filter. Reason: {reason})*")
                    yield response_template.format(reason=block_reason)
                else:
                    yield response.text

        elif provider == "anthropic":
            client = anthropic.AsyncAnthropic(api_key=api_key)
            if stream:
                async with client.messages.stream(max_tokens=4096, model=model, system=system_prompt, messages=user_messages, **extra_params) as s:
                    async for text in s.text_stream: yield text
            else:
                response = await client.messages.create(max_tokens=4096, model=model, system=system_prompt, messages=user_messages, **extra_params)
                yield response.content[0].text
        else: yield f"Error: Unsupported provider '{provider}'"

    full_response = ""
    async for chunk in response_generator():
        full_response += chunk
        if stream and chunk: yield "partial", full_response
    
    # 计算输出tokens并记录
    output_tokens = token_calc.get_token_count(full_response, provider, model)
    await usage_tracker.record_usage(provider, model, input_tokens, output_tokens)
    
    yield "full", full_response

    provider, api_key, base_url, model, stream = config.get("llm_provider", "openai"), config.get("api_key"), config.get("base_url"), config.get("model_name"), config.get("stream_response", True)
    extra_params = process_custom_params(config.get('custom_parameters', []))
    system_prompt = next((m['content'] for m in messages if m['role'] == 'system'), "")
    user_messages = [m for m in messages if m['role'] != 'system']

    async def response_generator():
        if provider == "openai":
            client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url if base_url else None)
            response_stream = await client.chat.completions.create(model=model, messages=messages, stream=stream, **extra_params)
            if stream:
                async for chunk in response_stream:
                    if content := chunk.choices[0].delta.content: yield content
            else: yield response_stream.choices[0].message.content or ""
        elif provider == "google":
            genai.configure(api_key=api_key)
            generation_config = {k: v for k, v in extra_params.items() if k in {'temperature', 'top_p', 'top_k', 'candidate_count', 'max_output_tokens', 'stop_sequences'}}
            model_instance = genai.GenerativeModel(model, system_instruction=system_prompt, generation_config=generation_config)
            google_formatted_messages = []
            for msg in user_messages:
                role = 'model' if msg['role'] == 'assistant' else 'user'
                content_parts = []
                if isinstance(msg['content'], list):
                    for part in msg['content']:
                        if part['type'] == 'text': content_parts.append(part['text'])
                        elif part['type'] == 'image_url' and 'url' in part.get('image_url', {}):
                            if image_data := await download_image(part['image_url']['url']):
                                img = Image.open(BytesIO(image_data)); content_parts.append(img)
                elif isinstance(msg['content'], str): content_parts.append(msg['content'])
                if content_parts: google_formatted_messages.append({'role': role, 'parts': content_parts})
            
            if stream:
                response_stream = await model_instance.generate_content_async(google_formatted_messages, stream=True)
                async for chunk in response_stream:
                    if chunk.parts: 
                        yield chunk.text
                    else:
                        logger.warning(f"Google Gemini stream returned an empty chunk. Prompt might be blocked.")
            else:
                response = await model_instance.generate_content_async(google_formatted_messages)
                
                if not response.candidates:
                    block_reason = "Unknown"
                    try:
                        block_reason = response.prompt_feedback.block_reason.name
                    except Exception:
                        pass
                    logger.warning(f"Google Gemini API returned no candidates. Prompt likely blocked. Reason: {block_reason}. Full feedback: {response.prompt_feedback}")
                    
                    response_template = config.get("blocked_prompt_response", "*(Response was blocked by content filter. Reason: {reason})*")
                    yield response_template.format(reason=block_reason)
                else:
                    yield response.text

        elif provider == "anthropic":
            client = anthropic.AsyncAnthropic(api_key=api_key)
            if stream:
                async with client.messages.stream(max_tokens=4096, model=model, system=system_prompt, messages=user_messages, **extra_params) as s:
                    async for text in s.text_stream: yield text
            else:
                response = await client.messages.create(max_tokens=4096, model=model, system=system_prompt, messages=user_messages, **extra_params)
                yield response.content[0].text
        else: yield f"Error: Unsupported provider '{provider}'"

    full_response = ""
    async for chunk in response_generator():
        full_response += chunk
        if stream and chunk: yield "partial", full_response
    yield "full", full_response

async def handle_quota_command(message: discord.Message, bot_config: Dict[str, Any], user_usage_tracker):
    if not isinstance(message.author, discord.Member):
        await message.reply("Quota information is only available in servers.", mention_author=False); return
    role_info = get_highest_configured_role(message.author, bot_config.get('role_based_config', {}))
    if not role_info:
        await message.reply("Your roles do not have any configured usage limits.", mention_author=False); return
    role_name, role_config = role_info
    usage = check_and_reset_quota(message.author.id, role_config, user_usage_tracker)
    try:
        embed_color = discord.Color(int(role_config.get('display_color', "#ffffff").lstrip('#'), 16))
    except (ValueError, TypeError): embed_color = discord.Color.default()
    embed = discord.Embed(title=f"Quota Status for {message.author.display_name}", color=embed_color)
    embed.set_thumbnail(url=message.author.display_avatar.url)
    embed.set_footer(text=f"Current Role Tier: {role_name}")
    if role_config.get('enable_message_limit'):
        limit = role_config.get('message_limit', 0)
        embed.add_field(name="Message Quota", value=f"**{limit - usage['count']}/{limit}** remaining", inline=True)
    if role_config.get('enable_char_limit'):
        limit = role_config.get('char_limit', 0)
        embed.add_field(name="Token Quota", value=f"**{limit - usage['chars']}/{limit}** remaining", inline=True)
    
    enabled_refreshes = []
    if role_config.get('enable_message_limit'): enabled_refreshes.append(role_config.get('message_refresh_minutes', 60))
    if role_config.get('enable_char_limit'): enabled_refreshes.append(role_config.get('char_refresh_minutes', 60))
    shortest_refresh = min(enabled_refreshes) if enabled_refreshes else -1

    if embed.fields and shortest_refresh > 0:
        reset_time = usage['timestamp'] + timedelta(minutes=shortest_refresh)
        embed.add_field(name="Next Reset", value=f"<t:{int(reset_time.timestamp())}:R>", inline=False)
    elif not embed.fields:
        embed.description = "No usage limits are currently enabled for your role."
    await message.reply(embed=embed, mention_author=False)


async def run_bot(memory_cutoffs: Dict[int, datetime], user_usage_tracker: Dict[int, Dict[str, Any]]):
    setup_logging()
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f: config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.critical(f"Config file '{CONFIG_FILE}' not found or corrupted.", exc_info=True); return
    if not (token := config.get("discord_token")):
        logger.critical("Discord token not found in config. Bot will not start."); return
        
    intents = discord.Intents.default()
    intents.messages = True; intents.guilds = True; intents.message_content = True; intents.members = True
    client = discord.Client(intents=intents)
    token_calculator = TokenCalculator()
    BOT_CONFIG = config

    @client.event
    async def on_ready():
        logger.info(f'Logged in as {client.user} (ID: {client.user.id})')
        await client.change_presence(activity=discord.Game(name="Chatting with layered persona"))

    @client.event
    async def on_message(message: discord.Message):
        if message.author.bot: return
        
        # --- 修改点: 默认值从 [] 改为 {} ---
        plugin_manager = PluginManager(BOT_CONFIG.get('plugins', {}), get_llm_response)
        plugin_result = await plugin_manager.process_message(message, BOT_CONFIG)

        injected_data_str = None
        if isinstance(plugin_result, tuple) and plugin_result[0] == 'append':
            injected_data_str = "\n\n---\n\n".join(plugin_result[1])
        elif plugin_result is True:
            return 
        
        trigger_keywords = BOT_CONFIG.get("trigger_keywords", [])
        is_triggered = (any(k.lower() in message.content.lower() for k in trigger_keywords) or
                        client.user in message.mentions or
                        (message.reference and message.reference.resolved and message.reference.resolved.author == client.user))

        if message.content.strip().lower() == '!myquota':
            await handle_quota_command(message, BOT_CONFIG, user_usage_tracker); return
        if not is_triggered: return
        
        async with message.channel.typing():
            try:
                channel_id_str = str(message.channel.id)
                guild_id_str = str(message.guild.id) if message.guild else None
                role_name, role_config = (None, None)
                if isinstance(message.author, discord.Member):
                    role_info = get_highest_configured_role(message.author, BOT_CONFIG.get('role_based_config', {}))
                    if role_info:
                        role_name, role_config = role_info
                
                cutoff_ts = memory_cutoffs.get(message.channel.id)
                history_messages, history_for_llm = await build_context_history(client, BOT_CONFIG, message, cutoff_ts)
                
                specific_persona, situational_prompt, log1 = determine_bot_persona(BOT_CONFIG, channel_id_str, guild_id_str, role_name, role_config)
                system_prompt = build_system_prompt(BOT_CONFIG, specific_persona, situational_prompt, message, history_messages, log1)
                final_user_content = format_user_message_for_llm(message, client, BOT_CONFIG, role_config, injected_data_str)
                logger.info(f"Active Directives for msg {message.id}: {' | '.join(log1)}")
                
                if role_config:
                    usage = check_and_reset_quota(message.author.id, role_config, user_usage_tracker)
                    error_msg = await check_pre_request_quota(message, role_config, usage, token_calculator, BOT_CONFIG, system_prompt, history_for_llm, final_user_content)
                    if error_msg:
                        await message.reply(error_msg, mention_author=False)
                        return
                    
                user_message_parts: List[Dict[str, Any]] = [{"type": "text", "text": final_user_content}]
                image_urls = {att.url for att in message.attachments if "image" in att.content_type}
                if image_urls:
                    for url in image_urls: user_message_parts.append({"type": "image_url", "image_url": {"url": url}})
                
                final_messages = [{"role": "system", "content": system_prompt}] + history_for_llm + [{"role": "user", "content": user_message_parts}]

                logger.info(f"Sending request to LLM '{BOT_CONFIG.get('llm_provider')}' model '{BOT_CONFIG.get('model_name')}' for msg {message.id}.")
                response_obj, full_response, last_edit_time = None, "", 0.0
                is_direct_reply = client.user in message.mentions or (message.reference and message.reference.resolved and message.reference.resolved.author == client.user)
                
                # 收集上下文信息用于统计
                context_info = {
                    "user_id": str(message.author.id),
                    "user_name": message.author.name,
                    "user_display_name": message.author.display_name,
                    "channel_id": str(message.channel.id),
                    "channel_name": message.channel.name if hasattr(message.channel, 'name') else str(message.channel.id),
                    "guild_id": str(message.guild.id) if message.guild else None,
                    "guild_name": message.guild.name if message.guild else None,
                    "role_id": str(message.author.top_role.id) if isinstance(message.author, discord.Member) else None,
                    "role_name": message.author.top_role.name if isinstance(message.author, discord.Member) else None
                    }
          
                async for r_type, content in get_llm_response(BOT_CONFIG, final_messages, context_info):

                    full_response = content
                    if not BOT_CONFIG.get("stream_response", True): break
                    if r_type == "partial" and full_response:
                        display_content = full_response[:1990] + "..." if len(full_response)>1990 else full_response
                        current_time = asyncio.get_event_loop().time()
                        if not response_obj:
                            response_obj = await (message.reply(display_content, mention_author=False) if is_direct_reply else message.channel.send(display_content))
                            last_edit_time = current_time
                        elif current_time - last_edit_time > 1.2:
                            await response_obj.edit(content=display_content)
                            last_edit_time = current_time
                
                if full_response:
                    if role_config and (role_config.get('enable_message_limit') or role_config.get('enable_char_limit')):
                        update_post_request_usage(message.author.id, user_usage_tracker, token_calculator, BOT_CONFIG, system_prompt, history_for_llm, final_user_content, full_response)
                        
                    parts = split_message(full_response)
                    if not parts: return
                    if response_obj:
                        if response_obj.content != parts[0]: await response_obj.edit(content=parts[0])
                    else:
                        response_obj = await (message.reply(parts[0], mention_author=False) if is_direct_reply else message.channel.send(parts[0]))
                    for part in parts[1:]: await message.channel.send(part)
                else:
                    logger.warning(f"Received empty response from LLM for message {message.id}.")
            
            except Exception as e:
                logger.error(f"Error processing message {message.id}.", exc_info=True)
                await message.reply(f"An error occurred: `{type(e).__name__}`", mention_author=False)

    try:
        await client.start(token)
    except discord.errors.LoginFailure: logger.critical("Login failed. Check your Discord token.")
    except Exception as e: logger.critical("A fatal error occurred during bot runtime.", exc_info=True)
    finally:
        if client and not client.is_closed():
            logger.info("Closing bot client."); await client.close()

if __name__ == "__main__":
    memory_cutoffs = {}
    user_usage_tracker = {}
    asyncio.run(run_bot(memory_cutoffs, user_usage_tracker))
