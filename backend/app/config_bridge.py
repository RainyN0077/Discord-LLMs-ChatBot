import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from .config_cache import BOTS_DIR

logger = logging.getLogger(__name__)

ENV_FILE = Path.cwd() / ".env"


def _read_bot_config(bot_dir: Path) -> Dict[str, Any]:
    config_path = bot_dir / "config.json"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read config for bot '{bot_dir.name}': {e}")
        return {}


def generate_env_file() -> None:
    if not BOTS_DIR.exists():
        return

    discord_bots: List[Dict[str, Any]] = []
    onebot_bots: List[Dict[str, Any]] = []

    for bot_dir in sorted(BOTS_DIR.iterdir()):
        if not bot_dir.is_dir():
            continue
        config = _read_bot_config(bot_dir)
        if not config:
            continue
        if not config.get("enabled", True):
            continue

        platform = config.get("platform", "discord")
        if platform == "discord":
            token = config.get("discord_token", "")
            if token:
                default_intents = {
                    "guilds": True,
                    "guild_messages": True,
                    "direct_messages": True,
                    "message_content": True,
                    "members": True,
                }
                user_intents = config.get("discord_intents", {})
                intents = {**default_intents, **user_intents}
                intents = {k: bool(v) for k, v in intents.items()}
                discord_bots.append({
                    "token": token,
                    "intent": intents,
                })
        elif platform == "qq":
            token = config.get("qq_token") or config.get("discord_token", "")
            if token:
                onebot_bots.append({
                    "token": token,
                })

    lines: List[str] = []
    existing = {}
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    if key not in ("DISCORD_BOTS", "ONEBOT_BOTS"):
                        existing[key] = val.strip()

    for key, value in existing.items():
        lines.append(f"{key}={value}")

    if "DRIVER" not in existing:
        lines.append("DRIVER=~httpx+~websockets")
    if "DISCORD_HANDLE_SELF_MESSAGE" not in existing:
        lines.append("DISCORD_HANDLE_SELF_MESSAGE=false")
    if "LOGURU_LEVEL" not in existing:
        lines.append("LOGURU_LEVEL=WARNING")

    lines.append(f"DISCORD_BOTS={json.dumps(discord_bots, ensure_ascii=False)}")
    lines.append(f"ONEBOT_BOTS={json.dumps(onebot_bots, ensure_ascii=False)}")

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    logger.info(f"Generated .env with {len(discord_bots)} Discord bots and {len(onebot_bots)} QQ bots.")
