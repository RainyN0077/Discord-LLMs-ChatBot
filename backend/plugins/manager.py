# backend/plugins/manager.py
import logging
import re
from typing import List, Dict, Any, Optional, Tuple

import discord
# 修复：将相对导入 '..app.utils' 改为绝对导入 'app.utils'
from app.utils import _execute_http_request, _format_with_placeholders

logger = logging.getLogger(__name__)

class PluginManager:
    # --- 修改点: 更新类型提示和初始化逻辑 ---
    def __init__(self, plugins_config: Dict[str, Any], llm_caller):
        self.plugins = [p for p in plugins_config.values() if p.get('enabled')]
        self.llm_caller = llm_caller

    async def process_message(self, message: discord.Message, bot_config: Dict[str, Any]) -> Optional[Tuple[str, List[str]] | bool]:
        """
        处理消息，检查是否有插件被触发。
        允许多个 'append' 模式的插件被触发。
        
        Returns:
            - ('append', list_of_strings): 如果一个或多个插件希望将数据注入上下文。
            - True: 如果一个 'override' 模式的插件已处理消息并希望终止后续处理。
            - None: 如果没有插件被触发。
        """
        triggered_appends = []
        
        for plugin in self.plugins:
            trigger_type = plugin.get('trigger_type', 'command')
            triggers = plugin.get('triggers', [])
            
            is_triggered = False
            args = ""
            
            if trigger_type == 'command':
                for trigger in triggers:
                    if message.content.startswith(trigger):
                        is_triggered = True
                        args = message.content[len(trigger):].strip()
                        break
            elif trigger_type == 'keyword':
                for trigger in triggers:
                    # Make sure triggers is a list of strings
                    if isinstance(trigger, str) and re.search(r'\b' + re.escape(trigger) + r'\b', message.content, re.IGNORECASE):
                        is_triggered = True
                        args = message.content # For keywords, the whole message is the argument
                        break

            if is_triggered:
                logger.info(f"Plugin '{plugin.get('name')}' triggered by message {message.id}.")
                result = await self._execute_plugin(plugin, message, args, bot_config)
                
                if result is True:
                    return True
                
                if isinstance(result, tuple) and result[0] == 'append':
                    triggered_appends.append(result[1])
        
        if triggered_appends:
            return 'append', triggered_appends
        
        return None

    async def _execute_plugin(self, plugin: Dict[str, Any], message: discord.Message, args: str, bot_config: Dict[str, Any]):
        action_type = plugin.get('action_type', 'http_request')
        
        if action_type == 'http_request':
            result_str = await _execute_http_request(plugin, message, args)
            if result_str:
                await message.reply(result_str[:2000], mention_author=False)
            return True

        elif action_type == 'llm_augmented_tool':
            api_result = await _execute_http_request(plugin, message, args)
            if not api_result or api_result.startswith("Error:"):
                await message.reply(api_result or "Tool execution failed.", mention_author=False)
                return True

            prompt_template = plugin.get('llm_prompt_template')
            final_prompt = _format_with_placeholders(prompt_template, message, args)
            final_prompt = final_prompt.replace("{api_result}", api_result)
            
            llm_messages = [{"role": "system", "content": "You are a tool-using assistant."}, {"role": "user", "content": final_prompt}]
            
            injection_mode = plugin.get('injection_mode', 'override')
            
            if injection_mode == 'override':
                sim_config = bot_config.copy()
                sim_config["stream_response"] = False
                full_response = ""
                async for _, content in self.llm_caller(sim_config, llm_messages):
                    full_response = content
                if full_response:
                    await message.reply(full_response[:2000], mention_author=False)
                return True
            
            elif injection_mode == 'append':
                formatted_result = f"Tool '{plugin.get('name')}' was used with input '{args}'. It returned the following data:\n{api_result}"
                return 'append', formatted_result

        return True
