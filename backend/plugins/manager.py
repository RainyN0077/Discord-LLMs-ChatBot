# backend/plugins/manager.py
import inspect
import logging
import importlib
import pkgutil
import functools
from typing import List, Dict, Any, Optional, Tuple

import discord

from .base import BasePlugin
from .configurable_plugin import ConfigurablePlugin
from .memory_plugin import MemoryPlugin

logger = logging.getLogger(__name__)

class PluginManager:
    def __init__(self, plugins_config: Dict[str, Any], llm_caller: callable):
        self.llm_caller = llm_caller
        self.plugins_config = plugins_config
        self.plugins: List[BasePlugin] = []
        self._load_plugins()

    def _load_plugins(self):
        """
        Dynamically loads all plugins.
        This includes both Python-based plugins and config-based plugins.
        """
        logger.info("--- Loading Plugins ---")
        
        # 1. Load Python-based plugins from the 'plugins' directory
        loaded_module_plugins = set()
        import plugins
        for _, name, _ in pkgutil.iter_modules(plugins.__path__):
            if name in ["manager", "base", "configurable_plugin"]:
                continue
            try:
                module = importlib.import_module(f"plugins.{name}")
                for attribute_name in dir(module):
                    attribute = getattr(module, attribute_name)
                    if inspect.isclass(attribute) and issubclass(attribute, BasePlugin) and attribute is not BasePlugin:
                        plugin_config = self.plugins_config.get(name, {})
                        # Per user request, force-enable memory_plugin to bypass config/volume issues.
                        is_memory_plugin = name == "memory_plugin"
                        if plugin_config.get("enabled", False) or is_memory_plugin:
                            self.plugins.append(attribute(plugin_config, self.llm_caller))
                            logger.info(f"Successfully loaded Python-based plugin: {attribute.__name__} from module {name}")
                            loaded_module_plugins.add(name)
                        else:
                            logger.info(f"Skipping disabled Python-based plugin: {name}")

            except Exception as e:
                logger.error(f"Failed to load plugin module {name}: {e}", exc_info=True)

        # 2. Load config-based (dynamic) plugins
        for name, config in self.plugins_config.items():
            if name in loaded_module_plugins:
                continue # Already loaded as a Python-based plugin
            
            if config.get("enabled", False):
                try:
                    self.plugins.append(ConfigurablePlugin(config, self.llm_caller))
                    logger.info(f"Successfully loaded config-based plugin: {name}")
                except Exception as e:
                    logger.error(f"Failed to load config-based plugin {name}: {e}", exc_info=True)
        logger.info("--- Plugin Loading Complete ---")


    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Collects tools from all loaded plugins."""
        all_tools = []
        for plugin in self.plugins:
            all_tools.extend(plugin.get_tools())
        return all_tools
    
    def get_all_tool_functions(self, message: discord.Message, config: Dict[str, Any]) -> Dict[str, callable]:
        """Collects tool functions from all loaded plugins."""
        all_functions = {}
        for plugin in self.plugins:
            functions = plugin.get_tool_functions()
            # For MemoryPlugin, pre-fill context for its specific tools
            if isinstance(plugin, MemoryPlugin):
                # Wrap add_to_memory to inject user info
                if 'add_to_memory' in functions:
                    original_func = functions['add_to_memory']
                    functions['add_to_memory'] = functools.partial(
                        original_func,
                        user_id=str(message.author.id),
                        user_name=message.author.name
                    )
                # Wrap add_to_world_book to inject the full message object and config for context
                if 'add_to_world_book' in functions:
                    original_func = functions['add_to_world_book']
                    functions['add_to_world_book'] = functools.partial(
                        original_func,
                        message=message,
                        config=config
                    )
            all_functions.update(functions)
        return all_functions

    async def process_message(self, message: discord.Message, bot_config: Dict[str, Any]) -> Optional[Tuple[str, List[str]] | bool]:
        """
        Processes a message by passing it to all loaded plugins.
        Handles different return types ('append', 'override') from plugins.
        """
        triggered_appends = []

        for plugin in self.plugins:
            if not getattr(plugin, 'enabled', True):
                continue

            try:
                result = await plugin.handle_message(message, bot_config)
                if result:
                    if result is True:
                        logger.info(f"Plugin '{plugin.name}' triggered in override mode. Halting further processing.")
                        return True  # Override and stop processing
                    
                    if isinstance(result, tuple) and result[0] == 'append':
                        data_to_append = result[1]
                        if not isinstance(data_to_append, list):
                             data_to_append = [data_to_append] # Ensure it's a list
                        
                        logger.info(f"Plugin '{plugin.name}' triggered in append mode.")
                        triggered_appends.extend(data_to_append)

            except Exception as e:
                logger.error(f"Error processing message with plugin '{plugin.name}': {e}", exc_info=True)
        
        if triggered_appends:
            return 'append', triggered_appends
        
        return None

