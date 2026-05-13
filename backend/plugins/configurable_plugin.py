# backend/plugins/configurable_plugin.py
import logging
import re
from typing import Dict, Any, Optional, Tuple, List

import discord
from app.utils import _execute_http_request, _format_with_placeholders
from .base import BasePlugin

logger = logging.getLogger(__name__)

class ConfigurablePlugin(BasePlugin):
    """
    一个通用的、可配置的插件实现，它继承自BasePlugin。
    这个类处理那些在config.json中定义、没有专门Python代码的插件。
    它封装了检查触发器（命令、关键字）和执行动作（HTTP请求）的逻辑。
    """
    
    async def handle_message(self, message: discord.Message, bot_config: Dict[str, Any]) -> Optional[Tuple[str, List[str]] | bool]:
        """
        检查此可配置插件是否被消息触发，如果是，则执行其动作。
        """
        is_triggered, args = self._check_trigger(message)

        if is_triggered:
            logger.info(f"ConfigurablePlugin '{self.name}' triggered.")
            return await self._execute_action(message, args, bot_config)
        
        return None

    def _check_trigger(self, message: discord.Message) -> Tuple[bool, str]:
        """根据插件配置检查触发条件。"""
        trigger_type = self.plugin_config.get('trigger_type', 'command')
        triggers = self.plugin_config.get('triggers', [])
        
        if trigger_type == 'command':
            for trigger in triggers:
                if message.content.startswith(trigger):
                    return True, message.content[len(trigger):].strip()
        elif trigger_type == 'keyword':
            for trigger in triggers:
                if isinstance(trigger, str) and re.search(r'\b' + re.escape(trigger) + r'\b', message.content, re.IGNORECASE):
                    return True, message.content
        return False, ""

    async def _execute_action(self, message: discord.Message, args: str, bot_config: Dict[str, Any]):
        """执行插件配置中定义的动作。"""
        action_type = self.plugin_config.get('action_type', 'http_request')
        
        if action_type == 'http_request':
            result_str = await _execute_http_request(self.plugin_config, message, args)
            if result_str:
                await message.reply(result_str[:2000], mention_author=False)
            return True # 'override' a.k.a. stop processing

        elif action_type == 'llm_augmented_tool':
            api_result = await _execute_http_request(self.plugin_config, message, args)
            if not api_result or api_result.startswith("Error:"):
                await message.reply(api_result or "Tool execution failed.", mention_author=False)
                return True

            prompt_template = self.plugin_config.get('llm_prompt_template')
            final_prompt = _format_with_placeholders(prompt_template, message, args)
            final_prompt = final_prompt.replace("{api_result}", api_result)
            
            llm_messages = [{"role": "system", "content": "You are a tool-using assistant."}, {"role": "user", "content": final_prompt}]
            
            injection_mode = self.plugin_config.get('injection_mode', 'override')
            
            if injection_mode == 'override':
                if not self.llm_caller:
                    logger.error(f"Plugin '{self.name}' needs an LLM caller for 'override' mode, but none was provided.")
                    return True

                sim_config = bot_config.copy()
                sim_config["stream_response"] = False
                # Note: llm_caller is expected to be a compatible async generator function
                full_response = ""
                response_generator = self.llm_caller(sim_config, llm_messages)
                async for response_type, content in response_generator:
                    if response_type == "final":
                         full_response = content

                if full_response:
                    await message.reply(full_response[:2000], mention_author=False)
                return True
            
            elif injection_mode == 'append':
                formatted_result = f"Tool '{self.name}' was used with input '{args}'. It returned the following data:\n{api_result}"
                return 'append', [formatted_result]

        return True # Default to override to maintain old behavior