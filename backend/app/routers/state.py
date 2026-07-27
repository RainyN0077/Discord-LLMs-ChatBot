import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends

from .. import state
from ..dependencies import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/state", tags=["state"])


@router.get("/driver")
async def get_driver_state(api_key: str = Depends(get_api_key)) -> Dict[str, Any]:
    astrbot_mgr = state.astrbot_process_manager
    if astrbot_mgr is None:
        raise HTTPException(status_code=503, detail="AstrBot process manager not initialized")

    processes = astrbot_mgr.list_all()
    bots_list = []
    for bot_id, proc_info in processes.items():
        bots_list.append({
            "bot_id": bot_id,
            "status": proc_info.get("status", "unknown"),
            "pid": proc_info.get("pid"),
            "started_at": proc_info.get("started_at"),
        })

    return {
        "driver_type": "AstrBotProcessManager",
        "processes": bots_list,
    }
