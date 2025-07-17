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
import tiktoken

def setup_logging():
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
    file_handler = RotatingFileHandler('logs/bot.log', maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)

logger = logging.getLogger(__name__)
CONFIG_FILE = "config.json"

class TokenCalculator:
    def __init__(self):
        self._openai_cache = {}
        self._anthropic_client = anthropic.Anthropic()

    def _get_openai_tokenizer(self, model_name: str):
        if model_name in self._openai_cache:
            return self._openai_cache[model_name]
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        self._openai_cache[model_name] = encoding
        return encoding

    def get_token_count(self, text: str, provider: str, model: str) -> int:
        if not text:
            return 0
        try:
            if provider == "openai":
                tokenizer = self._get_openai_tokenizer(model)
                return len(tokenizer.encode(text))
            elif provider == "anthropic":
                return self._anthropic_client.count_tokens(text)
            elif provider == "google":
                return max(1, int(len(text) / 3.5))
            else:
                return len(text)
        except Exception as e:
            logger.warning(f"Token calculation failed for provider {provider}: {e}. Falling back to character count.")
            return len(text)

async def download_image(url: str) -> bytes | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception as e:
        logger.warning(f"Error downloading image from {url}", exc_info=True)
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

# --- 函数 get_llm_response 已修正 ---
async def get_llm_response(config: dict, messages: List[Dict[str, Any]]) -> AsyncGenerator[tuple[str, str], None]:
    provider, api_key, base_url, model, stream = config.get("llm_provider", "openai"), config.get("api_key"), config.get("base_url"), config.get("model_name"), config.get("stream_response", True)
    extra_params = process_custom_params(config.get('custom_parameters', []))
    system_prompt = next((m['content'] for m in messages if m['role'] == 'system'), "")
    user_messages = [m for m in messages if m['role'] != 'system']

    full_response = ""

    async def response_generator():
        nonlocal full_response
        if provider == "openai":
            client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url if base_url else None)
            response_stream = await client.chat.completions.create(model=model, messages=messages, stream=stream, **extra_params)
            if stream:
                async for chunk in response_stream:
                    if content := chunk.choices[0].delta.content:
                        full_response += content
                        yield "partial", content  # 修正：返回两个值
            else:
                full_response = response_stream.choices[0].message.content
                # 对于非流式，我们也可以 yield 一次 partial 来统一处理
                if full_response:
                    yield "partial", full_response 
        
        elif provider == "google":
            # ... (Google 实现)
            full_response = "Simulated Google Response" # 假设的响应
            yield "partial", full_response # 修正：返回两个值
            
        elif provider == "anthropic":
            client = anthropic.AsyncAnthropic(api_key=api_key)
            if stream:
                async with client.messages.stream(max_tokens=4096, model=model, system=system_prompt, messages=user_messages, **extra_params) as s:
                    async for text in s.text_stream:
                        full_response += text
                        yield "partial", text # 修正：返回两个值
            else:
                response = await client.messages.create(max_tokens=4096, model=model, system=system_prompt, messages=user_messages, **extra_params)
                full_response = response.content[0].text
                if full_response:
                    yield "partial", full_response # 修正：返回两个值
        else:
            full_response = f"Error: Unsupported provider '{provider}'"
            yield "partial", full_response

    # 在循环外部处理累积的响应
    async for r_type, chunk_content in response_generator():
        # 这里只 yield partial，把 full 的判断移到外面
        yield r_type, full_response

    # response_generator 执行完毕后，full_response 包含了全部内容
    # 但我们不再需要在这里 yield "full"，因为外层循环会在结束后拿到最终的 full_response
    # 实际上，外层循环现在也不需要了，但为了保持结构，我们修改 yield 的内容

