from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="core_llm_bot",
    description="Core LLM chatbot pipeline as a NoneBot plugin",
    usage="Handles message triggers, context assembly, LLM pipeline, and streaming responses",
)

from .matchers import register_main_matcher as _register_main_matcher
_register_main_matcher()
