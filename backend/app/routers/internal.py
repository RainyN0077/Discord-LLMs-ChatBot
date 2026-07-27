"""Internal API Router.

Provides endpoints for AstrBot stars to communicate with the management layer.
All endpoints are authenticated via a shared internal secret token (X-Internal-Token header).

These are NOT exposed to the frontend — they are for inter-process communication
between AstrBot subprocesses and the FastAPI management server.
"""

import asyncio
import logging
import secrets
import types
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header, Request

from ..bot_manager import BotManager
from ..state import get_bot_manager
from ..core_shared import token_calculator, get_redis

logger = logging.getLogger(__name__)

internal_router = APIRouter(prefix="/internal", tags=["internal"])


def _verify_token(request: Request) -> str:
    """Verify the X-Internal-Token header against the bot's derived internal token.

    The internal token is derived from ``api_secret_key`` by appending
    ``":internal"`` (see ``astrbot_config_gen.py``).  This isolates IPC
    credentials from the external management API key so they can be
    rotated independently.

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

    # Derive expected token from api_secret_key (must match config_gen)
    api_key = instance.config.get("api_secret_key", "")
    expected = api_key + ":internal" if api_key else ""
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
        return {"memories": []}


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
            result = await knowledge_manager.ingest_memory_candidate(
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
            await knowledge_manager.add_world_book_entry(
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
        return {"status": "error"}


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
        return {"status": "error"}


# ---------------------------------------------------------------------------
# Plugin bridge (legacy plugin message processing)
# ---------------------------------------------------------------------------

@internal_router.post("/{bot_id}/plugins/process_message")
async def plugins_process_message(
    bot_id: str,
    payload: Dict[str, Any],
    request: Request = None,
) -> Dict[str, Any]:
    """Process a message through the legacy PluginManager.

    Delegates to ``PluginManager.process_message()`` which runs all loaded
    legacy plugins (e.g. memory_plugin, configurable plugins) in the
    management layer.

    Request Body:
        message_content (str): The message text.
        user_id (str): Discord snowflake of the sender.
        channel_id (str): Channel snowflake.
        guild_id (str | null): Guild snowflake (null for DMs).
        author_name (str): Sender's username.
        author_display_name (str): Sender's display/nickname.

    Response:
        result (str): ``consumed`` | ``append`` | ``none``.
        append_blocks (list[str] | null): Append-mode block content, if any.
    """
    bot_id = _verify_token(request)
    manager = get_bot_manager()
    instance = manager.get(bot_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Bot not found")

    plugin_manager = getattr(instance, "_plugin_manager", None)
    if not plugin_manager:
        logger.debug("No plugin_manager for bot '%s'", bot_id)
        return {"result": "none", "append_blocks": None}

    # Build a lightweight namespace object that mimicks the subset of
    # discord.Message attributes that legacy plugins access.
    msg = types.SimpleNamespace(
        author=types.SimpleNamespace(
            id=payload.get("user_id", ""),
            name=payload.get("author_name", ""),
            display_name=payload.get("author_display_name", ""),
        ),
        channel=types.SimpleNamespace(
            id=payload.get("channel_id", ""),
        ),
        guild=(
            types.SimpleNamespace(id=payload["guild_id"])
            if payload.get("guild_id")
            else types.SimpleNamespace(id="dm")
        ),
        content=payload.get("message_content", ""),
        mentions=[],
    )

    try:
        result = await plugin_manager.process_message(msg, instance.config)
    except Exception as e:
        logger.error(
            "Plugin process_message failed for bot '%s': %s",
            bot_id, e, exc_info=True,
        )
        return {"result": "none", "append_blocks": None}

    if result is True:
        return {"result": "consumed", "append_blocks": None}

    if isinstance(result, tuple) and result[0] == "append":
        return {"result": "append", "append_blocks": result[1]}

    return {"result": "none", "append_blocks": None}


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
        return {"status": "error"}


# ---------------------------------------------------------------------------
# Debug capture (for Debugger WebUI)
# ---------------------------------------------------------------------------

@internal_router.post("/{bot_id}/debug/capture")
async def debug_capture(
    bot_id: str,
    payload: Dict[str, Any],
    request: Request = None,
) -> Dict[str, Any]:
    """Store a debug capture record from the AstrBot pipeline.

    Intended for use by the debug_capture Star (Phase 2 IPC upload).
    Phase 1 uses local in-memory storage directly; this endpoint is
    reserved for Phase 2 when captures are uploaded from the Star.

    Request Body — fields matching the DebugCapture star's capture dict:
        trigger_message_id (str)
        channel_id (str)
        guild_id (str | None)
        user_id (str)
        user_name (str)
        user_display_name (str)
        trigger_sources (str | list)
        plugin_outputs (list)
        raw_user_message (str)
        formatted_user_request (str)
        system_prompt (str)
        history_for_llm (list)
        llm_messages (list)
        intermediate_llm_responses (list)
        raw_llm_response (str)
        cleaned_llm_response (str)
        usage (dict)
        provider (str)
        model (str)

    Response:
        {"status": "captured", "capture_id": "..."}
    """
    bot_id = _verify_token(request)
    try:
        from ..debug_capture_store import add_capture

        record = await add_capture(payload)
        return {"status": "captured", "capture_id": record.get("id", "")}
    except ImportError:
        return {"status": "not_implemented", "capture_id": ""}
    except Exception as e:
        logger.error(
            "Debug capture failed for bot '%s': %s", bot_id, e, exc_info=True
        )
        return {"status": "error"}


@internal_router.get("/{bot_id}/debug/captures")
async def debug_captures_list(
    bot_id: str,
    channel_id: str = "",
    limit: int = 20,
    request: Request = None,
) -> Dict[str, Any]:
    """Retrieve debug captures for the Debugger WebUI.

    Query Parameters:
        channel_id (str, optional): Filter by channel snowflake.
        limit (int, default 20): Max captures to return (1-100).

    Response:
        {"captures": [...]}
    """
    bot_id = _verify_token(request)
    try:
        from ..debug_capture_store import list_captures

        rows = await list_captures(limit=limit, channel_id=channel_id or None)
        return {"captures": rows}
    except ImportError:
        # TODO: fallback to local-memory access via DebugCapture.get_captures()
        # when debug_capture_store is unavailable (Phase 2).
        return {"captures": []}
    except Exception as e:
        logger.error(
            "Debug captures list failed for bot '%s': %s", bot_id, e, exc_info=True
        )
        return {"captures": []}


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
