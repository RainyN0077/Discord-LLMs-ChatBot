import asyncio
import json
import logging
import os

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, ValidationError

from ..config_cache import load_config, save_config, DEFAULT_BOT_ID, CONFIG_FILE
from ..dependencies import get_api_key
from ..models import Config
from .. import state

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_first_bot_config():
    mgr = state.bot_manager
    global_config = load_config()
    global_key = global_config.get('api_secret_key')
    if mgr and mgr._instances:
        first = next(iter(mgr._instances.values()))
        cfg = dict(first.config)
        if global_key and cfg.get('api_secret_key') != global_key:
            cfg['api_secret_key'] = global_key
            logger.debug('_get_first_bot_config: synced api_secret_key from global config')
        return cfg
    return global_config


@router.get("/api/config", summary="获取配置", description="返回第一个 Bot 实例的完整配置（或全局配置）。配置文件会在保存时自动验证结构。")
async def get_config_endpoint(api_key: str = Depends(get_api_key)):
    config_data = _get_first_bot_config()
    try:
        Config.parse_obj(config_data)
        logger.info("Config validation successful")
        return config_data
    except ValidationError as e:
        logger.error(f"Config validation failed: {e}")
        config_data["_validation_warning"] = str(e)
        return config_data


class BootstrapRequest(BaseModel):
    api_secret_key: str


def _is_localhost(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost")


@router.get("/api/auth/status", summary="认证状态", description="无认证端点。仅 localhost 请求返回 api_secret_key（供前端自动认证，实现傻瓜式启动）；非 localhost 请求不返回密钥。")
async def auth_status_endpoint(request: Request):
    config_data = load_config()
    key = config_data.get("api_secret_key") or ""
    if _is_localhost(request):
        return {"authenticated": False, "api_secret_key": key}
    return {"authenticated": False, "api_secret_key": ""}


@router.post("/api/auth/bootstrap", summary="初始化 API 密钥", description="仅在 localhost 可用。用于首次部署时通过 Web UI 设置 api_secret_key。一旦密钥已配置，此端点将被禁用。")
async def bootstrap_api_secret(request: Request, body: BootstrapRequest):
    if not _is_localhost(request):
        raise HTTPException(status_code=403, detail="Bootstrap is only allowed from localhost.")
    if not body.api_secret_key:
        raise HTTPException(status_code=422, detail="api_secret_key must not be empty.")

    # Read the raw config file directly to bypass load_config()'s auto-generation of api_secret_key.
    def _read_raw_config():
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Bootstrap: failed to read config file: {e}")
                return None  # sentinel for failure
        return {}

    raw_config = await asyncio.to_thread(_read_raw_config)
    if raw_config is None:
        raise HTTPException(status_code=500, detail="Failed to read configuration.")

    existing_key = raw_config.get("api_secret_key")
    if existing_key:
        raise HTTPException(status_code=403, detail="API secret key is already configured. Bootstrap is disabled.")

    raw_config["api_secret_key"] = body.api_secret_key
    await asyncio.to_thread(save_config, raw_config)
    # Invalidate cache so subsequent load_config() calls pick up the new key.
    from ..config_cache import invalidate_cache as invalidate_config_cache
    invalidate_config_cache()

    logger.info("Bootstrap: api_secret_key has been set.")
    return {"message": "API secret key has been set.", "api_secret_key": body.api_secret_key}


@router.post("/api/config", summary="更新配置", description="更新全局或指定 Bot 的配置。如果 Bot 正在运行，会触发自动重启以应用新配置。", dependencies=[Depends(get_api_key)])
async def update_config_endpoint(config_data: Config):
    mgr = state.bot_manager
    if not mgr:
        try:
            config_dict = config_data.model_dump(by_alias=True)
            config_dict.pop("_validation_warning", None)
            # quota_alert 未提供 (None) 时不覆盖既有值; 显式清空请发送空对象 {}
            if config_dict.get("quota_alert") is None:
                config_dict.pop("quota_alert", None)
            save_config(config_dict)
            return {"message": "Configuration saved (no bot manager running)."}
        except Exception as e:
            logger.error(f"Failed to save config: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="An internal error occurred while saving the configuration.")

    config_dict = config_data.model_dump(by_alias=True)
    config_dict.pop("_validation_warning", None)
    # quota_alert 未提供 (None) 时不覆盖既有值; 显式清空请发送空对象 {}
    if config_dict.get("quota_alert") is None:
        config_dict.pop("quota_alert", None)
    bot_id = config_dict.get("bot_id") or DEFAULT_BOT_ID

    if bot_id in mgr._instances:
        instance = mgr._instances[bot_id]
        try:
            merged = {**instance.config, **config_dict}
            instance.save_config(merged)
            instance.load_config()
            if instance.config.get("enabled", True):
                await mgr.restart(bot_id)
            logger.info("Configuration updated and bot restarted successfully")
            return {"message": "Configuration updated and bot restarted.", "bot_id": bot_id}
        except Exception as e:
            logger.error(f"Failed to update configuration: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="An internal error occurred while updating the configuration.")
    else:
        try:
            save_config(config_dict)
            return {"message": "Configuration saved (bot not yet in manager)."}
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="An internal error occurred while saving the configuration.")
