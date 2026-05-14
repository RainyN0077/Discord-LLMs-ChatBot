import logging
import os
import re
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO

import redis

from .utils import TokenCalculator

logger = logging.getLogger(__name__)

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

INSTANCE_ID = os.getenv("BOT_INSTANCE_ID") or f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"

redis_client = None


def get_redis():
    global redis_client
    if redis_client is not None:
        return redis_client
    try:
        REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
        REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
        _redis_client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True,
            socket_connect_timeout=2, socket_timeout=2,
        )
        _redis_client.ping()
        redis_client = _redis_client
        logger.info(f"[instance={INSTANCE_ID}] Successfully connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
        logger.error(f"[instance={INSTANCE_ID}] Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}. Error: {e}")
        if os.getenv("FAIL_ON_REDIS_ERROR", "false").lower() == "true":
            logger.critical(f"[instance={INSTANCE_ID}] FAIL_ON_REDIS_ERROR is true. Terminating application.")
            raise RuntimeError("Redis connection failed.")
        else:
            class MockRedis:
                def __init__(self):
                    self._store = {}
                def set(self, key, value, *args, **kwargs):
                    self._store[key] = value
                    return True
                def get(self, key):
                    return self._store.get(key)
                def ping(self):
                    return True
                def delete(self, key):
                    return self._store.pop(key, None) is not None
                def exists(self, key):
                    return key in self._store
            redis_client = MockRedis()
            logger.warning(f"[instance={INSTANCE_ID}] FAIL_ON_REDIS_ERROR is not set to true. Using a mock Redis client.")
    return redis_client

token_calculator = TokenCalculator()

from .config_cache import DATA_DIR


def _get_bot_lock_path(bot_id: str):
    return DATA_DIR / f"discord_bot_{bot_id}.lock"


def _try_acquire_bot_process_lock(bot_id: str = "main") -> Optional[TextIO]:
    lock_file = _get_bot_lock_path(bot_id)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_file, "a+", encoding="utf-8")
    try:
        handle.seek(0)
        if not handle.read(1):
            handle.write(" ")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            if msvcrt is None:
                raise RuntimeError("msvcrt is required to guard the Discord bot process on Windows.")
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        elif fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            raise RuntimeError("No supported file locking primitive available.")
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        return handle
    except OSError:
        handle.close()
        return None
    except Exception:
        handle.close()
        raise


def _release_bot_process_lock(handle: Optional[TextIO], bot_id: str = "main") -> None:
    if not handle:
        return
    try:
        handle.seek(0)
        handle.truncate()
        handle.write("")
        handle.flush()
        handle.seek(0)
        if os.name == "nt":
            if msvcrt is not None:
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        elif fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        logger.warning("Failed to release Discord bot process lock cleanly.", exc_info=True)
    finally:
        handle.close()


def strip_thinking_sections(text: str) -> str:
    if not text:
        return text
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.IGNORECASE | re.DOTALL)
    return cleaned.strip()


def strip_dsml_tool_blocks(text: str) -> str:
    if not text:
        return text
    cleaned = text
    cleaned = re.sub(
        r"<\s*/?\s*\|\s*DSML\s*\|\s*function_calls\s*>[\s\S]*?<\s*/?\s*\|\s*DSML\s*\|\s*function_calls\s*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(?im)^[^\n\r]*<\s*/?\s*\|\s*DSML\s*\|[^\n\r]*$",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"<\s*/?\s*\|\s*DSML\s*\|[^>]*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip()


def contains_dsml_tool_blocks(text: str) -> bool:
    if not text:
        return False
    return bool(
        re.search(
            r"<\s*/?\s*\|\s*DSML\s*\|\s*(function_calls|invoke|parameter)\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def _parse_user_info_fields(inner_text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    pos = 0
    while pos < len(inner_text):
        eq_pos = inner_text.find('=', pos)
        if eq_pos == -1:
            break
        key = inner_text[pos:eq_pos].strip()
        if key not in ("id", "keywords", "content"):
            break
        val_start = eq_pos + 1
        if key == "content":
            result["content"] = inner_text[val_start:]
            break
        next_semi = inner_text.find(';', val_start)
        if next_semi == -1:
            result[key] = inner_text[val_start:].strip()
            break
        val = inner_text[val_start:next_semi]
        result[key] = val.strip()
        pos = next_semi + 1
    return result
