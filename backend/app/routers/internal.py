"""Internal API Router.

Provides endpoints for AstrBot stars to communicate with the management layer.
All endpoints are authenticated via a shared internal secret token (X-Internal-Token header).

These are NOT exposed to the frontend — they are for inter-process communication
between AstrBot subprocesses and the FastAPI management server.
"""

import asyncio
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header, Request

from ..bot_manager import BotManager
from ..state import get_bot_manager
from ..core_shared import token_calculator, get_redis

logger = logging.getLogger(__name__)

internal_router = APIRouter(prefix="/internal", tags=["internal"])


def _verify_token(request: Request) -> str:
    """Verify the X-Internal-Token header against the bot's api_secret_key.

    Returns the validated bot_id on success.
    """
    token = request.headers.get("X-Internal-Token", "")
    bot_id = request.headers.get("X-Bot-Id", "")
    if not token or not bot_id:
        raise HTTPException(status_code=401, detail="Missing X-Internal-Token or X-Bot-Id header")

    manager = get_bot_manager()
    instance = manager.get(bot_id)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")

    expected = instance.config.get("api_secret_key", "")
    if not expected or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="Invalid internal token")

    return bot_id


# ---------------------------------------------------------------------------
# Knowledge / Memory endpoints
# ---------------------------------------------------------------------------

