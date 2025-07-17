# backend/plugins/manager.py

import discord
import logging
import asyncio
import json
from typing import List, Dict, Any

from app.utils import split_message, _format_with_placeholders, _execute_http_request

logger = logging.getLogger(__name__)

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
                        if not bot_config.get("stream_response", True): break
                        if r_type == "partial" and full_response:
                            display_content = full_response[:1990] + "..." if len(full_response)>1990 else full_response
                            if not response_obj:
                                response_obj = await message.reply(display_content, mention_author=False)
                            elif (asyncio.get_event_loop().time()) - last_edit_time > 1.2:
                                await response_obj.edit(content=display_content)
                                last_edit_time = asyncio.get_event_loop().time()
                    
                    if full_response:
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
