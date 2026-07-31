import asyncio
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pathlib import Path

from enum import Enum

from .config_cache import load_config, get_bot_config_path, get_bot_knowledge_path, get_bot_usage_path, DEFAULT_CONFIG, BOTS_DIR

logger = logging.getLogger(__name__)


class BotStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


class BotInstance:
    def __init__(self, bot_id: str):
        self.bot_id = bot_id
        self.config: Dict[str, Any] = {}
        self.platform: str = "discord"
        self.status: BotStatus = BotStatus.STOPPED
        self._status_lock = asyncio.Lock()
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
        self._runtime = None

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
        from .security.secrets_manager import SecretsManager
        sm = SecretsManager()
        if self.config_path.exists():
            import json
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data = sm.decrypt_dict(data)
            from .config_cache import _set_defaults_recursive
            _set_defaults_recursive(DEFAULT_CONFIG, data)
            if not data.get("api_secret_key"):
                data["api_secret_key"] = secrets.token_hex(32)
                logger.warning("api_secret_key was empty in per-bot config, generated a new one")
        else:
            from copy import deepcopy
            data = deepcopy(DEFAULT_CONFIG)
            data["bot_id"] = self.bot_id
            encrypted = sm.encrypt_dict(data)
            with open(self.config_path, "w", encoding="utf-8") as f:
                import json
                json.dump(encrypted, f, indent=2, ensure_ascii=False)
        self.config = data
        self.config["bot_id"] = self.bot_id
        self.platform = data.get("platform", "discord")
        return self.config

    def save_config(self, config_dict: Dict[str, Any]) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        import json
        from .security.secrets_manager import SecretsManager
        encrypted = SecretsManager().encrypt_dict(config_dict)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(encrypted, f, indent=2, ensure_ascii=False)
        self.config = config_dict

    def is_running(self) -> bool:
        return self.status == BotStatus.RUNNING

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
        async with self._status_lock:
            if self.status != BotStatus.STOPPED:
                logger.warning(
                    f"Bot '{self.bot_id}' cannot start: status={self.status.value}."
                )
                return
            self.status = BotStatus.STARTING
        self.started_at = datetime.now(timezone.utc)

        self.load_config()
        if not self.config.get("enabled", True):
            logger.info(f"Bot '{self.bot_id}' is disabled. Skipping start.")
            async with self._status_lock:
                self.status = BotStatus.STOPPED
            self.started_at = None
            return

        from .usage_tracker import UsageTracker
        from .core_logic.knowledge_manager import KnowledgeManager
        from .app_context import AppContext

        _ctx = AppContext.get()
        self._usage_tracker = UsageTracker(
            data_file=str(self.usage_path),
            quota_alert_manager=getattr(_ctx, 'quota_alert_manager', None),
        )
        await self._usage_tracker.initialize()
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

        from .ports.plugin_registry import PluginRegistry
        self._plugin_manager = PluginRegistry()
        self._plugin_manager.discover_and_load(
            self.config.get("plugins", {}),
            _get_llm_response,
        )
        logger.info("Bot '%s' using PluginRegistry (enhanced)", self.bot_id)

        from .adapters.factory import create_bot_runtime
        try:
            self._runtime = create_bot_runtime(self.bot_id, self.config)
            logger.info("BotRuntime created for bot '%s' (type=%s)", self.bot_id, self.config.get("runtime_type", "nonebot"))
        except Exception as e:
            logger.warning("Failed to create BotRuntime for '%s': %s", self.bot_id, e)

        try:
            await self._start_nonebot()
            # 启动 BotRuntime（如果创建了），连接平台并启动重连
            if self._runtime is not None:
                await self._runtime.start()
        except Exception:
            async with self._status_lock:
                self.status = BotStatus.STOPPED
            self.started_at = None
            if self._usage_tracker:
                await self._usage_tracker.close()
            self._usage_tracker = None
            self._knowledge_manager = None
            self._plugin_manager = None
            self._usage_manager = None
            logger.error(f"Bot '{self.bot_id}' failed to start.")
            raise

        async with self._status_lock:
            self.status = BotStatus.RUNNING
        logger.info(f"Bot '{self.bot_id}' started.")

    async def _start_nonebot(self) -> None:
        """Start the bot via the legacy NoneBot2 adapter."""
        from nb_plugins.core_llm_bot.matchers import register_bot_instance

        try:
            register_bot_instance(self.bot_id, self)
            logger.info("Bot '%s' registered with NoneBot adapter", self.bot_id)
        except Exception as e:
            logger.error("Failed to register bot '%s' with NoneBot adapter: %s", self.bot_id, e)
            raise

        # 重连由 BotRuntime（NoneBotRuntime）管理
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None

    async def _nonebot_reconnect_loop(self) -> None:
        """Background task: monitor NoneBot adapter health and reconnect on failure.

        Catches unhandled exceptions from the NoneBot adapter context and
        triggers exponential-backoff reconnection when the bot is in RUNNING
        status.  After ``MAX_RECONNECT_ATTEMPTS`` consecutive failures the bot
        is marked as ``STOPPED``.
        """
        MAX_RECONNECT_ATTEMPTS = 10
        attempt = 0

        try:
            while self.status == BotStatus.RUNNING and attempt < MAX_RECONNECT_ATTEMPTS:
                try:
                    # Keep the task alive; real NoneBot adapter exceptions may
                    # surface as CancelledError or generic Exception here.
                    await asyncio.sleep(5)
                except asyncio.CancelledError:
                    logger.info("Bot '%s' NoneBot reconnect loop cancelled", self.bot_id)
                    break
                except Exception as exc:
                    attempt += 1
                    logger.error(
                        "Bot '%s' NoneBot adapter error (%d/%d): %s",
                        self.bot_id, attempt, MAX_RECONNECT_ATTEMPTS, exc,
                    )
                    if self.status == BotStatus.RUNNING:
                        await self._reconnect_nonebot(attempt)
                    continue

            if attempt >= MAX_RECONNECT_ATTEMPTS and self.status == BotStatus.RUNNING:
                logger.error(
                    "Bot '%s' exceeded max NoneBot reconnect attempts (%d). Marking as error.",
                    self.bot_id, MAX_RECONNECT_ATTEMPTS,
                )
                async with self._status_lock:
                    self.status = BotStatus.STOPPED
        except asyncio.CancelledError:
            logger.info("Bot '%s' NoneBot reconnect loop cancelled (outer)", self.bot_id)

    async def _reconnect_nonebot(self, attempt: int) -> None:
        """Reconnect NoneBot adapter with exponential backoff.

        Backoff sequence: 1s, 2s, 4s, 8s, ... capped at 60s.
        Only proceeds when ``status == RUNNING``.
        """
        if self.status != BotStatus.RUNNING:
            logger.info(
                "Bot '%s' skip reconnect (status=%s)", self.bot_id, self.status.value,
            )
            return

        base_delay = 1.0
        max_delay = 60.0
        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)

        logger.warning(
            "Bot '%s' NoneBot disconnected. Reconnecting in %.1fs (attempt %d) ...",
            self.bot_id, delay, attempt,
        )
        await asyncio.sleep(delay)

        if self.status != BotStatus.RUNNING:
            logger.info(
                "Bot '%s' abort reconnect (status changed to %s during backoff)",
                self.bot_id, self.status.value,
            )
            return

        try:
            from nb_plugins.core_llm_bot.matchers import (
                register_bot_instance,
                unregister_bot_instance,
            )
            unregister_bot_instance(self.bot_id)
            register_bot_instance(self.bot_id, self)
            logger.info(
                "Bot '%s' re-registered with NoneBot adapter (attempt %d)",
                self.bot_id, attempt,
            )
        except Exception as e:
            logger.error("Bot '%s' reconnect (re-register) failed: %s", self.bot_id, e)
            raise

    async def stop(self) -> None:
        async with self._status_lock:
            if self.status != BotStatus.RUNNING:
                return
            self.status = BotStatus.STOPPING

        try:
            await self._stop_nonebot()
        except Exception:
            logger.exception(f"Error during provider stop for bot '{self.bot_id}'")

        # 停止 BotRuntime（如果创建了）
        if self._runtime is not None:
            try:
                await self._runtime.stop()
            except Exception:
                logger.exception(f"Error stopping runtime for bot '{self.bot_id}'")

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

        async with self._status_lock:
            self.status = BotStatus.STOPPED
        logger.info(f"Bot '{self.bot_id}' stopped.")

    async def _stop_nonebot(self) -> None:
        """Unregister from NoneBot2 adapter."""
        from nb_plugins.core_llm_bot.matchers import unregister_bot_instance
        unregister_bot_instance(self.bot_id)

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
        }
