import asyncio
import base64
import binascii
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends

from ..config_cache import load_config
from ..core_logic.persona_manager import determine_bot_persona, build_system_prompt
from ..core_logic.context_builder import format_user_message_for_llm
from ..dependencies import get_api_key
from ..llm_providers.factory import get_llm_provider
from .. import state
from ..models import (
    DirectChatRequest, DirectChatResponse, DirectChatDebugContext,
    DirectChatUserDebugDetail,
    TEXT_ATTACHMENT_EXTENSIONS, TEXT_ATTACHMENT_MIME_PREFIXES, TEXT_ATTACHMENT_MIME_EXACT,
    DIRECT_CHAT_MAX_ATTACHMENTS, DIRECT_CHAT_MAX_ATTACHMENT_BYTES,
    DIRECT_CHAT_MAX_TOTAL_ATTACHMENT_BYTES, DIRECT_CHAT_TEXT_PREVIEW_CHARS,
)
from ..ocr_service import (
    extract_ocr_text, get_ocr_timeout_seconds, has_ocr_model_config, is_multimodal_llm,
)
from ..utils import Stub, _async_stub, _safe_text

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_ocr_prompt_block(text: str) -> str:
    return f"[Image OCR Context]\n<ocr_output>\n{text}\n</ocr_output>"


def _build_attachment_context_block(text: str) -> str:
    return f"[Attached File Context]\n<attachment_context>\n{text}\n</attachment_context>"


def _is_text_attachment(name: str, content_type: Optional[str]) -> bool:
    normalized_type = str(content_type or "").strip().lower()
    if any(normalized_type.startswith(prefix) for prefix in TEXT_ATTACHMENT_MIME_PREFIXES):
        return True
    if normalized_type in TEXT_ATTACHMENT_MIME_EXACT:
        return True
    suffix = Path(name or "").suffix.lower()
    return suffix in TEXT_ATTACHMENT_EXTENSIONS


def _decode_direct_chat_attachments(attachments) -> List[Dict[str, Any]]:
    if not attachments:
        return []
    if len(attachments) > DIRECT_CHAT_MAX_ATTACHMENTS:
        raise HTTPException(status_code=400, detail=f"Too many attachments. Maximum is {DIRECT_CHAT_MAX_ATTACHMENTS}.")

    decoded_items: List[Dict[str, Any]] = []
    total_bytes = 0
    for item in attachments:
        raw_base64 = str(item.data_base64 or "")
        if "," in raw_base64 and raw_base64.startswith("data:"):
            raw_base64 = raw_base64.split(",", 1)[1]
        try:
            data = base64.b64decode(raw_base64, validate=True)
        except (binascii.Error, ValueError, TypeError):
            raise HTTPException(status_code=400, detail=f"Attachment '{item.name}' is not valid base64 data.")

        size = len(data)
        if size > DIRECT_CHAT_MAX_ATTACHMENT_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Attachment '{item.name}' exceeds the per-file limit.",
            )
        total_bytes += size
        if total_bytes > DIRECT_CHAT_MAX_TOTAL_ATTACHMENT_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Total attachment size exceeds the limit.",
            )

        content_type = str(item.content_type or "").strip() or "application/octet-stream"
        decoded_items.append({
            "name": _safe_text(item.name or "attachment"),
            "content_type": content_type,
            "bytes": data,
            "size": size,
            "is_image": content_type.startswith("image/"),
            "is_text": _is_text_attachment(item.name, content_type),
        })
    return decoded_items


def _build_direct_chat_attachment_context(attachments: List[Dict[str, Any]]) -> str:
    non_image_attachments = [item for item in attachments if not item.get("is_image")]
    if not non_image_attachments:
        return ""
    blocks: List[str] = []
    for item in non_image_attachments:
        header = f"[Attachment: {item['name']} | type={item['content_type']} | size={item['size']} bytes]"
        if item.get("is_text"):
            text = item["bytes"].decode("utf-8", errors="replace").strip()
            if len(text) > DIRECT_CHAT_TEXT_PREVIEW_CHARS:
                text = f"{text[:DIRECT_CHAT_TEXT_PREVIEW_CHARS].rstrip()}\n...[truncated]"
            body = text or "(empty text file)"
        else:
            body = "Binary file attached. Text preview unavailable."
        blocks.append(f"{header}\n{body}")
    return "\n\n".join(blocks)


def _build_mock_attachments(attachments: List[Dict[str, Any]]) -> list:
    mock_attachments = []
    for item in attachments:
        mock_attachment = Stub()
        mock_attachment.content_type = item.get("content_type")
        mock_attachment.filename = item.get("name")
        mock_attachments.append(mock_attachment)
    return mock_attachments


