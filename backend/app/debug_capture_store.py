from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Deque, Dict, List, Optional
import uuid

MAX_CAPTURE_RECORDS = 80

_captures: Deque[Dict[str, Any]] = deque(maxlen=MAX_CAPTURE_RECORDS)
_lock = Lock()


def add_capture(record: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(record or {})
    item.setdefault("id", uuid.uuid4().hex)
    item.setdefault("captured_at", datetime.now(timezone.utc).isoformat())
    with _lock:
        _captures.appendleft(item)
    return deepcopy(item)


def list_captures(limit: int = 20, channel_id: Optional[str] = None) -> List[Dict[str, Any]]:
    safe_limit = max(1, min(100, int(limit or 20)))
    with _lock:
        rows = list(_captures)
    if channel_id:
        channel_str = str(channel_id)
        rows = [row for row in rows if str(row.get("channel_id", "")) == channel_str]
    return deepcopy(rows[:safe_limit])


def get_capture(capture_id: str) -> Optional[Dict[str, Any]]:
    if not capture_id:
        return None
    with _lock:
        for row in _captures:
            if row.get("id") == capture_id:
                return deepcopy(row)
    return None
