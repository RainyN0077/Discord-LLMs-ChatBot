import asyncio
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional
import uuid

MAX_CAPTURE_RECORDS = 80

_captures: Deque[Dict[str, Any]] = deque(maxlen=MAX_CAPTURE_RECORDS)
_lock = asyncio.Lock()


async def add_capture(record: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(record or {})
    item.setdefault("id", uuid.uuid4().hex)
    item.setdefault("captured_at", datetime.now(timezone.utc).isoformat())
    async with _lock:
        _captures.appendleft(item)
    return deepcopy(item)


async def list_captures(limit: int = 20, channel_id: Optional[str] = None) -> List[Dict[str, Any]]:
    safe_limit = max(1, min(100, int(limit or 20)))
    async with _lock:
        rows = list(_captures)
    if channel_id:
        channel_str = str(channel_id)
        rows = [row for row in rows if str(row.get("channel_id", "")) == channel_str]
    return deepcopy(rows[:safe_limit])


async def get_capture(capture_id: str) -> Optional[Dict[str, Any]]:
    if not capture_id:
        return None
    async with _lock:
        for row in _captures:
            if row.get("id") == capture_id:
                return deepcopy(row)
    return None


async def delete_capture(capture_id: str) -> bool:
    """按 ID 删除单条捕获（持锁）。不存在返回 False。"""
    if not capture_id:
        return False
    async with _lock:
        for idx, row in enumerate(_captures):
            if row.get("id") == capture_id:
                del _captures[idx]
                return True
    return False


async def clear_captures() -> int:
    """清空全部捕获（持锁），返回删除条数。"""
    async with _lock:
        count = len(_captures)
        _captures.clear()
        return count
