from datetime import datetime
from typing import Any, Dict, Optional

bot_task = None
MEMORY_CUTOFFS: Dict[int, datetime] = {}
bot_manager: Optional["BotManager"] = None
nonebot_driver: Any = None
