import asyncio
import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import ValidationError

from ..config_cache import load_config, save_config
from ..dependencies import get_api_key
from ..models import Config
from .. import state

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/config")
async def get_config_endpoint():
    config_data = load_config()
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
    from ..bot import run_bot
    try:
        config_dict = config_data.dict(by_alias=True)
        config_dict.pop("_validation_warning", None)
        save_config(config_dict)

        if state.bot_task and not state.bot_task.done():
            state.bot_task.cancel()
            try:
                await state.bot_task
            except asyncio.CancelledError:
                pass

        loop = asyncio.get_event_loop()
        state.bot_task = loop.create_task(run_bot(state.MEMORY_CUTOFFS))

        logger.info("Configuration updated and bot restarted successfully")
        return {"message": "Configuration updated and bot restarted."}
    except Exception as e:
        logger.error(f"Failed to update configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while updating the configuration.")
