import logging
import os
from collections import deque

from fastapi import APIRouter, Depends, Response

from ..config_cache import DATA_DIR
from ..dependencies import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_LOG_FILE_SIZE = 10 * 1024 * 1024  # 10MB


async def _read_log_tail() -> str:
    log_file_path = DATA_DIR / 'logs/bot.log'
    try:
        file_size = os.path.getsize(log_file_path)
    except OSError:
        return ""

    if file_size > MAX_LOG_FILE_SIZE:
        import asyncio
        def _read_tail():
            chunk_size = 4 * 1024 * 1024
            offset = max(0, file_size - chunk_size)
            with open(log_file_path, 'rb') as f:
                os.pread(f.fileno(), min(chunk_size, file_size), offset)
                f.seek(offset)
                return f.read().decode('utf-8', errors='replace')
        content = await asyncio.to_thread(_read_tail)
        lines = content.splitlines()
        return "\n".join(lines[-200:])
    else:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            return "".join(deque(f, 200))


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
