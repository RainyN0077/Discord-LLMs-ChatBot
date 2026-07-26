import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from .bot_instance import BotInstance
from .config_cache import (DEFAULT_BOT_ID, 
    DATA_DIR, BOTS_DIR, CONFIG_FILE, DEFAULT_CONFIG,
    get_bot_config_path, get_bot_dir, get_bot_knowledge_path, load_config, save_config,
)

logger = logging.getLogger(__name__)


class BotManager:
    def __init__(self):
        self._instances: Dict[str, BotInstance] = {}
        self._lock = asyncio.Lock()
        self._astrbot_manager = None  # Lazy-init on first astrbot-mode bot

    def _get_astrbot_manager(self):
        if self._astrbot_manager is None:
            from .app_context import AppContext
            from .astrbot_manager import AstrBotProcessManager
            self._astrbot_manager = AstrBotProcessManager()
            # Store in AppContext so bot_instance can access it
            AppContext.get().astrbot_process_manager = self._astrbot_manager
        return self._astrbot_manager

    def get(self, bot_id: str) -> Optional[BotInstance]:
        return self._instances.get(bot_id)

    def list(self) -> List[Dict[str, Any]]:
        return [inst.to_status_dict() for inst in self._instances.values()]

    def _get_all_bot_dirs(self) -> List[Path]:
        if not BOTS_DIR.exists():
            return []
        return sorted([d for d in BOTS_DIR.iterdir() if d.is_dir()])

    def _migrate_legacy_config(self) -> Optional[str]:
        """Migrate old data/config.json to a bot instance if no bots exist yet."""
        if not CONFIG_FILE.exists():
            return None
        existing_bots = self._get_all_bot_dirs()
        if existing_bots:
            return None
        try:
            old_config = load_config()
        except Exception as e:
            logger.error(f"Failed to load legacy config for migration: {e}")
            return None
        bot_id = old_config.get("bot_id") or DEFAULT_BOT_ID
        bot_dir = get_bot_dir(bot_id)
        bot_dir.mkdir(parents=True, exist_ok=True)
        old_config["bot_id"] = bot_id
        if not old_config.get("bot_name"):
            old_config["bot_name"] = "Default Bot"
        if not old_config.get("platform"):
            old_config["platform"] = "discord"
        if "enabled" not in old_config:
            old_config["enabled"] = True
        bot_config_path = get_bot_config_path(bot_id)
        with open(bot_config_path, "w", encoding="utf-8") as f:
            json.dump(old_config, f, indent=2, ensure_ascii=False)
        backup_path = CONFIG_FILE.with_suffix(".json.backup")
        shutil.move(str(CONFIG_FILE), str(backup_path))
        legacy_api_key = old_config.get("api_secret_key")
        if legacy_api_key:
            save_config({"api_secret_key": legacy_api_key})
        legacy_knowledge = DATA_DIR / "knowledge.sqlite"
        bot_knowledge = get_bot_knowledge_path(bot_id)
        if legacy_knowledge.exists() and not bot_knowledge.exists():
            shutil.copy2(str(legacy_knowledge), str(bot_knowledge))
            logger.info(f"Migrated legacy knowledge DB -> {bot_knowledge}")
        logger.info(f"Migrated legacy config -> {bot_config_path} (backup: {backup_path})")
        return bot_id

    async def load_all(self) -> None:
        async with self._lock:
            migrated_id = self._migrate_legacy_config()
            bot_dirs = self._get_all_bot_dirs()
            for bot_dir in bot_dirs:
                bot_id = bot_dir.name
                if bot_id in self._instances:
                    continue
                config_path = get_bot_config_path(bot_id)
                if not config_path.exists():
                    logger.warning(f"No config.json found for bot '{bot_id}', skipping.")
                    continue
                try:
                    instance = BotInstance(bot_id)
                    instance.load_config()
                    self._instances[bot_id] = instance
                    logger.info(f"Loaded bot config: {bot_id}")
                except Exception as e:
                    logger.error(f"Failed to load bot '{bot_id}': {e}", exc_info=True)

            # Lazy-init AstrBotProcessManager if any bot uses astrbot mode
            has_astrbot = any(
                inst.provider_mode == "astrbot" for inst in self._instances.values()
            )
            if has_astrbot:
                self._get_astrbot_manager()

            for bot_id, instance in self._instances.items():
                if instance.config.get("enabled", True):
                    try:
                        await instance.start()
                    except Exception as e:
                        logger.error(f"Failed to start bot '{bot_id}': {e}", exc_info=True)

    async def create(self, config: Dict[str, Any]) -> str:
        bot_id = config.get("bot_id")
        if not bot_id:
            raise ValueError("bot_id is required")
        async with self._lock:
            if bot_id in self._instances:
                raise ValueError(f"Bot '{bot_id}' already exists")
            instance = BotInstance(bot_id)
            instance.save_config(config)
            instance.load_config()
            self._instances[bot_id] = instance
            logger.info(f"Created bot: {bot_id}")
            return bot_id

    async def delete(self, bot_id: str) -> None:
        async with self._lock:
            instance = self._instances.get(bot_id)
            if instance:
                await instance.stop()
                del self._instances[bot_id]
            bot_dir = get_bot_dir(bot_id)
            if bot_dir.exists():
                shutil.rmtree(str(bot_dir))
            logger.info(f"Deleted bot: {bot_id}")

    async def start(self, bot_id: str) -> None:
        async with self._lock:
            instance = self._instances.get(bot_id)
            if not instance:
                raise ValueError(f"Bot '{bot_id}' not found")
            # Ensure AstrBotProcessManager is initialized for astrbot bots.
            # This covers API-created bots where load_all() did not run.
            if instance.provider_mode == "astrbot":
                self._get_astrbot_manager()
            await instance.start()

    async def stop(self, bot_id: str) -> None:
        async with self._lock:
            instance = self._instances.get(bot_id)
            if not instance:
                raise ValueError(f"Bot '{bot_id}' not found")
            await instance.stop()

    async def restart(self, bot_id: str) -> None:
        async with self._lock:
            instance = self._instances.get(bot_id)
            if not instance:
                raise ValueError(f"Bot '{bot_id}' not found")
            await instance.restart()

    async def rename(self, old_id: str, new_id: str) -> str:
        import re
        if not new_id or not re.match(r'^[a-z0-9_-]+$', new_id):
            raise ValueError("bot_id must contain only lowercase letters, digits, hyphens, and underscores")

        async with self._lock:
            if old_id not in self._instances:
                raise ValueError(f"Bot '{old_id}' not found")
            if new_id in self._instances:
                raise ValueError(f"Bot '{new_id}' already exists")

            instance = self._instances[old_id]
            was_running = instance.is_running()

            if was_running:
                await instance.stop()

            # Capture old paths before mutating bot_id (config_dir/config_path derive from bot_id)
            old_dir = instance.config_dir
            old_config_path = instance.config_path

            instance.config["bot_id"] = new_id
            instance.bot_id = new_id

            # New paths now reflect the updated bot_id
            new_dir = instance.config_dir
            new_config_path = instance.config_path

            old_dir.rename(new_dir)

            import json
            raw_config = json.loads(new_config_path.read_text(encoding="utf-8"))
            raw_config["bot_id"] = new_id
            new_config_path.write_text(json.dumps(raw_config, indent=2, ensure_ascii=False), encoding="utf-8")

            del self._instances[old_id]
            self._instances[new_id] = instance

            if was_running:
                await instance.start()

            logger.info(f"Renamed bot '{old_id}' -> '{new_id}'")
            return new_id

    async def shutdown(self) -> None:
        async with self._lock:
            for instance in list(self._instances.values()):
                try:
                    await instance.stop()
                except Exception as e:
                    logger.error(f"Error stopping bot '{instance.bot_id}': {e}", exc_info=True)
            self._instances.clear()
            if self._astrbot_manager:
                await self._astrbot_manager.shutdown()
            logger.info("All bots shut down.")