async def _augment_direct_chat_user_content(
    base_content: str,
    attachments: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    final_content = str(base_content or "")
    attachment_context = _build_direct_chat_attachment_context(attachments)
    if attachment_context:
        attachment_block = _build_attachment_context_block(attachment_context)
        final_content = f"{final_content}\n\n{attachment_block}" if final_content else attachment_block

    image_attachments = [item for item in attachments if item.get("is_image")]
    ocr_output = ""
    llm_images: List[bytes] = []
    used_multimodal_images = False

    if image_attachments:
        if is_multimodal_llm(config):
            used_multimodal_images = True
            llm_images = [item["bytes"] for item in image_attachments]
        elif has_ocr_model_config(config):
            timeout_seconds = get_ocr_timeout_seconds(config)
            try:
                extraction_task = extract_ocr_text(image_attachments, config)
                if timeout_seconds is None:
                    ocr_output, _ = await extraction_task
                else:
                    ocr_output, _ = await asyncio.wait_for(extraction_task, timeout=timeout_seconds)
                if not ocr_output.strip():
                    ocr_output = "OCR returned an empty response."
            except asyncio.TimeoutError:
                ocr_output = "OCR解析超时，你没有成功获取到图片内容"
            except Exception:
                ocr_output = "OCR解析失败，你没有成功获取到图片内容"
        else:
            ocr_output = "Images were attached, but OCR is not configured for the current text-only LLM."

    if ocr_output:
        ocr_block = _build_ocr_prompt_block(ocr_output)
        final_content = f"{final_content}\n\n{ocr_block}" if final_content else ocr_block

    return {
        "final_content": final_content,
        "attachment_context": attachment_context,
        "ocr_output": ocr_output,
        "attachment_names": [item["name"] for item in attachments],
        "llm_images": llm_images,
        "used_multimodal_images": used_multimodal_images,
    }


@router.post("/api/chat/direct", dependencies=[Depends(get_api_key)], response_model=DirectChatResponse)
async def direct_chat(request: DirectChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty.")

    config = load_config()
    if request.bot_id and state.bot_manager:
        instance = state.bot_manager.get(request.bot_id)
        if instance:
            config = instance.config
    decoded_attachments = _decode_direct_chat_attachments(request.attachments)
    if decoded_attachments and not any((msg.role or "").lower().strip() == "user" for msg in request.messages):
        raise HTTPException(status_code=400, detail="attachments require at least one user message.")

    latest_user_index = next(
        (idx for idx in range(len(request.messages) - 1, -1, -1) if (request.messages[idx].role or "").lower().strip() == "user"),
        None,
    )
    if decoded_attachments and latest_user_index != len(request.messages) - 1:
        raise HTTPException(status_code=400, detail="attachments must be sent with the latest user message.")

    llm_messages: List[Dict[str, Any]] = []
    formatted_user_messages: Optional[List[str]] = None
    debug_user_details: Optional[List[DirectChatUserDebugDetail]] = None
    llm_images: Optional[List[bytes]] = None

    if request.debug_mode:
        debug_context = request.debug_context or DirectChatDebugContext()
        try:
            user_id_int = int(debug_context.user_id)
            channel_id_int = int(debug_context.channel_id)
            guild_id_int = int(debug_context.guild_id) if debug_context.guild_id else None
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="debug_context user_id/channel_id/guild_id must be numeric strings.")

        role_config = None
        role_name = None
        if debug_context.role_id:
            role_config = config.get("role_based_config", {}).get(debug_context.role_id)
            if role_config:
                role_name = role_config.get("title")

        mock_author = Stub()
        mock_author.id = user_id_int
        mock_author.name = f"debug-user-{debug_context.user_id}"
        mock_author.display_name = mock_author.name
        mock_author.bot = False
        mock_author.roles = []

        mock_channel = Stub()
        mock_channel.id = channel_id_int

        mock_guild = None
        if guild_id_int is not None:
            mock_guild = Stub()
            mock_guild.id = guild_id_int
            mock_guild.get_member = Stub()
            mock_channel.guild = mock_guild

        mock_bot = Stub()
        mock_bot.user = Stub()
        mock_bot.user.id = 999999999999999999
        mock_bot.fetch_user = _async_stub(return_value=mock_author)

        active_directives_log: List[str] = []
        specific_persona_prompt, situational_prompt, active_directives_log = determine_bot_persona(
            config,
            str(channel_id_int),
            str(guild_id_int) if guild_id_int is not None else None,
            role_name,
            role_config,
        )

        latest_user_message = next(
            (msg for msg in reversed(request.messages) if (msg.role or "").lower().strip() == "user"),
            request.messages[-1],
        )
        prompt_message = Stub()
        prompt_message.author = mock_author
        prompt_message.channel = mock_channel
        prompt_message.guild = mock_guild
        prompt_message.content = str(latest_user_message.content or "")
        prompt_message.clean_content = str(latest_user_message.content or "")
        prompt_message.mentions = []
        prompt_message.attachments = _build_mock_attachments(decoded_attachments) if decoded_attachments else []
        prompt_message.reference = None

        system_prompt = await build_system_prompt(
            mock_bot, config, specific_persona_prompt,
            situational_prompt, prompt_message, active_directives_log,
        )
        llm_messages.append({"role": "system", "content": system_prompt})

        formatted_user_messages = []
        debug_user_details = []
        for idx, msg in enumerate(request.messages):
            role = (msg.role or "").lower().strip()
            if role not in {"user", "assistant"}:
                raise HTTPException(status_code=400, detail=f"Invalid role '{msg.role}' for debug_mode.")
            if role == "assistant":
                llm_messages.append({"role": "assistant", "content": str(msg.content or "")})
                continue

            mock_user_message = Stub()
            mock_user_message.author = mock_author
            mock_user_message.channel = mock_channel
            mock_user_message.guild = mock_guild
            mock_user_message.content = str(msg.content or "")
            mock_user_message.clean_content = str(msg.content or "")
            mock_user_message.mentions = []
            is_latest_user_turn = latest_user_index == idx
            current_attachments = decoded_attachments if is_latest_user_turn else []
            mock_user_message.attachments = _build_mock_attachments(current_attachments)
            mock_user_message.reference = None

            formatted_content = await format_user_message_for_llm(mock_user_message, mock_bot, config, role_config)
            debug_detail_data = {
                "original_content": str(msg.content or ""),
                "formatted_content": formatted_content,
                "attachment_context": "",
                "ocr_output": "",
                "attachment_names": [item["name"] for item in current_attachments],
                "used_multimodal_images": False,
            }
            if current_attachments:
                augmented = await _augment_direct_chat_user_content(formatted_content, current_attachments, config)
                formatted_content = augmented["final_content"]
                debug_detail_data = {
                    **debug_detail_data,
                    "formatted_content": formatted_content,
                    "attachment_context": augmented["attachment_context"],
                    "ocr_output": augmented["ocr_output"],
                    "used_multimodal_images": augmented["used_multimodal_images"],
                }
                if augmented["llm_images"]:
                    llm_images = augmented["llm_images"]

            formatted_user_messages.append(formatted_content)
            llm_messages.append({"role": "user", "content": formatted_content})
            debug_user_details.append(DirectChatUserDebugDetail(**debug_detail_data))
    else:
        has_custom_system = any((msg.role or "").lower().strip() == "system" for msg in request.messages)
        if request.include_system_prompt and not has_custom_system and config.get("system_prompt"):
            llm_messages.append({"role": "system", "content": str(config.get("system_prompt", ""))})

        for idx, msg in enumerate(request.messages):
            role = (msg.role or "").lower().strip()
            if role not in {"system", "user", "assistant"}:
                raise HTTPException(status_code=400, detail=f"Invalid role '{msg.role}'.")
            content = str(msg.content or "")
            if role == "user" and latest_user_index == idx and decoded_attachments:
                augmented = await _augment_direct_chat_user_content(content, decoded_attachments, config)
                content = augmented["final_content"]
                if augmented["llm_images"]:
                    llm_images = augmented["llm_images"]
            llm_messages.append({"role": role, "content": content})

    runtime_config = dict(config)
    runtime_config["stream_response"] = False

    try:
        llm_provider = get_llm_provider(runtime_config)
        full_response = ""
        usage_data: Optional[Dict[str, int]] = None
        async for response_type, data in llm_provider.get_response_stream(llm_messages, images=llm_images):
            if response_type == "final":
                full_response = str(data)
            elif response_type == "usage" and isinstance(data, dict):
                usage_data = data

        if full_response.startswith("LLM_PROVIDER_ERROR:"):
            raise HTTPException(status_code=500, detail=full_response)

        return {
            "success": True,
            "response": full_response,
            "usage": usage_data,
            "provider": str(config.get("llm_provider", "openai")),
            "model": str(config.get("model_name", "")),
            "debug_mode": bool(request.debug_mode),
            "formatted_user_messages": formatted_user_messages if request.debug_mode else None,
            "debug_user_details": debug_user_details if request.debug_mode else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Direct chat failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Direct chat failed. Check backend logs for details.")
