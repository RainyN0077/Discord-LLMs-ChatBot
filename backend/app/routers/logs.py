import asyncio
import logging
import os

from fastapi import APIRouter, Depends, Response

from ..config_cache import DATA_DIR
from ..dependencies import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_LOG_FILE_SIZE = 10 * 1024 * 1024  # 10MB
_CHUNK_SIZE = 4 * 1024 * 1024  # 4MB — amount to read from the tail of large files


async def _read_log_tail() -> str:
    """Return the last 200 lines of bot.log, handling truncation and large files."""
    log_file_path = DATA_DIR / 'logs/bot.log'
    try:
        file_size = os.path.getsize(log_file_path)
    except OSError:
        return ""

    if file_size == 0:
        return ""

    def _read() -> str:
        """Synchronous file read — run inside asyncio.to_thread to avoid blocking."""
        with open(log_file_path, 'rb') as f:
            if file_size > MAX_LOG_FILE_SIZE:
                offset = max(0, file_size - _CHUNK_SIZE)
                f.seek(offset)
            raw = f.read()
        return raw.decode('utf-8', errors='replace')

    content = await asyncio.to_thread(_read)

    # ── Discard incomplete last line ──────────────────────────────
    # If the file is being written to concurrently, the final line may
    # be truncated (no trailing newline).  Drop it to avoid serving
    # garbled / partial log entries.
    if content and not content.endswith('\n'):
        last_newline = content.rfind('\n')
        if last_newline != -1:
            content = content[:last_newline + 1]
        else:
            return ""          # no complete line found in the chunk

    lines = content.splitlines()
    return "\n".join(lines[-200:])


@router.get("/api/logs", dependencies=[Depends(get_api_key)])
async def get_logs():
    log_file_path = DATA_DIR / 'logs/bot.log'
    headers = {"Access-Control-Allow-Origin": "*"}
    if not log_file_path.exists():
        logger.warning(f"Log file not found at '{log_file_path}'.")
        return Response(
            content=f"INFO: Log file at '{log_file_path}' not found.",
            media_type="text/plain; charset=utf-8",
            headers=headers,
        )

    try:
        log_content = await _read_log_tail()
        return Response(
            content=log_content,
            media_type="text/plain; charset=utf-8",
            headers=headers,
        )
    except Exception as e:
        error_message = f"ERROR: Unexpected error while reading logs: {e}"
        logger.error(error_message, exc_info=True)
        return Response(
            content=error_message,
            status_code=200,
            media_type="text/plain; charset=utf-8",
            headers=headers,
        )
