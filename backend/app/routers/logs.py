import logging
from collections import deque

from fastapi import APIRouter, Depends, Response

from ..config_cache import DATA_DIR
from ..dependencies import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


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
        with open(log_file_path, 'r', encoding='utf-8') as f:
            log_content = "".join(deque(f, 200))
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
