import asyncio
import json
import discord
import os
import aiohttp
from io import BytesIO
from typing import AsyncGenerator, Dict, List, Union, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
import logging
from logging.handlers import RotatingFileHandler
import openai
import google.generativeai as genai
import anthropic

def setup_logging():
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    if logger.hasHandlers(): logger.handlers.clear()
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(log_formatter)
    logger.addHandler(stream_handler)
    if not os.path.exists('logs'): os.makedirs('logs')
    file_handler = RotatingFileHandler('logs/bot.log', maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)

logger = logging.getLogger(__name__)
CONFIG_FILE = "config.json"

async def download_image(url: str) -> bytes | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200: return await resp.read()
    except Exception as e: logger.warning(f"Error downloading image from {url}", exc_info=True)
    return None

def get_highest_configured_role(member: discord.Member, role_configs: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    for role in reversed(member.roles):
        if (role_id_str := str(role.id)) in role_configs:
            return role.name, role_configs[role_id_str]
    return None

def get_rich_identity(author: Union[discord.User, discord.Member], personas: Dict[str, Any], role_config: Optional[Dict[str, Any]]) -> str:
    user_id_str, display_name = str(author.id), author.display_name
    if (persona_info := personas.get(user_id_str)) and persona_info.get('nickname'):
        display_name = persona_info['nickname']
    elif role_config and role_config.get('title'):
        display_name = role_config['title']
    return f"{display_name} (Username: {author.name}, ID: {user_id_str})"

def escape_content(text: str) -> str:
    return text.replace('[', '&#91;').replace(']', '&#93;')

def format_user_message(author_rich_id: str, content: str) -> str:
    escaped_content = escape_content(content)
    return f"Sender: {author_rich_id}\nMessage:\n---\n{escaped_content}\n---"

def split_message(text: str, max_length: int = 2000) -> List[str]:
    if not text: return []
    parts = []
    while len(text) > 0:
        if len(text) <= max_length: parts.append(text); break
        try: cut_index = text.rindex('\n', 0, max_length)
        except ValueError: cut_index = -1
        if cut_index == -1:
            try: cut_index = text.rindex(' ', 0, max_length)
            except ValueError: cut_index = max_length
        parts.append(text[:cut_index].strip())
        text = text[cut_index:].strip()
    return parts

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

    async def response_generator():
        if provider == "openai":
            client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url if base_url else None)
            response_stream = await client.chat.completions.create(model=model, messages=messages, stream=stream, **extra_params)
            if stream:
                async for chunk in response_stream:
                    if content := chunk.choices[0].delta.content: yield content
            else: yield response_stream.choices[0].message.content
        elif provider == "google":
            genai.configure(api_key=api_key)
            valid_gemini_keys = {'temperature', 'top_p', 'top_k', 'candidate_count', 'max_output_tokens', 'stop_sequences'}
            generation_config = {k: v for k, v in extra_params.items() if k in valid_gemini_keys}
            model_instance = genai.GenerativeModel(model, system_instruction=system_prompt, generation_config=generation_config)
            google_formatted_messages = []
            for msg in user_messages:
                role, content = ('model' if msg['role'] == 'assistant' else 'user'), msg['content']
                parts = []
                if isinstance(content, list):
                    for part in content:
                        if part['type'] == 'text': parts.append(part['text'])
                        elif part['type'] == 'image_url' and 'url' in part.get('image_url', {}):
                            if image_data := await download_image(part['image_url']['url']):
                                parts.append({'mime_type': 'image/jpeg', 'data': image_data})
                elif isinstance(content, str): parts.append(content)
                if parts: google_formatted_messages.append({'role': role, 'parts': parts})
            if stream:
                response_stream = await model_instance.generate_content_async(google_formatted_messages, stream=True)
                async for chunk in response_stream:
                    if chunk.parts: yield chunk.text
            else:
                response = await model_instance.generate_content_async(google_formatted_messages)
                yield response.text
        elif provider == "anthropic":
            client = anthropic.AsyncAnthropic(api_key=api_key)
            if stream:
                async with client.messages.stream(max_tokens=4096, model=model, system=system_prompt, messages=user_messages, **extra_params) as s:
                    async for text in s.text_stream: yield text
            else:
                response = await client.messages.create(max_tokens=4096, model=model, system=system_prompt, messages=user_messages, **extra_params)
                yield response.content[0].text
        else:
            yield f"Error: Unsupported provider '{provider}'"

    full_response = ""
    async for chunk in response_generator():
        full_response += chunk
        if stream: yield "partial", full_response
    yield "full", full_response

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

    @client.event
    async def on_ready():
        logger.info(f'Logged in successfully as {client.user} (ID: {client.user.id})')

    async def handle_quota_command(message: discord.Message, bot_config: Dict[str, Any]):
        if not isinstance(message.author, discord.Member):
            await message.reply("Quota information is only available in servers.", mention_author=False)
            return

        role_info = get_highest_configured_role(message.author, bot_config.get('role_based_config', {}))
        if not role_info:
            await message.reply("Your roles do not have any configured usage limits.", mention_author=False)
            return

        role_name, role_config = role_info
        user_id, now = message.author.id, datetime.now(timezone.utc)
        usage = user_usage_tracker.get(user_id, {"count": 0, "chars": 0, "timestamp": now})

        msg_refresh = role_config.get('message_refresh_minutes', 60)
        char_refresh = role_config.get('char_refresh_minutes', 60)
        
        # 使用最短的刷新周期来决定是否重置
        shortest_refresh = min(msg_refresh if role_config.get('enable_message_limit') else 1e9, 
                               char_refresh if role_config.get('enable_char_limit') else 1e9)

        if shortest_refresh != 1e9 and now - usage['timestamp'] > timedelta(minutes=shortest_refresh):
            usage = {"count": 0, "chars": 0, "timestamp": now}
            user_usage_tracker[user_id] = usage

        try:
            color_hex = role_config.get('display_color', "#ffffff").lstrip('#')
            embed_color = discord.Color(int(color_hex, 16))
        except (ValueError, TypeError):
            embed_color = discord.Color.default()

        embed = discord.Embed(title=f"Quota Status for {message.author.display_name}", color=embed_color)
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text=f"Current Role: {role_name}")

        if role_config.get('enable_message_limit'):
            limit = role_config.get('message_limit', 0)
            value = f"**{limit - usage['count']}/{limit}** remaining"
            embed.add_field(name="Message Quota", value=value, inline=True)
        
        if role_config.get('enable_char_limit'):
            limit = role_config.get('char_limit', 0)
            value = f"**{limit - usage['chars']}/{limit}** remaining"
            embed.add_field(name="Character Quota", value=value, inline=True)
        
        if embed.fields:
             reset_time = usage['timestamp'] + timedelta(minutes=shortest_refresh)
             embed.add_field(name="Next Reset", value=f"<t:{int(reset_time.timestamp())}:R>", inline=False)
        else:
             embed.description = "No usage limits are currently enabled for your role."

        await message.reply(embed=embed, mention_author=False)

    @client.event
    async def on_message(message: discord.Message):
        if message.author.bot: return
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f: bot_config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): return

        if message.content.strip().lower() == '!myquota':
            await handle_quota_command(message, bot_config)
            return

        is_trigger = (any(k.lower() in message.content.lower() for k in bot_config.get("trigger_keywords", [])) or
                      client.user in message.mentions or
                      (message.reference and message.reference.resolved and message.reference.resolved.author == client.user))
        
        if not is_trigger: return
        
        logger.info(f"Bot triggered for msg {message.id} by user {message.author.id}")

        role_name, role_config = None, None
        if isinstance(message.author, discord.Member):
            if role_info := get_highest_configured_role(message.author, bot_config.get('role_based_config', {})):
                role_name, role_config = role_info
                user_id, now = message.author.id, datetime.now(timezone.utc)
                usage = user_usage_tracker.get(user_id, {"count": 0, "chars": 0, "timestamp": now})

                def check_reset_and_limit(limit_type, current_val, limit_val, refresh_mins):
                    if limit_val > 0 and refresh_mins > 0:
                        if now - usage['timestamp'] > timedelta(minutes=refresh_mins): return "RESET", None
                        if current_val >= limit_val: return "LIMITED", f"You've reached the {limit_type} limit for your role '{role_name}' ({current_val}/{limit_val}). Try again later."
                    return "OK", None

                if role_config.get('enable_message_limit'):
                    status, error_msg = check_reset_and_limit('message', usage['count'], role_config.get('message_limit', 0), role_config.get('message_refresh_minutes', 60))
                    if status == "RESET": usage = {"count": 0, "chars": 0, "timestamp": now}
                    elif status == "LIMITED": await message.reply(error_msg, mention_author=False); return

                if role_config.get('enable_char_limit'):
                    status, error_msg = check_reset_and_limit('character', usage['chars'], role_config.get('char_limit', 0), role_config.get('char_refresh_minutes', 60))
                    if status == "RESET" and usage['count'] > 0: usage = {"count": 0, "chars": 0, "timestamp": now}
                    elif status == "LIMITED": await message.reply(error_msg, mention_author=False); return
                
                user_usage_tracker[user_id] = usage
        
        async with message.channel.typing():
            user_personas = bot_config.get("user_personas", {})
            author_rich_id = get_rich_identity(message.author, user_personas, role_config)
            
            final_system_prompt = bot_config.get("system_prompt", "You are a helpful assistant.")
            if (user_persona_info := user_personas.get(str(message.author.id))) and user_persona_info.get('prompt'):
                final_system_prompt = user_persona_info['prompt']
            elif role_config and role_config.get('prompt'):
                final_system_prompt = role_config['prompt']

            history_for_llm = [] 
            processed_content = message.content
            if message.mentions:
                for mentioned_user in message.mentions:
                     if mentioned_user.id != client.user.id and message.guild and (member := message.guild.get_member(mentioned_user.id)):
                         _, m_role_config = get_highest_configured_role(member, bot_config.get('role_based_config', {})) or (None, None)
                         rich_id_str = get_rich_identity(member, user_personas, m_role_config)
                         processed_content = processed_content.replace(f'<@{mentioned_user.id}>', rich_id_str).replace(f'<@!{mentioned_user.id}>', rich_id_str)

            final_text_content = processed_content.replace(f'<@{client.user.id}>', '').replace(f'<@!{client.user.id}>', '')
            for keyword in bot_config.get("trigger_keywords", []): final_text_content = final_text_content.replace(keyword, "")
            final_text_content = final_text_content.strip()

            user_message_parts: List[Dict[str, Any]] = [{"type": "text", "text": format_user_message(author_rich_id, final_text_content)}]
            for attachment in message.attachments:
                if "image" in attachment.content_type: user_message_parts.append({"type": "image_url", "image_url": {"url": attachment.url}})

            final_messages = [{"role": "system", "content": final_system_prompt}] + history_for_llm + [{"role": "user", "content": user_message_parts}]

            try:
                response_obj, full_response, last_edit_time = None, "", 0
                is_direct_reply = client.user in message.mentions or (message.reference and message.reference.resolved and message.reference.resolved.author == client.user)
                async for r_type, content in get_llm_response(bot_config, final_messages):
                    full_response = content
                    if bot_config.get("stream_response", True) and r_type == "partial" and full_response:
                        display_content = full_response if len(full_response) <= 1990 else f"...{full_response[-1990:]}"
                        if not response_obj: response_obj = await (message.reply(display_content, mention_author=False) if is_direct_reply else message.channel.send(display_content))
                        elif (current_time := asyncio.get_event_loop().time()) - last_edit_time > 1.2:
                            await response_obj.edit(content=display_content); last_edit_time = current_time
                
                if full_response:
                    if role_config and isinstance(message.author, discord.Member):
                        usage = user_usage_tracker[message.author.id]
                        usage['count'] += 1; usage['chars'] += len(final_text_content)
                        logger.info(f"Updated usage for user {message.author.id}: count={usage['count']}, chars={usage['chars']}")
                    
                    parts = split_message(full_response)
                    if not parts: return
                    if response_obj: await response_obj.edit(content=parts[0])
                    else: response_obj = await (message.reply(parts[0], mention_author=False) if is_direct_reply else message.channel.send(parts[0]))
                    for i in range(1, len(parts)): await message.channel.send(parts[i])
                else: logger.warning(f"Empty LLM response for msg {message.id}.")

            except Exception as e:
                logger.error(f"Error processing msg {message.id}.", exc_info=True)
                await message.reply(f"Error: {type(e).__name__}", mention_author=False)
    try:
        await client.start(token)
    except discord.errors.LoginFailure: logger.critical("Login failed. Check your token.")
    except Exception as e: logger.critical("A fatal error occurred.", exc_info=True)
    finally:
        if client and not client.is_closed(): await client.close()