async def run_bot(memory_cutoffs: Dict[int, datetime], user_usage_tracker: Dict[int, Dict[str, Any]]):
    setup_logging()
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.critical(f"Config file '{CONFIG_FILE}' not found or corrupted.", exc_info=True); return
    if not (token := config.get("discord_token")):
        logger.critical("Discord token not found in config. Bot will not start."); return

    intents = discord.Intents.default()
    intents.messages = True; intents.guilds = True; intents.message_content = True; intents.members = True
    client = discord.Client(intents=intents)
    token_calculator = TokenCalculator()

    @client.event
    async def on_ready():
        logger.info(f'Logged in successfully as {client.user} (ID: {client.user.id})')

    async def handle_quota_command(message: discord.Message, bot_config: Dict[str, Any]):
        if not isinstance(message.author, discord.Member):
            await message.reply("Quota information is only available in servers.", mention_author=False); return
        role_info = get_highest_configured_role(message.author, bot_config.get('role_based_config', {}))
        if not role_info:
            await message.reply("Your roles do not have any configured usage limits.", mention_author=False); return

        role_name, role_config = role_info
        user_id, now = message.author.id, datetime.now(timezone.utc)
        usage = user_usage_tracker.get(user_id, {"count": 0, "chars": 0, "timestamp": now})
        
        shortest_refresh = min(
            role_config.get('message_refresh_minutes', 1e9) if role_config.get('enable_message_limit') else 1e9,
            role_config.get('char_refresh_minutes', 1e9) if role_config.get('enable_char_limit') else 1e9
        )
        if shortest_refresh != 1e9 and now - usage['timestamp'] > timedelta(minutes=shortest_refresh):
            usage = {"count": 0, "chars": 0, "timestamp": now}
            user_usage_tracker[user_id] = usage

        try:
            embed_color = discord.Color(int(role_config.get('display_color', "#ffffff").lstrip('#'), 16))
        except (ValueError, TypeError):
            embed_color = discord.Color.default()

        embed = discord.Embed(title=f"Quota Status for {message.author.display_name}", color=embed_color)
        embed.set_thumbnail(url=message.author.display_avatar.url); embed.set_footer(text=f"Current Role: {role_name}")

        if role_config.get('enable_message_limit'):
            limit = role_config.get('message_limit', 0)
            embed.add_field(name="Message Quota", value=f"**{limit - usage['count']}/{limit}** remaining", inline=True)
        if role_config.get('enable_char_limit'):
            limit = role_config.get('char_limit', 0)
            embed.add_field(name="Token Quota", value=f"**{limit - usage['chars']}/{limit}** remaining", inline=True)
        
        if embed.fields and shortest_refresh != 1e9:
            reset_time = usage['timestamp'] + timedelta(minutes=shortest_refresh)
            embed.add_field(name="Next Reset", value=f"<t:{int(reset_time.timestamp())}:R>", inline=False)
        elif not embed.fields:
            embed.description = "No usage limits are currently enabled for your role."
        await message.reply(embed=embed, mention_author=False)

    @client.event
    async def on_message(message: discord.Message):
        if message.author.bot: return
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f: bot_config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): return

        if message.content.strip().lower() == '!myquota':
            await handle_quota_command(message, bot_config); return

        is_trigger = (any(k.lower() in message.content.lower() for k in bot_config.get("trigger_keywords", [])) or
                      client.user in message.mentions or
                      (message.reference and message.reference.resolved and message.reference.resolved.author == client.user))
        if not is_trigger: return
        
        logger.info(f"Bot triggered for msg {message.id} by user {message.author.id}")

        async with message.channel.typing():
            provider = bot_config.get("llm_provider", "openai")
            model = bot_config.get("model_name", "")
            role_name, role_config = None, None
            if isinstance(message.author, discord.Member):
                if role_info := get_highest_configured_role(message.author, bot_config.get('role_based_config', {})):
                    role_name, role_config = role_info

            history_for_llm, context_text_for_calc = [], ""
            # ... (Implement your history fetching logic here) ...
            
            processed_content = message.content
            if message.mentions:
                 for mentioned_user in message.mentions:
                     if mentioned_user.id != client.user.id and message.guild and (member := message.guild.get_member(mentioned_user.id)):
                         _, m_role_config = get_highest_configured_role(member, bot_config.get('role_based_config', {})) or (None, None)
                         rich_id_str = get_rich_identity(member, bot_config.get("user_personas", {}), m_role_config)
                         processed_content = processed_content.replace(f'<@{mentioned_user.id}>', rich_id_str).replace(f'<@!{mentioned_user.id}>', rich_id_str)
            
            final_text_content = processed_content.replace(f'<@{client.user.id}>', '').replace(f'<@!{client.user.id}>', '')
            for keyword in bot_config.get("trigger_keywords", []): final_text_content = final_text_content.replace(keyword, "")
            final_text_content = final_text_content.strip()

            if role_config:
                user_id, now = message.author.id, datetime.now(timezone.utc)
                usage = user_usage_tracker.get(user_id, {"count": 0, "chars": 0, "timestamp": now})
                shortest_refresh = min(role_config.get('message_refresh_minutes', 60), role_config.get('char_refresh_minutes', 60))
                if now - usage['timestamp'] > timedelta(minutes=shortest_refresh):
                    usage = {"count": 0, "chars": 0, "timestamp": now}
                    user_usage_tracker[user_id] = usage

                if role_config.get('enable_message_limit') and (usage['count'] + 1) > role_config.get('message_limit', 0):
                    await message.reply(f"Your message quota would be exceeded.", mention_author=False); return

                if role_config.get('enable_char_limit'):
                    token_limit = role_config.get('char_limit', 0)
                    token_budget = role_config.get('char_output_budget', 300)
                    input_tokens = token_calculator.get_token_count(final_text_content, provider, model)
                    context_tokens = token_calculator.get_token_count(context_text_for_calc, provider, model)
                    pre_estimated_tokens = input_tokens + context_tokens + token_budget
                    if (usage['chars'] + pre_estimated_tokens) > token_limit:
                        await message.reply(f"Estimated token use ({pre_estimated_tokens}) would exceed your quota (Remaining: {token_limit - usage['chars']}).", mention_author=False); return

            final_system_prompt = bot_config.get("system_prompt", "You are a helpful assistant.")
            if (user_persona_info := bot_config.get("user_personas", {}).get(str(message.author.id))) and user_persona_info.get('prompt'):
                final_system_prompt = user_persona_info['prompt']
            elif role_config and role_config.get('prompt'):
                final_system_prompt = role_config['prompt']

            author_rich_id = get_rich_identity(message.author, bot_config.get("user_personas", {}), role_config)
            user_message_parts: List[Dict[str, Any]] = [{"type": "text", "text": format_user_message(author_rich_id, final_text_content)}]
            for attachment in message.attachments:
                if "image" in attachment.content_type: user_message_parts.append({"type": "image_url", "image_url": {"url": attachment.url}})

            final_messages = [{"role": "system", "content": final_system_prompt}] + history_for_llm + [{"role": "user", "content": user_message_parts}]

            try:
                response_obj, full_response, last_edit_time = None, "", 0
                is_direct_reply = client.user in message.mentions or (message.reference and message.reference.resolved and message.reference.resolved.author == client.user)
                
                # --- 主要循环逻辑修正 ---
                async for _, current_full_response in get_llm_response(bot_config, final_messages):
                    full_response = current_full_response # 持续更新 full_response
                    if bot_config.get("stream_response", True):
                        display_content = full_response[:1990] + "..." if len(full_response) > 1990 else full_response
                        if not response_obj: 
                            response_obj = await (message.reply(display_content, mention_author=False) if is_direct_reply else message.channel.send(display_content))
                        elif (current_time := asyncio.get_event_loop().time()) - last_edit_time > 1.2:
                            await response_obj.edit(content=display_content); last_edit_time = current_time

                # 循环结束后，full_response 保存着最终的完整回复
                if full_response:
                    if role_config and isinstance(message.author, discord.Member):
                        usage = user_usage_tracker[message.author.id]
                        input_tokens = token_calculator.get_token_count(final_text_content, provider, model)
                        context_tokens = token_calculator.get_token_count(context_text_for_calc, provider, model)
                        output_tokens = token_calculator.get_token_count(full_response, provider, model)
                        actual_tokens_consumed = input_tokens + context_tokens + output_tokens
                        usage['count'] += 1; usage['chars'] += actual_tokens_consumed
                        logger.info(f"Final token deduction for {message.author.id}: {actual_tokens_consumed}. New total: {usage['chars']}")
                    
                    parts = split_message(full_response)
                    if not parts: return
                    
                    final_content = parts[0]
                    if response_obj:
                         if response_obj.content != final_content:
                            await response_obj.edit(content=final_content)
                    else:
                        response_obj = await (message.reply(final_content, mention_author=False) if is_direct_reply else message.channel.send(final_content))
                    
                    for i in range(1, len(parts)): 
                        await message.channel.send(parts[i])
                else: 
                    logger.warning(f"Empty LLM response for msg {message.id}.")
            except Exception as e:
                logger.error(f"Error processing msg {message.id}.", exc_info=True)
                await message.reply(f"Error: {type(e).__name__}", mention_author=False)
    
    try:
        await client.start(token)
    except discord.errors.LoginFailure: logger.critical("Login failed. Check your token.")
    except Exception as e: logger.critical("A fatal error occurred.", exc_info=True)
    finally:
        if client and not client.is_closed(): await client.close()
