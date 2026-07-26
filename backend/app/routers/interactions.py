import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from ..core_logic.interaction_recorder import get_interaction_recorder, _get_date_path
from ..config_cache import DATA_DIR
from ..dependencies import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/interactions/{bot_id}/tree", dependencies=[Depends(get_api_key)])
async def get_interaction_tree(
    bot_id: str,
    guild_id: Optional[str] = None,
    role_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    member_id: Optional[str] = None,
):
    recorder = get_interaction_recorder()
    results = await recorder.list_tree(bot_id, guild_id=guild_id, role_id=role_id, channel_id=channel_id, member_id=member_id)
    return {"items": results}


@router.get("/api/interactions/{bot_id}/members", dependencies=[Depends(get_api_key)])
async def get_recorded_members(bot_id: str, guild_id: str = Query(...)):
    recorder = get_interaction_recorder()
    members = await recorder.list_members(bot_id, guild_id)
    return {"members": members}


@router.get("/api/interactions/{bot_id}/messages", dependencies=[Depends(get_api_key)])
async def get_interaction_messages(
    bot_id: str,
    guild_id: str = Query(...),
    role_id: str = Query(...),
    channel_id: str = Query(...),
    member_id: str = Query(...),
    date: str = Query(...),
):
    recorder = get_interaction_recorder()
    messages = await recorder.read_messages(bot_id, guild_id, role_id, channel_id, member_id, date)
    return {"messages": messages}


@router.get("/api/interactions/{bot_id}/images", dependencies=[Depends(get_api_key)])
async def get_interaction_images(
    bot_id: str,
    guild_id: str = Query(...),
    role_id: str = Query(...),
    channel_id: str = Query(...),
    member_id: str = Query(...),
    date: str = Query(...),
):
    date_path = _get_date_path(bot_id, guild_id, role_id, channel_id, member_id, date)
    images_dir = date_path / "images"
    images = []
    if images_dir.exists():
        for img_file in images_dir.iterdir():
            if img_file.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                images.append({
                    "filename": img_file.name,
                    "size": img_file.stat().st_size,
                })
    return {"images": images}


@router.get("/api/interactions/{bot_id}/image-file", dependencies=[Depends(get_api_key)])
async def get_interaction_image_file(
    bot_id: str,
    guild_id: str = Query(...),
    role_id: str = Query(...),
    channel_id: str = Query(...),
    member_id: str = Query(...),
    date: str = Query(...),
    filename: str = Query(...),
):
    from fastapi.responses import FileResponse
    date_path = _get_date_path(bot_id, guild_id, role_id, channel_id, member_id, date)
    img_path = date_path / "images" / filename
    if not img_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(img_path))


@router.get("/api/interactions/{bot_id}/usage", dependencies=[Depends(get_api_key)])
async def get_interaction_usage(bot_id: str):
    from ..config_cache import load_config
    config = load_config()
    ih_config = config.get("interaction_history", {})
    max_bytes = ih_config.get("max_storage_bytes", 524288000)
    recorder = get_interaction_recorder()
    used_bytes = await recorder.get_disk_usage(bot_id)
    return {
        "used_bytes": used_bytes,
        "max_bytes": max_bytes,
        "percent": round(used_bytes / max_bytes * 100, 2) if max_bytes > 0 else 0,
    }


@router.delete("/api/interactions/{bot_id}/delete", dependencies=[Depends(get_api_key)])
async def delete_interaction_records(
    bot_id: str,
    guild_id: Optional[str] = None,
    channel_id: Optional[str] = None,
    member_id: Optional[str] = None,
    date: Optional[str] = None,
):
    recorder = get_interaction_recorder()
    deleted = await recorder.delete_records(bot_id, guild_id=guild_id, channel_id=channel_id, member_id=member_id, date_str=date)
    return {"deleted": deleted}


