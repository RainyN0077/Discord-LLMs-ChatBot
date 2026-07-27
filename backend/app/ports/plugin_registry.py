"""集中式插件注册表 — 统一管理插件的发现、注册和生命周期.

替代旧 PluginManager (已删除的 plugins/manager.py) 中的 _load_plugins 逻辑。
"""

import asyncio
import functools
import importlib
import inspect
import logging
import pkgutil
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from app.ports.plugin_base import PluginBase

logger = logging.getLogger(__name__)


class PluginRegistry:
    """集中式插件注册表.

    替代旧 PluginManager (已删除的 plugins/manager.py) 中的 _load_plugins 逻辑。
    """

    def __init__(self) -> None:
        """初始化插件注册表."""
        self._plugins: Dict[str, "PluginBase"] = {}
        self._search_paths: List[str] = ["plugins"]
        self._loaded_modules: Set[str] = set()
        self._lock = asyncio.Lock()

    def register(self, name: str, plugin: "PluginBase") -> None:
        """注册一个插件实例.

        Args:
            name: 插件名称
            plugin: 插件实例
        """
        self._plugins[name] = plugin
        logger.info("Plugin '%s' registered", name)

    def unregister(self, name: str) -> None:
        """注销一个插件.

        Args:
            name: 插件名称
        """
        self._plugins.pop(name, None)
        self._loaded_modules.discard(name)

    def get_all_snapshot(self) -> List["PluginBase"]:
        """获取所有插件实例的快照（用于安全遍历）.

        Returns:
            插件实例列表副本
        """
        return list(self._plugins.values())

    def get(self, name: str) -> Optional["PluginBase"]:
        """获取已注册的插件实例.

        Args:
            name: 插件名称

        Returns:
            插件实例，未找到时返回 None
        """
        return self._plugins.get(name)

    def get_all(self) -> List["PluginBase"]:
        """获取所有已注册的插件实例.

        Returns:
            插件实例列表
        """
        return list(self._plugins.values())

    async def process_message(
        self,
        message: Any,
        bot_config: Dict[str, Any],
    ) -> Optional[Union[bool, Tuple[str, List]]]:
        """处理消息 — 与 PluginManager.process_message() 语义兼容.

        遍历所有已注册插件，依次调用 handle_message()。
        支持 override (return True) 和 append (return ('append', [...])) 模式。

        Args:
            message: 消息对象 (MessageContext 或 discord.Message)
            bot_config: Bot 配置字典

        Returns:
            - ('append', list): 注入模式
            - True: 覆盖模式
            - None: 无命中
        """
        triggered_appends = []

        # 使用快照避免迭代时字典被修改
        for plugin in self.get_all_snapshot():
            if not getattr(plugin, 'enabled', True):
                continue

            try:
                result = await plugin.handle_message(message, bot_config)
                if result:
                    if result is True:
                        logger.info("Plugin '%s' triggered in override mode.", plugin.name)
                        return True

                    if isinstance(result, tuple) and result[0] == 'append':
                        data = result[1]
                        if not isinstance(data, list):
                            data = [data]
                        logger.info("Plugin '%s' triggered in append mode.", plugin.name)
                        triggered_appends.extend(data)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Error in plugin '%s': %s", plugin.name, e, exc_info=True)

        if triggered_appends:
            return 'append', triggered_appends

        return None

    def discover_and_load(
        self,
        plugins_config: Dict[str, Any],
        llm_caller: callable,
    ) -> None:
        """自动发现并加载插件.

        扫描 plugins/ 目录，自动加载所有 PluginBase 子类。
        未通过自动发现的插件会尝试从配置中实例化 ConfigurablePlugin。

        Args:
            plugins_config: 插件配置字典
            llm_caller: LLM 调用函数
        """
        try:
            import plugins  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("plugins/ package not found, skipping plugin discovery")
            return

        for _, name, _ in pkgutil.iter_modules(plugins.__path__):
            if name in self._loaded_modules or name in [
                "manager",
                "base",
            ]:
                continue
            try:
                module = importlib.import_module(f"plugins.{name}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        inspect.isclass(attr)
                        and issubclass(attr, PluginBase)
                        and attr is not PluginBase
                    ):
                        plugin_cfg = plugins_config.get(name, {})
                        # 强制启用 memory_plugin（与 PluginManager 行为一致）
                        is_memory_plugin = name == "memory_plugin"
                        if plugin_cfg.get("enabled", False) or is_memory_plugin:
                            instance = attr(plugin_cfg, llm_caller)
                            self.register(name, instance)
                            self._loaded_modules.add(name)
            except Exception as e:
                logger.error(
                    "Failed to load plugin module %s: %s", name, e, exc_info=True
                )

        try:
            from plugins.configurable_plugin import ConfigurablePlugin
        except ImportError:
            ConfigurablePlugin = None

        if ConfigurablePlugin is None:
            logger.warning("ConfigurablePlugin not available, skipping config plugins")
            return

        for name, cfg in plugins_config.items():
            if name in self._loaded_modules:
                continue
            if cfg.get("enabled", False):
                try:
                    instance = ConfigurablePlugin(cfg, llm_caller)
                    self.register(name, instance)
                except Exception as e:
                    logger.error(
                        "Failed to load config plugin %s: %s", name, e
                    )

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有已注册插件的工具定义.

        Returns:
            工具定义列表（OpenAI function calling 格式）
        """
        tools: List[Dict[str, Any]] = []
        for plugin in self._plugins.values():
            tools.extend(plugin.get_tools())
        return tools

    def get_all_tool_functions(
        self,
        message: Any,
        config: Dict[str, Any],
    ) -> Dict[str, callable]:
        """获取所有已注册插件的工具函数映射.

        对 MemoryPlugin 特殊处理：使用 functools.partial 注入消息上下文。

        Args:
            message: 消息对象
            config: Bot 配置

        Returns:
            工具名称到可调用函数的映射
        """
        functions: Dict[str, callable] = {}
        for plugin in self._plugins.values():
            plugin_funcs = plugin.get_tool_functions()

            # MemoryPlugin 上下文注入（与 PluginManager 行为一致）
            if plugin.name == "memory_plugin":
                author = getattr(message, 'author', None)
                user_id = str(getattr(author, 'id', '')) if author else ''
                user_name = getattr(author, 'name', '') if author else ''

                if 'add_to_memory' in plugin_funcs:
                    original = plugin_funcs['add_to_memory']
                    plugin_funcs['add_to_memory'] = functools.partial(
                        original,
                        message=message,
                        config=config,
                        user_id=user_id,
                        user_name=user_name,
                    )
                if 'add_to_world_book' in plugin_funcs:
                    original = plugin_funcs['add_to_world_book']
                    plugin_funcs['add_to_world_book'] = functools.partial(
                        original,
                        message=message,
                        config=config,
                        user_id=user_id,
                        user_name=user_name,
                    )

            functions.update(plugin_funcs)
        return functions
