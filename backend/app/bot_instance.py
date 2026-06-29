import asyncio
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pathlib import Path

from .config_cache import load_config, get_bot_config_path, get_bot_knowledge_path, get_bot_usage_path, DEFAULT_CONFIG, BOTS_DIR

logger = logging.getLogger(__name__)


class BotInstance:
    def __init__(self, bot_id: str):
        self.bot_id = bot_id
        self.config: Dict[str, Any] = {}
        self.platform: str = "discord"
        self.status: str = "stopped"
        self._task: Optional[asyncio.Task] = None
        self._client: Any = None
        self.memory_cutoffs: Dict[int, datetime] = {}
        self.auto_message_counts: Dict[int, int] = {}
        self.started_at: Optional[datetime] = None
        self._usage_tracker = None
        self._knowledge_manager = None
        self._plugin_manager = None
        self._usage_manager = None
        self._bot_process_lock = None

    @property
    def provider_mode(self) -> str:
        """Return the provider mode: 'nonebot' (legacy) or 'astrbot'."""
        return self.config.get("provider_mode", "nonebot")

    @property
    def config_dir(self) -> Path:
        return BOTS_DIR / self.bot_id

    @property
    def config_path(self) -> Path:
        return get_bot_config_path(self.bot_id)

    @property
    def knowledge_path(self) -> Path:
        return get_bot_knowledge_path(self.bot_id)

    @property
    def usage_path(self) -> Path:
        return get_bot_usage_path(self.bot_id)

    def load_config(self) -> Dict[str, Any]:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if self.config_path.exists():
            import json
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            from .config_cache import _set_defaults_recursive
            _set_defaults_recursive(DEFAULT_CONFIG, data)
            if not data.get("api_secret_key"):
                data["api_secret_key"] = secrets.token_hex(32)
                logger.warning("api_secret_key was empty in per-bot config, generated a new one")
        else:
            from copy import deepcopy
            data = deepcopy(DEFAULT_CONFIG)
            data["bot_id"] = self.bot_id
            with open(self.config_path, "w", encoding="utf-8") as f:
                import json
                json.dump(data, f, indent=2, ensure_ascii=False)
        self.config = data
        self.config["bot_id"] = self.bot_id
        self.platform = data.get("platform", "discord")
        return self.config

    def save_config(self, config_dict: Dict[str, Any]) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        import json
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
        self.config = config_dict

    def is_running(self) -> bool:
        return self.status == "running"

    def generate_env_config(self) -> Dict[str, Any]:
        platform = self.config.get("platform", "discord")
        if platform == "discord":
            token = self.config.get("discord_token", "")
            if not token:
                return {}
            default_intents = {
                "guilds": True,
                "guild_messages": True,
                "direct_messages": True,
                "message_content": True,
                "members": True,
            }
            user_intents = self.config.get("discord_intents", {})
            intents = {**default_intents, **user_intents}
            intents = {k: bool(v) for k, v in intents.items()}
            return {
                "token": token,
                "intent": intents,
            }
        elif platform == "qq":
            token = self.config.get("qq_token") or self.config.get("discord_token", "")
            if not token:
                return {}
            return {"token": token}
        return {}

    async def start(self) -> None:
        if self.is_running():
            logger.warning(f"Bot '{self.bot_id}' is already running.")
            return
        self.load_config()
        if not self.config.get("enabled", True):
            logger.info(f"Bot '{self.bot_id}' is disabled. Skipping start.")
            return
        self.status = "starting"
        self.started_at = datetime.now(timezone.utc)

        from .usage_tracker import UsageTracker
        from .core_logic.knowledge_manager import KnowledgeManager
        from plugins.manager import PluginManager

        self._usage_tracker = UsageTracker(data_file=str(self.usage_path))
        self._knowledge_manager = KnowledgeManager(db_path=str(self.knowledge_path))

        def _get_llm_response(messages_or_config, extra_messages=None, images=None):
            async def _inner():
                from .llm_providers.factory import get_llm_provider
                llm_provider = get_llm_provider(self.config)
                full_response = ""
                if isinstance(messages_or_config, dict) and extra_messages is not None:
                    messages = extra_messages
                else:
                    messages = messages_or_config
                async for response_type, data in llm_provider.get_response_stream(messages, images, tools=[], tool_functions={}):
                    if response_type == "final":
                        full_response = data
                        break
                return full_response
            return _inner()

        self._plugin_manager = PluginManager(self.config.get("plugins", {}), _get_llm_response)

        if self.provider_mode == "astrbot":
            await self._start_astrbot()
        else:
            await self._start_nonebot()

        self.status = "running"
        logger.info(f"Bot '{self.bot_id}' started (mode={self.provider_mode}).")

    async def _start_nonebot(self) -> None:
        """Start the bot via the legacy NoneBot2 adapter."""
        from nb_plugins.core_llm_bot.matchers import register_bot_instance
        register_bot_instance(self.bot_id, self)

    async def _start_astrbot(self) -> None:
        """Start the bot via AstrBot subprocess."""
        from .state import astrbot_process_manager
        from .astrbot_manager import AstrBotProcessError

        if astrbot_process_manager is None:
            raise RuntimeError("AstrBotProcessManager not initialized in state.")

        try:
            await astrbot_process_manager.start(self.bot_id, self.config)
            logger.info(f"Bot '{self.bot_id}' AstrBot process started.")
        except AstrBotProcessError as e:
            self.status = "error"
            logger.error(f"Failed to start AstrBot process for '{self.bot_id}': {e}")
            raise

    async def stop(self) -> None:
        if not self.is_running():
            return
        self.status = "stopped"
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        self._client = None
        self.started_at = None
        if self._usage_tracker:
            await self._usage_tracker.close()
        self._usage_tracker = None
        self._knowledge_manager = None
        self._plugin_manager = None
        self._usage_manager = None

        if self.provider_mode == "astrbot":
            await self._stop_astrbot()
        else:
            await self._stop_nonebot()

        logger.info(f"Bot '{self.bot_id}' stopped.")

    async def _stop_nonebot(self) -> None:
        """Unregister from NoneBot2 adapter."""
        from nb_plugins.core_llm_bot.matchers import unregister_bot_instance
        unregister_bot_instance(self.bot_id)

    async def _stop_astrbot(self) -> None:
        """Stop the AstrBot subprocess."""
        from .state import astrbot_process_manager
        if astrbot_process_manager:
            await astrbot_process_manager.stop(self.bot_id)

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    def to_status_dict(self) -> Dict[str, Any]:
        uptime = None
        if self.started_at and self.is_running():
            uptime = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return {
            "bot_id": self.bot_id,
            "bot_name": self.config.get("bot_name", "Unnamed Bot"),
            "platform": self.platform,
            "enabled": self.config.get("enabled", True),
            "status": self.status,
            "uptime_seconds": uptime,
            "bot_nickname": self.config.get("bot_nickname", ""),
            "model_name": self.config.get("model_name", ""),
            "llm_provider": self.config.get("llm_provider", "openai"),
            "trigger_keywords": self.config.get("trigger_keywords", []),
            "provider_mode": self.provider_mode,
        }
