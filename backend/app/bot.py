import asyncio
import json
import discord
import os
import aiohttp
from io import BytesIO
from typing import AsyncGenerator, Dict, List, Union, Any, Set, Optional, Tuple
from datetime import datetime, timedelta, timezone

import logging
from logging.handlers import RotatingFileHandler

import openai
import google.generativeai as genai
import anthropic

# --- 日志系统设置 ---
def setup_logging():
    """配置日志系统，输出到控制台和文件。"""
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(log_formatter)
    logger.addHandler(stream_handler)

    if not os.path.exists('logs'):
        os.makedirs('logs')
    file_handler = RotatingFileHandler(
        'logs/bot.log', maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)

logger = logging.getLogger(__name__)
# --- 日志系统设置结束 ---

CONFIG_FILE = "config.json"

async def download_image(url: str) -> bytes | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200: return await resp.read()
    except Exception as e:
        logger.warning(f"Error downloading image from {url}", exc_info=True)
    return None

def get_highest_configured_role(member: discord.Member, role_configs: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    """从用户的身份组中，找到配置中存在的、且在 Discord 中层级最高的那个身份组。"""
    for role in reversed(member.roles): # member.roles 默认按层级从低到高排序，倒序遍历即可
        role_id_str = str(role.id)
        if role_id_str in role_configs:
            return role.name, role_configs[role_id_str]
    return None

def get_rich_identity(author: Union[discord.User, discord.Member], personas: Dict[str, Any], role_config: Optional[Dict[str, Any]]) -> str:
    """获取用户的丰富身份信息，优先级：用户昵称 > 身份组头衔 > Discord 显示名称。"""
    user_id_str, display_name = str(author.id), author.display_name
    persona_info = personas.get(user_id_str)
    
    if persona_info and isinstance(persona_info, dict) and persona_info.get('nickname'):
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
        if len(text) <= max_length:
            parts.append(text)
            break
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
                elif not isinstance(value, str): processed_params[name] = value # Already a JSON object from frontend
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
                role = 'model' if msg['role'] == 'assistant' else 'user'
                content = msg['content']
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
        logger.critical(f"Config file '{CONFIG_FILE}' not found or corrupted. Bot cannot start.", exc_info=True)
        return
    if not (token := config.get("discord_token")):
        logger.critical("Discord token not found in config. Bot will not start.")
        return
    
    intents = discord.Intents.default()
    intents.messages = True; intents.guilds = True; intents.message_content = True; intents.members = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        logger.info(f'Logged in successfully as {client.user} (ID: {client.user.id})')
        await client.change_presence(activity=discord.Game(name="Chatting reliably"))

    @client.event
    async def on_message(message: discord.Message):
        if message.author.bot: return
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f: bot_config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning(f"Could not load config file for message {message.id}. Aborting processing.")
            return

        is_trigger = (any(k.lower() in message.content.lower() for k in bot_config.get("trigger_keywords", [])) or
                      client.user in message.mentions or
                      (message.reference and message.reference.resolved and message.reference.resolved.author == client.user))
        
        if not is_trigger: return
        
        logger.info(f"Bot triggered for message {message.id} by user {message.author.id} in channel {message.channel.id}.")

        role_name, role_config = None, None
        if isinstance(message.author, discord.Member):
            role_configs = bot_config.get('role_based_config', {})
            role_config_result = get_highest_configured_role(message.author, role_configs)
            if role_config_result:
                role_name, role_config = role_config_result
                user_id, now = message.author.id, datetime.now(timezone.utc)
                usage = user_usage_tracker.get(user_id, {"count": 0, "chars": 0, "timestamp": now})

                def check_limit(limit_type, current_val, limit_val, refresh_mins):
                    if limit_val > 0 and refresh_mins > 0:
                        if now - usage['timestamp'] > timedelta(minutes=refresh_mins):
                            return "RESET", None
                        if current_val >= limit_val:
                            return "LIMITED", f"You have reached the {limit_type} limit for your role '{role_name}' ({current_val}/{limit_val}). Please try again later."
                    return "OK", None
                
                status_msg, error_msg_msg = check_limit('message', usage['count'], role_config.get('message_limit', 0), role_config.get('message_refresh_minutes', 60))
                status_char, error_char_msg = check_limit('character', usage['chars'], role_config.get('char_limit', 0), role_config.get('char_refresh_minutes', 60))

                if status_msg == "RESET" or status_char == "RESET":
                    logger.info(f"Usage tracker reset for user {user_id}")
                    usage = {"count": 0, "chars": 0, "timestamp": now}
                
                if status_msg == "LIMITED": await message.reply(error_msg_msg, mention_author=False); return
                if status_char == "LIMITED": await message.reply(error_char_msg, mention_author=False); return
                
                user_usage_tracker[user_id] = usage

        async with message.channel.typing():
            user_personas = bot_config.get("user_personas", {})
            user_persona_info = user_personas.get(str(message.author.id))
            
            author_rich_id = get_rich_identity(message.author, user_personas, role_config)
            
            final_system_prompt = bot_config.get("system_prompt", "You are a helpful assistant.")
            if user_persona_info and user_persona_info.get('prompt'):
                final_system_prompt = user_persona_info['prompt']
                logger.info(f"Using user-specific persona for {message.author.id}")
            elif role_config and role_config.get('prompt'):
                final_system_prompt = role_config['prompt']
                logger.info(f"Using role-based persona for {message.author.id} from role '{role_name}'")

            history_for_llm = [] 

            processed_content = message.content
            if message.mentions:
                for mentioned_user in message.mentions:
                     if mentioned_user.id != client.user.id and message.guild:
                         if member := message.guild.get_member(mentioned_user.id):
                             m_role_name, m_role_config = None, None
                             if res := get_highest_configured_role(member, bot_config.get('role_based_config', {})):
                                m_role_name, m_role_config = res
                             rich_id_str = get_rich_identity(member, user_personas, m_role_config)
                             processed_content = processed_content.replace(f'<@{mentioned_user.id}>', rich_id_str).replace(f'<@!{mentioned_user.id}>', rich_id_str)

            final_text_content = processed_content.replace(f'<@{client.user.id}>', '').replace(f'<@!{client.user.id}>', '')
            for keyword in bot_config.get("trigger_keywords", []): final_text_content = final_text_content.replace(keyword, "")
            final_text_content = final_text_content.strip()

            final_user_message_str = format_user_message(author_rich_id, final_text_content)
            user_message_parts: List[Dict[str, Any]] = [{"type": "text", "text": final_user_message_str}]

            for attachment in message.attachments:
                if "image" in attachment.content_type:
                    user_message_parts.append({"type": "image_url", "image_url": {"url": attachment.url}})

            final_messages = [{"role": "system", "content": final_system_prompt}] + history_for_llm
            final_messages.append({"role": "user", "content": user_message_parts})

            try:
                logger.info(f"Sending request to LLM provider '{bot_config.get('llm_provider')}' model '{bot_config.get('model_name')}'.")
                response_obj, full_response = None, ""
                last_edit_time = 0
                is_direct_reply_action = client.user in message.mentions or (message.reference and message.reference.resolved and message.reference.resolved.author == client.user)

                async for r_type, content in get_llm_response(bot_config, final_messages):
                    full_response = content
                    if bot_config.get("stream_response", True) and r_type == "partial" and full_response:
                        display_content = full_response if len(full_response) <= 1990 else f"...{full_response[-1990:]}"
                        if not response_obj:
                            response_obj = await (message.reply(display_content, mention_author=False) if is_direct_reply_action else message.channel.send(display_content))
                        else:
                            current_time = asyncio.get_event_loop().time()
                            if (current_time - last_edit_time) > 1.2:
                                await response_obj.edit(content=display_content)
                                last_edit_time = current_time
                
                if full_response:
                    logger.info(f"Successfully received full response for message {message.id}.")
                    if role_config and isinstance(message.author, discord.Member):
                        user_id = message.author.id
                        usage = user_usage_tracker[user_id]
                        usage['count'] += 1
                        usage['chars'] += len(final_text_content)
                        logger.info(f"Updated usage for user {user_id}: count={usage['count']}, chars={usage['chars']}")
                    
                    parts = split_message(full_response)
                    if not parts: return
                    
                    if response_obj: await response_obj.edit(content=parts[0])
                    else: response_obj = await (message.reply(parts[0], mention_author=False) if is_direct_reply_action else message.channel.send(parts[0]))
                    
                    for i in range(1, len(parts)): await message.channel.send(parts[i])
                else: 
                    logger.warning(f"Received an empty response from LLM for message {message.id}.")
                    await message.channel.send("（空回应）")

            except Exception as e:
                logger.error(f"An unhandled error occurred while processing message {message.id}.", exc_info=True)
                await message.reply(f"发生错误: {type(e).__name__}", mention_author=False)

    try:
        await client.start(token)
    except discord.errors.LoginFailure:
        logger.critical("Login failed. Please check your Discord token in the config file.")
    except Exception as e:
        logger.critical("A fatal error occurred during bot runtime.", exc_info=True)
    finally:
        if client and not client.is_closed():
            await client.close()
