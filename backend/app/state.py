from datetime import datetime
from typing import Dict, Optional
import asyncio

bot_task = None
qq_bot_task: Optional[asyncio.Task] = None
MEMORY_CUTOFFS: Dict[int, datetime] = {}
