from app.utils import split_message

import discord
import logging
import aiohttp
import json
import asyncio # 将asyncio导入到文件顶部
from typing import List, Dict, Any, Optional

# --- 【【【核心修改区】】】 ---
# 使用绝对路径从 app 包导入需要的函数
from app.bot import split_message
# --- 【【【修改结束】】】 ---

logger = logging.getLogger(__name__)

def _format_with_placeholders(template_str: str, message: discord.Message, args: str) -> str:
    """用消息上下文中的值替换模板字符串中的占位符。"""
    if not isinstance(template_str, str): return ''
    
    # 基础占位符
    replacements = {
        "{user_input}": args,
        "{raw_content}": message.content,
        "{author_id}": str(message.author.id),
        "{author_name}": message.author.name,
        "{author_display_name}": message.author.display_name,
        "{channel_id}": str(message.channel.id),
        "{guild_id}": str(message.guild.id) if message.guild else "N/A",
    }
    
    for placeholder, value in replacements.items():
        template_str = template_str.replace(placeholder, value)
        
    return template_str

async def _execute_http_request(plugin_config: Dict[str, Any], message: discord.Message, args: str) -> Optional[str]:
    """执行HTTP请求并返回结果字符串。"""
    http_conf = plugin_config.get('http_request_config', {})
    url = _format_with_placeholders(http_conf.get('url', ''), message, args)
    method = http_conf.get('method', 'GET').upper()
    
    if not url:
        logger.warning(f"Plugin '{plugin_config.get('name')}' has no URL configured.")
        return None

    headers_str = _format_with_placeholders(http_conf.get('headers', '{}'), message, args)
    body_str = _format_with_placeholders(http_conf.get('body_template', '{}'), message, args)

    try:
        headers = json.loads(headers_str) if headers_str.strip() else {}
        if body_str.strip() and 'content-type' not in (h.lower() for h in headers):
            headers['Content-Type'] = 'application/json'

        async with aiohttp.ClientSession(headers=headers) as session:
            request_kwargs = {}
            if method in ['POST', 'PUT', 'PATCH']:
                try:
                    request_kwargs['json'] = json.loads(body_str)
                except json.JSONDecodeError:
                    request_kwargs['data'] = body_str

            async with session.request(method, url, **request_kwargs) as response:
                response_text = await response.text()
                if 200 <= response.status < 300:
                    logger.info(f"Plugin '{plugin_config.get('name')}' HTTP request to {url} successful.")
                    return response_text
                else:
                    logger.error(f"Plugin '{plugin_config.get('name')}' HTTP request failed with status {response.status}: {response_text}")
                    return f"Error: API call failed with status {response.status}."
    except aiohttp.ClientError as e:
        logger.error(f"Plugin '{plugin_config.get('name')}' HTTP request network error: {e}", exc_info=True)
        return f"Error: Network error during API call: {e}"
    except (json.JSONDecodeError, TypeError) as e:
         logger.error(f"Plugin '{plugin_config.get('name')}' failed to parse Headers or Body JSON: {e}", exc_info=True)
         return f"Error: Invalid JSON in plugin configuration (Headers/Body): {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred in plugin '{plugin_config.get('name')}': {e}", exc_info=True)
        return f"Error: An unexpected error occurred while running the plugin."

class PluginManager:
    def __init__(self, plugins_config: List[Dict[str, Any]], llm_responder):
        self.plugins = [p for p in plugins_config if p.get('enabled')]
        self._get_llm_response = llm_responder
        logger.info(f"PluginManager initialized with {len(self.plugins)} enabled plugins.")

    async def process_message(self, message: discord.Message, bot_config: Dict[str, Any]) -> bool:
        content = message.content.strip()
        if not content:
            return False

        for plugin in self.plugins:
            trigger_type = plugin.get('trigger_type')
            triggers = [t.strip().lower() for t in plugin.get('triggers', []) if t.strip()]
            
            matched = False
            args = ''

            if trigger_type == 'command':
                for trigger in triggers:
                    if content.lower().startswith(trigger):
                        matched = True
                        args = content[len(trigger):].strip()
                        break
            elif trigger_type == 'keyword':
                for trigger in triggers:
                    if trigger in content.lower():
                        matched = True
                        args = content
                        break
            
            if matched:
                logger.info(f"Message {message.id} triggered plugin '{plugin.get('name')}' with trigger type '{trigger_type}'.")
                await self._execute_plugin(plugin, message, args, bot_config)
                return True

        return False

    async def _execute_plugin(self, plugin: Dict[str, Any], message: discord.Message, args: str, bot_config: Dict[str, Any]):
        action_type = plugin.get('action_type')

        try:
            async with message.channel.typing():
                if action_type == 'http_request':
                    result = await _execute_http_request(plugin, message, args)
                    if result:
                        # 不再需要局部导入
                        parts = split_message(result)
                        for part in parts:
                            await message.reply(part, mention_author=False)

                elif action_type == 'llm_augmented_tool':
                    api_result = await _execute_http_request(plugin, message, args)
                    if not api_result:
                        await message.reply("Sorry, the tool failed to fetch data.", mention_author=False)
                        return

                    prompt_template = plugin.get('llm_prompt_template', "Please summarize the following data:\n\n{api_result}")
                    final_prompt = _format_with_placeholders(prompt_template, message, args)
                    final_prompt = final_prompt.replace("{api_result}", api_result)

                    llm_messages = [{"role": "system", "content": "You are a helpful assistant that processes data from tools."}, {"role": "user", "content": final_prompt}]
                    
                    full_response = ""
                    response_obj = None
                    last_edit_time = 0.0
                    async for r_type, content in self._get_llm_response(bot_config, llm_messages):
                        full_response = content
                        if not bot_config.get("stream_response", True):
                            break
                        if r_type == "partial" and full_response:
                            display_content = full_response[:1990] + "..." if len(full_response)>1990 else full_response
                            if not response_obj:
                                response_obj = await message.reply(display_content, mention_author=False)
                            elif (asyncio.get_event_loop().time()) - last_edit_time > 1.2:
                                # 不再需要局部导入
                                await response_obj.edit(content=display_content)
                                last_edit_time = asyncio.get_event_loop().time()
                    
                    if full_response:
                        # 不再需要局部导入
                        parts = split_message(full_response)
                        if not parts: return
                        if response_obj:
                            if response_obj.content != parts[0]: await response_obj.edit(content=parts[0])
                        else: response_obj = await message.reply(parts[0], mention_author=False)
                        for i in range(1, len(parts)): await message.channel.send(parts[i])
                    else:
                        await message.reply("The tool gathered data, but the AI model returned an empty summary.", mention_author=False)

        except Exception as e:
            logger.error(f"Failed to execute plugin '{plugin.get('name')}'. Error: {e}", exc_info=True)
            await message.reply(f"An error occurred while running the plugin: `{type(e).__name__}`", mention_author=False)
