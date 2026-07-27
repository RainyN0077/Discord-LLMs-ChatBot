"""集中式插件注册表 — 统一管理插件的发现、注册和生命周期.

替代 plugins/manager.py 中的 _load_plugins 逻辑。
"""

import importlib
import inspect
import logging
import pkgutil
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from plugins.base import BasePlugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """集中式插件注册表.

    替代 plugins/manager.py 中的 _load_plugins 逻辑。
    """

    def __init__(self) -> None:
        """初始化插件注册表."""
        self._plugins: Dict[str, "BasePlugin"] = {}
        self._search_paths: List[str] = ["plugins"]
        self._loaded_modules: Set[str] = set()

    def register(self, name: str, plugin: "BasePlugin") -> None:
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

    def get(self, name: str) -> Optional["BasePlugin"]:
        """获取已注册的插件实例.

        Args:
            name: 插件名称

        Returns:
            插件实例，未找到时返回 None
        """
        return self._plugins.get(name)

    def get_all(self) -> List["BasePlugin"]:
        """获取所有已注册的插件实例.

        Returns:
            插件实例列表
        """
        return list(self._plugins.values())

    def discover_and_load(
        self,
        plugins_config: Dict[str, Any],
        llm_caller: callable,
    ) -> None:
        """自动发现并加载插件.

        扫描 plugins/ 目录，自动加载所有 BasePlugin 子类。
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
                "configurable_plugin",
            ]:
                continue
            try:
                module = importlib.import_module(f"plugins.{name}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        inspect.isclass(attr)
                        and issubclass(attr, plugins.base.BasePlugin)
                        and attr is not plugins.base.BasePlugin
                    ):
                        plugin_cfg = plugins_config.get(name, {})
                        if plugin_cfg.get("enabled", False):
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

        Args:
            message: 消息对象
            config: Bot 配置

        Returns:
            工具名称到可调用函数的映射
        """
        functions: Dict[str, callable] = {}
        for plugin in self._plugins.values():
            functions.update(plugin.get_tool_functions())
        return functions
