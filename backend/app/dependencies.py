import logging
import secrets
from typing import Optional

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from .config_cache import load_config

logger = logging.getLogger(__name__)

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)


async def get_api_key(api_key_received: str = Security(api_key_header)):
    config = load_config()
    correct_api_key = config.get("api_secret_key")
    if not correct_api_key:
        raise HTTPException(status_code=401, detail="API key not configured. Set api_secret_key in config.")
    if secrets.compare_digest(api_key_received, correct_api_key):
        return api_key_received
    raise HTTPException(status_code=403, detail="Could not validate credentials")


# ---------------------------------------------------------------------------
# Dependency Injection providers
# ---------------------------------------------------------------------------


def get_knowledge_manager_dep(bot_id: Optional[str] = None):
    """FastAPI dependency that provides a KnowledgeManager instance.

    Resolves the instance via ``AppContext`` — either from a specific bot
    (when ``bot_id`` is given) or from the first available bot.  Falls back
    to a standalone ``KnowledgeManager`` if no bot is running.
    """
    from .app_context import AppContext
    from .core_logic.knowledge_manager import KnowledgeManager

    ctx = AppContext.get()
    if ctx.bot_manager:
        if bot_id:
            inst = ctx.bot_manager.get(bot_id)
            if inst and hasattr(inst, "_knowledge_manager"):
                return inst._knowledge_manager
        # Fallback: use first bot's knowledge manager
        if hasattr(ctx.bot_manager, "_instances") and ctx.bot_manager._instances:
            first = next(iter(ctx.bot_manager._instances.values()))
            if hasattr(first, "_knowledge_manager") and first._knowledge_manager:
                return first._knowledge_manager
    # Final fallback: return a standalone instance
    return KnowledgeManager()


async def get_usage_tracker_dep():
    """FastAPI dependency that provides the application-wide UsageTracker."""
    from .app_context import AppContext

    ctx = AppContext.get()
    if hasattr(ctx, "usage_tracker") and ctx.usage_tracker is not None:
        return ctx.usage_tracker
    from .usage_tracker import UsageTracker

    logger.warning("No UsageTracker found on AppContext — creating a temporary instance")
    t = UsageTracker()
    await t.initialize()
    return t
