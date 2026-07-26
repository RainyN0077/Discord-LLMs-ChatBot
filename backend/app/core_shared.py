import logging
import os
import re
import socket
import time
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, TextIO

import redis

from .security.log_sanitizer import SanitizingFilter
from .utils import TokenCalculator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Register the secret-sanitising filter on the root logger so every log
# message in the application is automatically redacted.
# ---------------------------------------------------------------------------
logging.getLogger().addFilter(SanitizingFilter())

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
_last_redis_attempt: float = 0.0
REDIS_RETRY_INTERVAL = 30  # seconds between reconnection attempts


def get_redis():
    """Return the global Redis client, or ``None`` if Redis is unavailable.

    **Graceful degradation** — when Redis cannot be reached the first time
    (or the connection has been lost) the function logs a warning and returns
    ``None``.  Callers **must** check for ``None`` and degrade cache/queue
    operations accordingly.

    **Auto-reconnect** — every ``REDIS_RETRY_INTERVAL`` seconds the function
    attempts to re-establish the connection.  A quick ``PING`` health-check
    is also performed on every call so that a stale connection is detected
    early.
    """
    global redis_client, _last_redis_attempt

    # ---- Health check on existing connection ----
    if redis_client is not None:
        try:
            redis_client.ping()
            return redis_client
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            logger.warning(
                "[instance=%s] Redis ping failed: %s. Marking as disconnected.",
                INSTANCE_ID, e,
            )
            redis_client = None

    # ---- Throttled reconnection ----
    now = time.monotonic()
    if now - _last_redis_attempt < REDIS_RETRY_INTERVAL:
        return None  # degraded mode
    _last_redis_attempt = now

    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    try:
        _client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True,
            socket_connect_timeout=2, socket_timeout=2,
        )
        _client.ping()
        redis_client = _client
        logger.info(
            "[instance=%s] Redis connected at %s:%s",
            INSTANCE_ID, REDIS_HOST, REDIS_PORT,
        )
        return redis_client
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
        logger.warning(
            "[instance=%s] Redis at %s:%s unavailable: %s. "
            "Running in degraded mode (cache/queue operations will no-op).",
            INSTANCE_ID, REDIS_HOST, REDIS_PORT, e,
        )
        return None

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


# ---------------------------------------------------------------------------
# Unified logging setup  (moved from utils.py)
# ---------------------------------------------------------------------------

def setup_logging():
    """Configure the root logger once.

    * Clears any pre-existing handlers.
    * Adds a coloured/generic ``StreamHandler`` and a ``RotatingFileHandler``.
    * Registers the :class:`SanitizingFilter` (also registered at module-level
      for early coverage, but this ensures it is present after setup).
    * Silences noisy third-party loggers.
    """

    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    log_formatter = logging.Formatter(
        fmt='%(asctime)s.%(msecs)03dZ [%(name)-18s] - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S',
    )
    log_formatter.converter = time.gmtime

    root_logger.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(log_formatter)
    root_logger.addHandler(stream_handler)

    # ---- Uvicorn loggers (let them propagate to the root) ----
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(logging.INFO)

    # ---- Rotating file handler ----
    try:
        data_dir = Path.cwd() / 'data'
        log_dir = data_dir / 'logs'
        log_dir.mkdir(exist_ok=True, parents=True)
        log_file = log_dir / 'bot.log'

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8',
        )
        file_handler.setFormatter(log_formatter)
        root_logger.addHandler(file_handler)

        root_logger.info("File logging configured successfully to: %s", log_file)

    except (PermissionError, IOError) as e:
        root_logger.error(
            "Could not configure file logging: %s", e, exc_info=True,
        )
    except Exception as e:
        root_logger.error(
            "Unexpected error during file logging setup: %s", e, exc_info=True,
        )

    # ---- SanitizingFilter (belt-and-suspenders with module-level registration) ----
    # Check if already registered to avoid duplicates.
    has_sanitizer = any(
        isinstance(f, SanitizingFilter)
        for f in root_logger.filters
    )
    if not has_sanitizer:
        root_logger.addFilter(SanitizingFilter())

    # ---- Noisy loggers ----
    noisy_loggers = {
        "httpx": logging.WARNING,
        "httpcore": logging.WARNING,
        "discord.client": logging.WARNING,
        "discord.gateway": logging.WARNING,
        "discord.http": logging.WARNING,
        "discord.state": logging.WARNING,
        "urllib3": logging.WARNING,
        "asyncio": logging.WARNING,
    }
    for name, level in noisy_loggers.items():
        logging.getLogger(name).setLevel(level)

    # Discourage loguru from interfering when NoneBot initialises.
    os.environ.setdefault("LOGURU_LEVEL", "WARNING")
    os.environ.setdefault("LOGURU_AUTOINIT", "0")
