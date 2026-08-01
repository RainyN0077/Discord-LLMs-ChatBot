import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends

from ..bot import strip_dsml_tool_blocks, strip_thinking_sections
from ..config_cache import load_config
from ..core_logic.persona_manager import determine_bot_persona, build_system_prompt
from ..core_logic.context_builder import format_user_message_for_llm
from ..debug_capture_store import list_captures as list_debug_captures, get_capture as get_debug_capture
from ..dependencies import get_api_key
from ..llm_providers.factory import get_provider_pool
from ..models import (
    DebuggerRequest, DebugCaptureSummary, DebugCaptureDetail,
    DebugSanitizeRequest, DebugSanitizeResponse,
)
from ..utils import Stub, _async_stub, _safe_text, _safe_str_list, _safe_dict_list, _json_safe

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_debug_config(bot_id: Optional[str]) -> dict:
    """解析调试所用的 Bot 配置.

    Args:
        bot_id: 指定 Bot ID 时使用该 Bot 的配置；缺省时回退到全局配置（向后兼容）。

    Returns:
        配置字典（dict 形式）.

    Raises:
        HTTPException: Bot 不存在（404）或 Bot 管理器未初始化（503）
    """
    if not bot_id:
        return load_config()

    from .. import state
    mgr = state.bot_manager
    if mgr is None:
        raise HTTPException(status_code=503, detail="Bot manager not initialized")
    instance = mgr.get(bot_id)
    if instance is None:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found.")
    return instance.config


@router.post("/api/debug/simulate", dependencies=[Depends(get_api_key)])
async def simulate_debugger_run(request: DebuggerRequest):
    config = _resolve_debug_config(request.bot_id)

    role_config = None
    role_name = None
    if request.role_id:
        role_config = config.get("role_based_config", {}).get(request.role_id)
        if role_config:
            role_name = role_config.get("title")

    active_directives_log: List[str] = []
    specific_persona_prompt, situational_prompt, active_directives_log = determine_bot_persona(
        config,
        request.channel_id,
        request.guild_id,
        role_name,
        role_config,
    )

    mock_author = Stub()
    mock_author.id = int(request.user_id)
    mock_author.name = f"debug-user-{request.user_id}"
    mock_author.display_name = mock_author.name
    mock_author.roles = []

    mock_channel = Stub()
    mock_channel.id = int(request.channel_id)

    mock_guild = None
    if request.guild_id:
        mock_guild = Stub()
        mock_guild.id = int(request.guild_id)
        mock_channel.guild = mock_guild

    mock_message = Stub()
    mock_message.author = mock_author
    mock_message.channel = mock_channel
    mock_message.guild = mock_guild
    mock_message.content = request.message_content
    mock_message.clean_content = request.message_content
    mock_message.mentions = []
    mock_message.attachments = []
    mock_message.reference = None

    mock_bot = Stub()
    mock_bot.fetch_user = _async_stub(return_value=mock_author)

    system_prompt = await build_system_prompt(
        mock_bot,
        config,
        specific_persona_prompt,
        situational_prompt,
        mock_message,
        active_directives_log,
    )
    formatted_content = await format_user_message_for_llm(mock_message, mock_bot, config, role_config)

    llm_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": formatted_content},
    ]

    try:
        pool = get_provider_pool()
        generator = await pool.execute(config, llm_messages)
        llm_response = ""
        async for response_type, data in generator:
            if response_type in ("partial", "final"):
                llm_response = str(data)
    except RuntimeError:
        logger.warning("Debug simulate rejected by provider pool")
        raise HTTPException(status_code=503, detail="LLM provider is temporarily unavailable. Please retry later.")

    return {
        "generated_system_prompt": system_prompt,
        "formatted_user_request": formatted_content,
        "llm_response": llm_response,
        "active_directives_log": active_directives_log,
    }


@router.get("/api/debug/captures", dependencies=[Depends(get_api_key)], response_model=List[DebugCaptureSummary])
async def get_debug_captures(limit: int = 20, channel_id: Optional[str] = None):
    rows = await list_debug_captures(limit=limit, channel_id=channel_id)
    return [
        {
            "id": str(row.get("id", "")),
            "captured_at": str(row.get("captured_at", "")),
            "trigger_message_id": str(row.get("trigger_message_id", "")),
            "channel_id": str(row.get("channel_id", "")),
            "guild_id": row.get("guild_id"),
            "user_id": str(row.get("user_id", "")),
            "user_name": str(row.get("user_name", "")),
            "user_display_name": str(row.get("user_display_name", "")),
            "trigger_sources": _safe_str_list(row.get("trigger_sources")),
            "raw_user_message": str(row.get("raw_user_message", "")),
            "provider": str(row.get("provider", "")),
            "model": str(row.get("model", "")),
        }
        for row in rows
    ]


@router.get("/api/debug/captures/{capture_id}", dependencies=[Depends(get_api_key)], response_model=DebugCaptureDetail)
async def get_debug_capture_detail(capture_id: str):
    row = await get_debug_capture(capture_id)
    if not row:
        raise HTTPException(status_code=404, detail="Capture not found.")

    safe_history = _safe_dict_list(row.get("history_for_llm", []))
    safe_messages = _safe_dict_list(row.get("llm_messages", []))
    safe_usage = _json_safe(row.get("usage"))

    return {
        "id": _safe_text(row.get("id", "")),
        "captured_at": _safe_text(row.get("captured_at", "")),
        "trigger_message_id": _safe_text(row.get("trigger_message_id", "")),
        "channel_id": _safe_text(row.get("channel_id", "")),
        "guild_id": _safe_text(row.get("guild_id", "")) if row.get("guild_id") is not None else None,
        "user_id": _safe_text(row.get("user_id", "")),
        "user_name": _safe_text(row.get("user_name", "")),
        "user_display_name": _safe_text(row.get("user_display_name", "")),
        "trigger_sources": _safe_str_list(row.get("trigger_sources")),
        "raw_user_message": _safe_text(row.get("raw_user_message", "")),
        "provider": _safe_text(row.get("provider", "")),
        "model": _safe_text(row.get("model", "")),
        "plugin_outputs": _safe_str_list(row.get("plugin_outputs")),
        "formatted_user_request": _safe_text(row.get("formatted_user_request", "")),
        "system_prompt": _safe_text(row.get("system_prompt", "")),
        "history_for_llm": safe_history,
        "llm_messages": safe_messages,
        "intermediate_llm_responses": _safe_str_list(row.get("intermediate_llm_responses")),
        "raw_llm_response": _safe_text(row.get("raw_llm_response", "")),
        "cleaned_llm_response": _safe_text(row.get("cleaned_llm_response", "")),
        "usage": safe_usage if isinstance(safe_usage, dict) else None,
    }


@router.post("/api/debug/sanitize", dependencies=[Depends(get_api_key)], response_model=DebugSanitizeResponse)
async def sanitize_debug_text(request: DebugSanitizeRequest):
    original_text = _safe_text(request.text)
    sanitized = strip_dsml_tool_blocks(original_text)
    sanitized = strip_thinking_sections(sanitized)
    return {
        "original_text": original_text,
        "sanitized_text": sanitized,
    }
