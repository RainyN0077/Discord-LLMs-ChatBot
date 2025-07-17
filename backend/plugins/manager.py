# backend/plugins/manager.py

import discord
import logging
import asyncio
import json
from typing import List, Dict, Any, Tuple, Optional, Union

from app.utils import split_message, _format_with_placeholders, _execute_http_request

logger = logging.getLogger(__name__)

class PluginManager:
    def __init__(self, plugins_config: List[Dict[str, Any]], llm_responder):
        self.plugins = [p for p in plugins_config if p.get('enabled')]
        self._get_llm_response = llm_responder
        logger.info(f"PluginManager initialized with {len(self.plugins)} enabled plugins.")

    # --- 【【【核心修改区：修改 process_message 的返回值】】】 ---
    async def process_message(
        self, message: discord.Message, bot_config: Dict[str, Any]
    ) -> Union[bool, Tuple[str, str]]:
        """
        处理消息。
        - 如果插件是 'override' 模式并成功执行，返回 True。
        - 如果插件是 'append' 模式并成功执行，返回一个元组 ('append', data_string)。
        - 如果没有插件被触发，返回 False。
        """
        content = message.content.strip()
        if not content:
            return False
 
        for plugin in self.plugins:
            # ... (触发器匹配逻辑保持不变) ...
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
                logger.info(f"Message {message.id} triggered plugin '{plugin.get('name')}' with injection mode '{plugin.get('injection_mode', 'override')}'.")
                # 调用执行函数，并根据返回结果决定下一步
                return await self._execute_plugin(plugin, message, args, bot_config)
 
        return False
 
    async def _execute_plugin(
        self, plugin: Dict[str, Any], message: discord.Message, args: str, bot_config: Dict[str, Any]
    ) -> Union[bool, Tuple[str, str]]:
        """
        执行单个插件的逻辑，并根据注入模式返回不同的结果。
        """
        action_type = plugin.get('action_type')
        injection_mode = plugin.get('injection_mode', 'override')
 
        try:
            async with message.channel.typing():
                # 直接输出模式，行为不变，执行完就结束
                if action_type == 'http_request':
                    result = await _execute_http_request(plugin, message, args)
                    if result:
                        parts = split_message(result)
                        for part in parts:
                            await message.reply(part, mention_author=False)
                    return True # 流程结束
 
                # LLM增强工具，需要根据注入模式分别处理
                elif action_type == 'llm_augmented_tool':
                    api_result = await _execute_http_request(plugin, message, args)
                    if not api_result:
                        await message.reply("抱歉，工具未能获取到数据。", mention_author=False)
                        return True # 获取数据失败，流程也结束
 
                    # --- '追加' 模式 ---
                    if injection_mode == 'append':
                        # 我们不在这里调用LLM，而是准备好数据，返回给主流程
                        # 模板可以简单一些，主要是为了格式化数据
                        prompt_template = plugin.get('llm_prompt_template', "Tool execution result for '{user_input}':\n{api_result}")
                        formatted_data = _format_with_placeholders(prompt_template, message, args)
                        formatted_data = formatted_data.replace("{api_result}", api_result)
                        
                        logger.info(f"Plugin '{plugin.get('name')}' is appending data to context.")
                        return ('append', formatted_data) # 返回元组，代表需要追加
 
                    # --- '覆盖' 模式 (默认行为，保持不变) ---
                    else: 
                        prompt_template = plugin.get('llm_prompt_template', "Please summarize the following data:\n\n{api_result}")
                        final_prompt = _format_with_placeholders(prompt_template, message, args)
                        final_prompt = final_prompt.replace("{api_result}", api_result)
                        
                        llm_messages = [{"role": "system", "content": "You are a helpful assistant that processes data from tools."}, {"role": "user", "content": final_prompt}]
                        
                        # ... (流式输出的逻辑保持不变) ...
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
                            if not parts: return True
                            if response_obj:
                                if response_obj.content != parts[0]: await response_obj.edit(content=parts[0])
                            else: response_obj = await message.reply(parts[0], mention_author=False)
                            for i in range(1, len(parts)): await message.channel.send(parts[i])
                        else:
                            await message.reply("The tool gathered data, but the AI model returned an empty summary.", mention_author=False)
                        
                        return True # 流程结束
 
        except Exception as e:
            logger.error(f"Failed to execute plugin '{plugin.get('name')}'. Error: {e}", exc_info=True)
            await message.reply(f"An error occurred while running the plugin: `{type(e).__name__}`", mention_author=False)
            return True # 出现异常，流程也结束
        
        return False # 理论上不会到这里

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