@internal_router.get("/{bot_id}/knowledge/recall")
async def knowledge_recall(
    bot_id: str,
    query: str = "",
    top_k: int = 12,
    char_limit: int = 2200,
    max_age_days: int = 365,
    request: Request = None,
) -> Dict[str, Any]:
    """Recall relevant memories from the bot's knowledge base."""
    bot_id = _verify_token(request)
    manager = get_bot_manager()
    instance = manager.get(bot_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Bot not found")

    knowledge_manager = instance._knowledge_manager
    if not knowledge_manager:
        return {"memories": []}

    try:
        memories = await knowledge_manager.get_relevant_memories(
            query_text=query,
            top_k=top_k,
            char_limit=char_limit,
            max_age_days=max_age_days,
            config=instance.config,
        )
        return {"memories": memories}
    except Exception as e:
        logger.error("Knowledge recall failed for bot '%s': %s", bot_id, e, exc_info=True)
        return {"memories": [], "error": str(e)}


@internal_router.post("/{bot_id}/knowledge/ingest")
async def knowledge_ingest(
    bot_id: str,
    payload: Dict[str, Any],
    request: Request = None,
) -> Dict[str, Any]:
    """Ingest a memory candidate or world book entry."""
    bot_id = _verify_token(request)
    manager = get_bot_manager()
    instance = manager.get(bot_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Bot not found")

    knowledge_manager = instance._knowledge_manager
    if not knowledge_manager:
        return {"status": "no_knowledge_manager"}

    ingest_type = payload.get("type", "memory")
    try:
        if ingest_type == "memory":
            result = knowledge_manager.ingest_memory_candidate(
                content=payload.get("content", ""),
                timestamp=payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
                user_id=payload.get("user_id", "unknown"),
                user_name=payload.get("user_name", ""),
                source=payload.get("source", "ai_tag"),
                config=instance.config,
                channel_id=payload.get("channel_id", ""),
            )
            return result
        elif ingest_type == "world_book":
            knowledge_manager.add_world_book_entry(
                keywords=payload.get("keywords", ""),
                content=payload.get("content", ""),
                linked_user_id=payload.get("linked_user_id"),
                source=payload.get("source", "ai_tag"),
            )
            return {"status": "added"}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown ingest type: {ingest_type}")
    except Exception as e:
        logger.error("Knowledge ingest failed for bot '%s': %s", bot_id, e, exc_info=True)
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Usage tracking
# ---------------------------------------------------------------------------

@internal_router.post("/{bot_id}/usage/track")
async def usage_track(
    bot_id: str,
    payload: Dict[str, Any],
    request: Request = None,
) -> Dict[str, Any]:
    """Record token usage for a bot instance."""
    bot_id = _verify_token(request)
    manager = get_bot_manager()
    instance = manager.get(bot_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Bot not found")

    usage_tracker = instance._usage_tracker
    if not usage_tracker:
        return {"status": "no_usage_tracker"}

    try:
        await usage_tracker.record_usage(
            provider=payload.get("provider", ""),
            model=payload.get("model", ""),
            input_tokens=payload.get("input_tokens", 0),
            output_tokens=payload.get("output_tokens", 0),
            user_id=payload.get("user_id", ""),
            user_name=payload.get("user_name", ""),
            user_display_name=payload.get("user_display_name", ""),
            role_id=payload.get("role_id"),
            role_name=payload.get("role_name"),
            channel_id=payload.get("channel_id", ""),
            channel_name=payload.get("channel_name", ""),
            guild_id=payload.get("guild_id"),
            guild_name=payload.get("guild_name"),
        )
        return {"status": "recorded"}
    except Exception as e:
        logger.error("Usage tracking failed for bot '%s': %s", bot_id, e, exc_info=True)
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Interaction recording
# ---------------------------------------------------------------------------

@internal_router.post("/{bot_id}/interaction/record")
async def interaction_record(
    bot_id: str,
    payload: Dict[str, Any],
    request: Request = None,
) -> Dict[str, Any]:
    """Record an interaction (user message or bot reply)."""
    bot_id = _verify_token(request)
    try:
        from .core_logic.interaction_recorder import get_interaction_recorder
        recorder = get_interaction_recorder()

        await recorder.record_message(
            bot_id=bot_id,
            guild_id=payload.get("guild_id", "dm"),
            channel_id=payload.get("channel_id", ""),
            member_id=payload.get("member_id", "unknown"),
            member_name=payload.get("member_name", ""),
            role_id=payload.get("role_id", "default"),
            content=payload.get("content", ""),
            message_id=payload.get("message_id", ""),
            attachments=payload.get("attachments", []),
            is_bot_reply=payload.get("is_bot_reply", False),
            trigger_source=payload.get("trigger_source", "unknown"),
        )
        return {"status": "recorded"}
    except Exception as e:
        logger.error("Interaction recording failed for bot '%s': %s", bot_id, e, exc_info=True)
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Config access (read-only subset for stars)
# ---------------------------------------------------------------------------

@internal_router.get("/{bot_id}/config")
async def config_get(
    bot_id: str,
    request: Request = None,
) -> Dict[str, Any]:
    """Get a read-only subset of the bot's configuration for stars."""
    bot_id = _verify_token(request)
    manager = get_bot_manager()
    instance = manager.get(bot_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Bot not found")

    config = instance.config
    return {
        "bot_id": config.get("bot_id", bot_id),
        "bot_name": config.get("bot_name", ""),
        "bot_nickname": config.get("bot_nickname", ""),
        "system_prompt": config.get("system_prompt", ""),
        "trigger_keywords": config.get("trigger_keywords", []),
        "trigger_match_mode": config.get("trigger_match_mode", "contains"),
        "trigger_case_sensitive": config.get("trigger_case_sensitive", False),
        "role_based_config": config.get("role_based_config", {}),
        "scoped_prompts": config.get("scoped_prompts", {"guilds": {}, "channels": {}}),
        "user_options": config.get("user_options", {"enabled": False, "rules": {}}),
        "plugins": config.get("plugins", {}),
        "llm_provider": config.get("llm_provider", "openai"),
        "model_name": config.get("model_name", ""),
        "context_mode": config.get("context_mode", "channel"),
        "channel_context_settings": config.get("channel_context_settings", {"message_limit": 10, "char_limit": 4000}),
        "memory_context_settings": config.get("memory_context_settings", {"message_limit": 15, "char_limit": 6000}),
        "llm_is_multimodal": config.get("llm_is_multimodal", True),
        "auto_interject_enabled": config.get("auto_interject_enabled", False),
        "auto_interject_interval": config.get("auto_interject_interval", 20),
        "auto_interject_min_length": config.get("auto_interject_min_length", 0),
        "repeat_parrot_enabled": config.get("repeat_parrot_enabled", False),
        "repeat_parrot_threshold": config.get("repeat_parrot_threshold", 3),
        "repeat_parrot_case_sensitive": config.get("repeat_parrot_case_sensitive", False),
        "repeat_parrot_trim_whitespace": config.get("repeat_parrot_trim_whitespace", True),
        "repeat_parrot_min_length": config.get("repeat_parrot_min_length", 2),
        "repeat_parrot_require_multiple_users": config.get("repeat_parrot_require_multiple_users", True),
    }


# ---------------------------------------------------------------------------
# Persona retrieval
# ---------------------------------------------------------------------------

@internal_router.get("/{bot_id}/persona/{user_id}")
async def persona_get(
    bot_id: str,
    user_id: str,
    request: Request = None,
) -> Dict[str, Any]:
    """Get persona information for a specific user."""
    bot_id = _verify_token(request)
    manager = get_bot_manager()
    instance = manager.get(bot_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Bot not found")

    user_personas = instance.config.get("user_personas", {})
    persona = user_personas.get(user_id, {})
    return {
        "user_id": user_id,
        "persona": persona,
    }
