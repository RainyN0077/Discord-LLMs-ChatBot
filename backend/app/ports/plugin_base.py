"""统一插件抽象基类 — 平台无关.

使用 PlatformMessage 替代旧 BasePlugin 的 Any 类型。
旧 BasePlugin (已删除的 plugins/base.py) 通过 NBPluginAdapter 包装适配。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from .platform_message import PlatformMessage


class PluginBase(ABC):
    """统一插件抽象基类 — 平台无关.

    替代旧 BasePlugin (已删除的 plugins/base.py)，使用 PlatformMessage。
    旧 BasePlugin 通过 NBPluginAdapter 包装适配。
    """

    def __init__(
        self,
        plugin_config: Dict[str, Any],
        llm_caller: Optional[callable] = None,
    ) -> None:
        self.plugin_config = plugin_config
        self.llm_caller = llm_caller
        self.name = plugin_config.get('name', self.__class__.__name__)

    @abstractmethod
    async def handle_message(
        self,
        message: PlatformMessage,
        bot_config: Dict[str, Any],
    ) -> Optional[Tuple[str, List[str]] | bool]:
        """处理平台无关消息.

        Args:
            message: 平台无关消息对象
            bot_config: Bot 配置字典

        Returns:
            - ('append', list_of_strings): 注入数据到上下文
            - True: 消费消息，停止后续处理
            - None: 未触发
        """
        ...

    def get_tools(self) -> List[Dict[str, Any]]:
        """获取插件提供的工具定义.

        Returns:
            工具定义列表（OpenAI function calling 格式）
        """
        return []

    def get_tool_functions(self) -> Dict[str, callable]:
        """获取插件提供的工具函数映射.

        Returns:
            工具名称到可调用函数的映射
        """
        return {}
