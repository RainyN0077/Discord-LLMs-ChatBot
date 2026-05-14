from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="configurable_tools",
    description="User-configurable HTTP and LLM-augmented tool plugins",
    usage="Configured via the bot config JSON; automatically provides tools to the LLM",
)
