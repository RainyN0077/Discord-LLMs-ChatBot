from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from .bot_manager import BotManager

bot_task = None
MEMORY_CUTOFFS: Dict[int, datetime] = {}
bot_manager: Optional["BotManager"] = None
nonebot_driver: Any = None
astrbot_process_manager: Any = None  # AstrBotProcessManager instance


def get_bot_manager() -> "BotManager":
    return bot_manager
