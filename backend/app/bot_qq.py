import asyncio
import logging
from typing import Any, Dict

from .platforms.qq.qq_adapter import QQAdapter
from .bot import handle_platform_message
from .utils import TokenCalculator
from .usage_tracker import usage_tracker
from .core_logic.usage_manager import UsageManager
from .core_logic.knowledge_manager import get_knowledge_manager
from .llm_providers.factory import get_llm_provider
from plugins.manager import PluginManager

logger = logging.getLogger(__name__)


async def run_qq_bot(config: Dict[str, Any]):
    qq_config = config.get("qq_bot", {})
    logger.info("Starting QQ bot...")

    adapter = QQAdapter(config)

    token_calculator = TokenCalculator()
    usage_manager = UsageManager(token_calculator)

    async def get_llm_response(messages, images=None):
        llm_provider = get_llm_provider(config)
        full_response = ""
        try:
            response_generator = llm_provider.get_response_stream(messages, images, tools=[], tool_functions={})
            async for response_type, data in response_generator:
                if response_type == "final":
                    full_response = data
                    break
        except Exception as e:
            logger.error("Error getting LLM response for QQ plugin: %s", e, exc_info=True)
            return f"LLM_PROVIDER_ERROR: {e}"
        return full_response

    plugin_manager = PluginManager(config.get("plugins", {}), get_llm_response)
    get_knowledge_manager()

    # Trackers for Discord are channel-id based; QQ uses string channel IDs
    auto_message_counts: Dict[int, int] = {}
    repeat_streaks: Dict[int, Dict[str, Any]] = {}

    async def handle_qq_message(plat_msg):
        fresh_config = config
        await handle_platform_message(
            plat_msg,
            fresh_config,
            plugin_manager,
            usage_manager,
            auto_message_counts,
            repeat_streaks,
            qq_adapter=adapter,
        )

    adapter.set_message_handler(handle_qq_message)

    try:
        await adapter.start()
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("QQ bot task cancelled.")
        raise
    except Exception:
        logger.error("QQ bot encountered an error", exc_info=True)
    finally:
        await adapter.stop()
