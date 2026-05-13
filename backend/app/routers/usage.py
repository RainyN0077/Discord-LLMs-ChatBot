import json
import logging
import os
from typing import Dict, Any

from fastapi import APIRouter, Depends, Header, Query

from ..config_cache import DATA_DIR
from ..dependencies import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/usage/stats", dependencies=[Depends(get_api_key)])
async def get_usage_statistics(
    period: str = Query(default="today"),
    view: str = Query(default="user"),
    x_timezone: str = Header(default="UTC"),
):
    from ..usage_tracker import usage_tracker
    stats = await usage_tracker.get_statistics(period, view, timezone_str=x_timezone)
    return stats


@router.post("/api/usage/pricing", dependencies=[Depends(get_api_key)])
async def update_pricing(pricing_dict: Dict[str, Any]):
    pricing_file = DATA_DIR / "pricing_config.json"
    with open(pricing_file, 'w') as f:
        json.dump(pricing_dict, f, indent=2)
    return {"message": "Pricing updated"}


@router.get("/api/usage/pricing", dependencies=[Depends(get_api_key)])
async def get_pricing():
    pricing_file = DATA_DIR / "pricing_config.json"
    if os.path.exists(pricing_file):
        try:
            with open(pricing_file, 'r', encoding='utf-8') as f:
                pricing_data = json.load(f)
                return {"pricing": pricing_data}
        except FileNotFoundError:
            logger.info(f"Pricing config file not found at {pricing_file}.")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding pricing_config.json: {e}")
        except Exception as e:
            logger.error(f"Unexpected error reading pricing config: {e}", exc_info=True)
    return {"pricing": {}}
