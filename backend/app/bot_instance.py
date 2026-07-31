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
            try:
                data = sm.decrypt_dict(data)
            except ValueError as e:
                # Sec LOW-3: 与 config_cache.load_config 对齐 —— 顶层明文/错误 key 时给出
                # 明确指引后继续抛出（bot_manager 已有兜底，跳过该 Bot 加载）
                logger.error(
                    "FATAL: per-bot config decryption failed for '%s': %s. "
                    "Set DISABLE_ENCRYPTION=1 to read plaintext configs for migration.",
                    self.bot_id,
                    e,
                )
                raise
            from .config_cache import _set_defaults_recursive
            _set_defaults_recursive(DEFAULT_CONFIG, data)
            if not data.get("api_secret_key"):
                data["api_secret_key"] = secrets.token_hex(32)
                logger.warning("api_secret_key was empty in per-bot config, generated a new one")
            # MEDIUM-5: 嵌套明文写回（正常模式 save_config 内部 encrypt_dict 幂等）
            if sm.last_migrated_paths:
                if sm.write_enabled:
                    self.save_config(data)
                else:
                    logger.info(
                        "Migration mode: nested plaintext fields %s left in place (no write-back)",
                        sm.last_migrated_paths,
                    )
        else:
            from copy import deepcopy
            data = deepcopy(DEFAULT_CONFIG)
            data["bot_id"] = self.bot_id
            if sm.write_enabled:
                encrypted = sm.encrypt_dict(data)
                with open(self.config_path, "w", encoding="utf-8") as f:
                    import json
                    json.dump(encrypted, f, indent=2, ensure_ascii=False)
            else:
                logger.warning(
                    "Migration mode: skipping write of new bot config for '%s'",
                    self.bot_id,
                )
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
                from .llm_providers.factory import get_provider_pool
                pool = get_provider_pool()
                full_response = ""
                if isinstance(messages_or_config, dict) and extra_messages is not None:
                    messages = extra_messages
                else:
                    messages = messages_or_config
                generator = await pool.execute(
                    self.config, messages, images=images, tools=[], tool_functions={}
                )
                async for response_type, data in generator:
                    if response_type == "final":
                        full_response = data
                        # MEDIUM-2: 显式关闭生成器，触发 pool 收敛重置（break 不再跳过收敛）
                        await generator.aclose()
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
