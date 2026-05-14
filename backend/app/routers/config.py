import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import ValidationError

from ..config_cache import load_config, save_config, DEFAULT_BOT_ID
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


@router.get("/api/config")
async def get_config_endpoint():
    config_data = _get_first_bot_config()
    try:
        Config.parse_obj(config_data)
        logger.info("Config validation successful")
        return config_data
    except ValidationError as e:
        logger.error(f"Config validation failed: {e}")
        config_data["_validation_warning"] = str(e)
        return config_data


@router.post("/api/config", dependencies=[Depends(get_api_key)])
async def update_config_endpoint(config_data: Config):
    mgr = state.bot_manager
    if not mgr:
        try:
            config_dict = config_data.model_dump(by_alias=True)
            config_dict.pop("_validation_warning", None)
            save_config(config_dict)
            return {"message": "Configuration saved (no bot manager running)."}
        except Exception as e:
            logger.error(f"Failed to save config: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="An internal error occurred while saving the configuration.")

    config_dict = config_data.model_dump(by_alias=True)
    config_dict.pop("_validation_warning", None)
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