@router.post("/api/interactions/{bot_id}/prune", dependencies=[Depends(get_api_key)])
async def prune_interaction_records(bot_id: str):
    from ..config_cache import load_config
    config = load_config()
    ih_config = config.get("interaction_history", {})
    max_bytes = ih_config.get("max_storage_bytes", 524288000)
    recorder = get_interaction_recorder()
    pruned = await recorder.prune_oldest(bot_id, max_bytes)
    return {"pruned": pruned}


@router.post("/api/interactions/{bot_id}/context", dependencies=[Depends(get_api_key)])
async def reconstruct_context(
    bot_id: str,
    guild_id: str = Query(...),
    role_id: str = Query(...),
    channel_id: str = Query(...),
    member_id: str = Query(...),
    date: str = Query(...),
):
    from ..config_cache import load_config
    from ..core_logic.persona_manager import build_system_prompt
    from ..core_logic.context_builder import format_user_message_for_llm
    from ..utils import Stub

    config = load_config()
    all_configs = config

    bot_config = None
    if isinstance(config, dict) and "bots" in config:
        bot_config = config.get("bots", {}).get(bot_id)
    if not bot_config:
        bot_configs = config.get("bot_configs", getattr(config, "bot_configs", None))
        if bot_configs and isinstance(bot_configs, dict):
            bot_config = bot_configs.get(bot_id)
    if not bot_config:
        bot_config = config

    recorder = get_interaction_recorder()
    messages = await recorder.read_messages(bot_id, guild_id, role_id, channel_id, member_id, date)
    if not messages:
        return {"context": None, "message": "No messages found for the specified parameters"}

    mock_author = Stub()
    mock_author.id = int(member_id) if member_id.lstrip('-').isdigit() else 1
    mock_author.name = member_id
    mock_author.display_name = member_id
    mock_author.roles = []

    mock_channel = Stub()
    mock_channel.id = int(channel_id) if channel_id.lstrip('-').isdigit() else 1

    mock_guild = Stub()
    mock_guild.id = int(guild_id) if guild_id.lstrip('-').isdigit() else 1
    mock_channel.guild = mock_guild

    mock_client = Stub()

    mock_message = Stub()
    mock_message.author = mock_author
    mock_message.channel = mock_channel
    mock_message.guild = mock_guild
    mock_message.content = ""
    mock_message.mentions = []

    for msg in messages:
        if msg.get("content"):
            mock_message.content = msg.get("content", "")
            break

    try:
        system_prompt = await build_system_prompt(
            None, bot_config, "", "", mock_message, []
        )
    except Exception:
        system_prompt = "(Context reconstruction failed — insufficient config data)"

    formatted_messages = []
    for msg in messages:
        try:
            msg_author = Stub(
                id=int(msg.get("author_id", 0)) if str(msg.get("author_id", "0")).lstrip('-').isdigit() else 0,
                name=msg.get("author_name", "") or "",
                display_name=msg.get("author_name", "") or "",
                bot=False,
            )
            msg_attachments = []
            for att in (msg.get("attachments") or []):
                mock_att = Stub()
                mock_att.content_type = att.get("content_type", "") if isinstance(att, dict) else ""
                msg_attachments.append(mock_att)

            mock_msg = Stub(
                author=msg_author,
                channel=mock_channel,
                guild=mock_guild,
                content=msg.get("content", ""),
                mentions=[],
                attachments=msg_attachments,
                reference=None,
            )
            formatted_content = await format_user_message_for_llm(
                mock_msg, mock_client, bot_config, None,
            )
        except Exception:
            formatted_content = msg.get("content", "")

        formatted_messages.append({
            "timestamp": msg.get("timestamp"),
            "author_id": msg.get("author_id"),
            "author_name": msg.get("author_name"),
            "formatted_content": formatted_content,
            "original_content": msg.get("content"),
        })

    return {
        "system_prompt": system_prompt,
        "messages": formatted_messages,
    }
