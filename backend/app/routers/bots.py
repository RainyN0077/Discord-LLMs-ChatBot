import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from ..dependencies import get_api_key
from ..models import BotInstanceStatus, Config, CreateBotRequest
from .. import state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bots", dependencies=[Depends(get_api_key)])


def _get_manager():
    mgr = state.bot_manager
    if mgr is None:
        raise HTTPException(status_code=503, detail="Bot manager not initialized")
    return mgr


def _resolve_bot_id(bot_id: str):
    mgr = _get_manager()
    instance = mgr.get(bot_id)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")
    return mgr, instance


@router.get("/")
async def list_bots() -> List[Dict[str, Any]]:
    mgr = _get_manager()
    return mgr.list()


@router.post("/")
async def create_bot(request: CreateBotRequest) -> Dict[str, Any]:
    mgr = _get_manager()
    config = request.model_dump(by_alias=True)
    try:
        bot_id = await mgr.create(config)
        return {"message": f"Bot '{bot_id}' created.", "bot_id": bot_id}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{bot_id}")
async def delete_bot(bot_id: str) -> Dict[str, Any]:
    mgr, instance = _resolve_bot_id(bot_id)
    await mgr.delete(bot_id)
    return {"message": f"Bot '{bot_id}' deleted."}


@router.post("/{bot_id}/start")
async def start_bot(bot_id: str) -> Dict[str, Any]:
    mgr, instance = _resolve_bot_id(bot_id)
    if instance.is_running():
        return {"message": f"Bot '{bot_id}' is already running."}
    await mgr.start(bot_id)
    return {"message": f"Bot '{bot_id}' started.", "status": instance.status}


@router.post("/{bot_id}/stop")
async def stop_bot(bot_id: str) -> Dict[str, Any]:
    mgr, instance = _resolve_bot_id(bot_id)
    if not instance.is_running():
        return {"message": f"Bot '{bot_id}' is not running."}
    await mgr.stop(bot_id)
    return {"message": f"Bot '{bot_id}' stopped.", "status": instance.status}


@router.post("/{bot_id}/restart")
async def restart_bot(bot_id: str) -> Dict[str, Any]:
    mgr, instance = _resolve_bot_id(bot_id)
    await mgr.restart(bot_id)
    return {"message": f"Bot '{bot_id}' restarted.", "status": instance.status}


@router.get("/{bot_id}/config")
async def get_bot_config(bot_id: str) -> Dict[str, Any]:
    mgr, instance = _resolve_bot_id(bot_id)
    return instance.config


@router.put("/{bot_id}/config")
async def update_bot_config(bot_id: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
    mgr, instance = _resolve_bot_id(bot_id)
    try:
        import copy
        merged = copy.deepcopy(instance.config)
        merged.update(config_data)
        instance.save_config(merged)
        instance.load_config()
        if instance.config.get("enabled", True):
            await mgr.restart(bot_id)
        logger.info(f"Bot '{bot_id}' configuration updated and bot restarted successfully")
        return {"message": f"Bot '{bot_id}' configuration updated.", "status": instance.status}
    except Exception as e:
        logger.error(f"Failed to update bot '{bot_id}' config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while updating the configuration.")


@router.get("/{bot_id}/logs")
async def get_bot_logs(bot_id: str) -> Dict[str, Any]:
    mgr, instance = _resolve_bot_id(bot_id)
    log_file = instance.config_dir / ".local-run" / "bot.log"
    if not log_file.exists():
        return {"logs": [], "message": "No log file found."}
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return {"logs": [line.rstrip() for line in lines[-200:]]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {e}")
