import asyncio
import json
import logging
import os
from typing import Dict, Any

from fastapi import APIRouter, Depends, Header, Query

from ..config_cache import DATA_DIR
from ..dependencies import get_api_key, get_usage_tracker_dep
from ..usage_tracker import UsageTracker

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/usage/stats", dependencies=[Depends(get_api_key)])
async def get_usage_statistics(
    period: str = Query(default="today"),
    view: str = Query(default="user"),
    x_timezone: str = Header(default="UTC"),
    ut: UsageTracker = Depends(get_usage_tracker_dep),
):
    stats = await ut.get_statistics(period, view, timezone_str=x_timezone)
    return stats


@router.post("/api/usage/pricing", dependencies=[Depends(get_api_key)])
async def update_pricing(pricing_dict: Dict[str, Any]):
    pricing_file = str(DATA_DIR / "pricing_config.json")

    def _write() -> None:
        with open(pricing_file, 'w') as f:
            json.dump(pricing_dict, f, indent=2)

    await asyncio.to_thread(_write)
    return {"message": "Pricing updated"}


@router.get("/api/usage/pricing", dependencies=[Depends(get_api_key)])
async def get_pricing():
    pricing_file = str(DATA_DIR / "pricing_config.json")

    def _read():
        if not os.path.exists(pricing_file):
            return None
        try:
            with open(pricing_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.info(f"Pricing config file not found at {pricing_file}.")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding pricing_config.json: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error reading pricing config: {e}", exc_info=True)
            return None

    pricing_data = await asyncio.to_thread(_read)
    if pricing_data is not None:
        return {"pricing": pricing_data}
    return {"pricing": {}}
