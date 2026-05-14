import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from .. import state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/state", tags=["state"])


@router.get("/driver")
async def get_driver_state() -> Dict[str, Any]:
    driver = state.nonebot_driver
    if driver is None:
        raise HTTPException(status_code=503, detail="NoneBot driver not initialized")

    bots = []
    for adapter_name, adapter in driver._adapters.items():
        bots_info = []
        for bot_id in getattr(adapter, 'bots', {}):
            bot = adapter.bots.get(bot_id)
            bots_info.append({
                "bot_id": str(bot_id),
                "self_id": str(getattr(bot, 'self_id', '')),
                "connected": getattr(bot, '_ws', None) is not None,
            })
        bots.append({
            "adapter": adapter_name,
            "bots": bots_info,
        })

    return {
        "driver_type": type(driver).__name__,
        "adapters": bots,
    }
