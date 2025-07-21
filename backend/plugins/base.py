# backend/plugins/base.py
from abc import ABC, abstractmethod
from typing import Optional, Tuple, List, Dict, Any

import discord

class BasePlugin(ABC):
    """
    所有插件的抽象基类。
    它定义了所有插件必须实现的统一接口。
    """

    def __init__(self, plugin_config: Dict[str, Any], llm_caller: callable = None):
        """
        初始化插件。
        :param plugin_config: 来自 config.json 的该插件的配置字典。
        :param llm_caller: 一个可调用对象，用于在需要时调用LLM。
        """
        self.plugin_config = plugin_config
        self.llm_caller = llm_caller
        self.name = plugin_config.get('name', self.__class__.__name__)

    @abstractmethod
    async def handle_message(self, message: discord.Message, bot_config: Dict[str, Any]) -> Optional[Tuple[str, List[str]] | bool]:
        """
        处理传入的Discord消息。
        这是插件的主要入口点。插件应该在此方法中实现其触发逻辑和核心功能。

        :param message: The discord.Message object to process.
        :param bot_config: The main bot configuration.
        :return:
            - ('append', list_of_strings): If the plugin wishes to inject data into the context.
            - True: If the plugin has handled the message and wants to stop further processing (override).
            - None: If the plugin is not triggered or has no action.
        """
        pass

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        如果插件提供可供LLM使用的工具，则重写此方法。
        :return: A list of tool definitions in the format expected by the LLM provider.
        """
        return []

    def get_tool_functions(self) -> Dict[str, callable]:
        """
        如果插件提供工具，则重写此方法以返回工具名称到其实现函数的映射。
        :return: A dictionary mapping tool function names to their callable implementations.
        """
        return {}