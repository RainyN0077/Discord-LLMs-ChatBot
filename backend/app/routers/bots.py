import asyncio
import json
import logging
from collections import deque
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..dependencies import get_api_key
from ..models import BotInstanceStatus, Config, CreateBotRequest
from ..config_cache import DATA_DIR, normalize_config
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


@router.get("/", summary="获取 Bot 列表", description="返回所有已注册 Bot 实例的列表，包含每个 Bot 的运行状态和基本信息。")
async def list_bots() -> List[Dict[str, Any]]:
    mgr = _get_manager()
    return mgr.list()


@router.post("/", summary="创建 Bot", description="创建一个新的 Bot 实例。需要提供配置数据，bot_id 会自动生成或从配置中读取。")
async def create_bot(request: CreateBotRequest) -> Dict[str, Any]:
    mgr = _get_manager()
    config = request.model_dump(by_alias=True)
    try:
        bot_id = await mgr.create(config)
        return {"message": f"Bot '{bot_id}' created.", "bot_id": bot_id}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{bot_id}", summary="删除 Bot", description="删除指定 Bot 实例及其配置文件和知识库数据。此操作不可撤销。")
async def delete_bot(bot_id: str) -> Dict[str, Any]:
    mgr, instance = _resolve_bot_id(bot_id)
    await mgr.delete(bot_id)
    return {"message": f"Bot '{bot_id}' deleted."}


@router.post("/{bot_id}/start", summary="启动 Bot", description="启动指定 Bot 实例，建立 Discord/QQ 适配器连接。")
async def start_bot(bot_id: str) -> Dict[str, Any]:
    mgr, instance = _resolve_bot_id(bot_id)
    if instance.is_running():
        return {"message": f"Bot '{bot_id}' is already running."}
    await mgr.start(bot_id)
    return {"message": f"Bot '{bot_id}' started.", "status": instance.status}


@router.post("/{bot_id}/stop", summary="停止 Bot", description="停止指定 Bot 实例，断开适配器连接。")
async def stop_bot(bot_id: str) -> Dict[str, Any]:
    mgr, instance = _resolve_bot_id(bot_id)
    if not instance.is_running():
        return {"message": f"Bot '{bot_id}' is not running."}
    await mgr.stop(bot_id)
    return {"message": f"Bot '{bot_id}' stopped.", "status": instance.status}


@router.post("/{bot_id}/restart", summary="重启 Bot", description="重启指定 Bot 实例（停止后重新启动）。")
async def restart_bot(bot_id: str) -> Dict[str, Any]:
    mgr, instance = _resolve_bot_id(bot_id)
    await mgr.restart(bot_id)
    return {"message": f"Bot '{bot_id}' restarted.", "status": instance.status}


@router.put("/{bot_id}/rename", summary="重命名 Bot", description="修改 Bot 的唯一标识符（bot_id）。新 ID 只能包含小写字母、数字、连字符和下划线。")
async def rename_bot(bot_id: str, body: Dict[str, str]) -> Dict[str, Any]:
    new_id = body.get("new_id", "").strip()
    if not new_id:
        raise HTTPException(status_code=400, detail="new_id is required")
    mgr = _get_manager()
    try:
        renamed = await mgr.rename(bot_id, new_id)
        return {"message": f"Bot renamed to '{renamed}'.", "bot_id": renamed}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{bot_id}/config", summary="获取 Bot 配置", description="返回指定 Bot 实例的完整配置对象。")
async def get_bot_config(bot_id: str) -> Dict[str, Any]:
    mgr, instance = _resolve_bot_id(bot_id)
    return instance.config


@router.put("/{bot_id}/config", summary="更新 Bot 配置", description="更新指定 Bot 的配置字段。如果 Bot 已启用，会自动重启以应用新配置。")
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


@router.get("/{bot_id}/adapter/status", summary="获取适配器状态", description="返回 Bot 的 AstrBot 进程连接状态。")
async def get_adapter_status(bot_id: str) -> Dict[str, Any]:
    mgr = _get_manager()
    instance = mgr.get(bot_id)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")

    astrbot_mgr = state.astrbot_process_manager
    if astrbot_mgr is None:
        raise HTTPException(status_code=503, detail="AstrBot process manager not initialized")

    status_info = astrbot_mgr.get_status(bot_id)
    if status_info is None:
        return {
            "bot_id": bot_id,
            "status": "stopped",
            "pid": None,
            "connected": False,
        }

    return {
        "bot_id": bot_id,
        "status": status_info.get("status", "unknown"),
        "pid": status_info.get("pid"),
        "connected": status_info.get("status") == "running",
        "started_at": status_info.get("started_at"),
    }


@router.get("/{bot_id}/logs", summary="获取 Bot 日志", description="返回指定 Bot 日志文件的最后 200 行。")
async def get_bot_logs(bot_id: str) -> Dict[str, Any]:
    mgr, instance = _resolve_bot_id(bot_id)
    log_file = DATA_DIR / "logs" / "bot.log"
    if not log_file.exists():
        return {"logs": [], "message": "No log file found."}
    try:
        def _read_log():
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                return list(deque(f, 200))
        lines = await asyncio.to_thread(_read_log)
        return {"logs": [line.rstrip() for line in lines]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {e}")


@router.get("/{bot_id}/export", summary="导出 Bot 配置", description="以 JSON 文件的形式导出指定 Bot 的完整配置，用于备份或迁移。")
async def export_bot_config(bot_id: str):
    mgr, instance = _resolve_bot_id(bot_id)
    config = instance.config or {}
    filename = f"{bot_id}-config.json"
    return JSONResponse(
        content=config,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post("/import", summary="导入 Bot 配置", description="通过 JSON 文件上传或 JSON 字符串导入 Bot 配置。支持覆盖已有 Bot 或创建新 Bot。")
async def import_bot_config(
    file: Optional[UploadFile] = None,
    config_json: Optional[str] = Form(None),
    overwrite: bool = Form(False),
):
    mgr = _get_manager()

    if file:
        raw = await file.read()
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON file: {e}")
    elif config_json:
        try:
            data = json.loads(config_json)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {e}")
    else:
        raise HTTPException(status_code=400, detail="Provide either a JSON file upload or config_json form field")

    normalized = normalize_config(data)

    bot_id = str(normalized.get("bot_id") or "").strip()
    if not bot_id:
        raise HTTPException(status_code=400, detail="Config must include a bot_id field")

    import re
    if not re.match(r'^[a-z0-9_-]+$', bot_id):
        raise HTTPException(status_code=400, detail="bot_id must contain only lowercase letters, digits, hyphens, and underscores")

    existing = mgr.get(bot_id)
    if existing and not overwrite:
        raise HTTPException(
            status_code=409,
            detail=f"Bot '{bot_id}' already exists. Set overwrite=true to replace it.",
        )

    if existing:
        existing.save_config(normalized)
        existing.load_config()
        if normalized.get("enabled", True):
            await mgr.restart(bot_id)
        logger.info(f"Bot '{bot_id}' configuration overwritten via import.")
        return {"message": f"Bot '{bot_id}' configuration overwritten.", "bot_id": bot_id, "status": existing.status}
    else:
        created_id = await mgr.create(normalized)
        logger.info(f"Bot '{created_id}' created via import.")
        return {"message": f"Bot '{created_id}' imported successfully.", "bot_id": created_id, "status": "stopped"}
