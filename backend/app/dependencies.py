import logging
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from .config_cache import load_config

logger = logging.getLogger(__name__)

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)
api_key_header_optional = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_api_key(api_key_received: str = Security(api_key_header)):
    config = load_config()
    correct_api_key = config.get("api_secret_key")
    if not correct_api_key:
        from .config_cache import save_config
        correct_api_key = secrets.token_hex(32)
        config["api_secret_key"] = correct_api_key
        save_config(config)
        logger.warning("api_secret_key was empty, auto-generated a new one and persisted to config.json")
    if secrets.compare_digest(api_key_received, correct_api_key):
        return api_key_received
    raise HTTPException(status_code=403, detail="Could not validate credentials")


async def get_api_key_optional(api_key_received: str = Security(api_key_header_optional)):
    if not api_key_received:
        return None
    config = load_config()
    correct_api_key = config.get("api_secret_key")
    if not correct_api_key:
        return None
    if secrets.compare_digest(api_key_received, correct_api_key):
        return api_key_received
    return None
