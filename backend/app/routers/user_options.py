import asyncio
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Depends

from .. import state
from ..dependencies import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter()

DISCORD_API_BASE = "https://discord.com/api/v10"


def _get_bot_instance(bot_id: str):
    mgr = state.bot_manager
    if not mgr:
        raise HTTPException(status_code=503, detail="Bot manager not available")
    instance = mgr._instances.get(bot_id)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")
    return instance


def _get_bot_token(bot_id: str) -> str:
    instance = _get_bot_instance(bot_id)
    if not instance.is_running():
        raise HTTPException(status_code=503, detail=f"Bot '{bot_id}' is not running")
    token = instance.config.get("discord_token", "")
    if not token:
        raise HTTPException(status_code=503, detail=f"Bot '{bot_id}' has no discord_token configured")
    return token


async def _discord_rest_get(token: str, path: str) -> dict:
    headers = {"Authorization": f"Bot {token}"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{DISCORD_API_BASE}{path}", headers=headers)
        if resp.status_code == 429:
            raise HTTPException(status_code=429, detail="Discord rate limited")
        if resp.status_code >= 400:
            raise HTTPException(status_code=503, detail=f"Discord API error {resp.status_code}")
        return resp.json()


@router.get("/api/bots/{bot_id}/guilds", dependencies=[Depends(get_api_key)])
async def get_bot_guilds(bot_id: str):
    token = _get_bot_token(bot_id)
    data = await _discord_rest_get(token, "/users/@me/guilds")
    guilds = []
    for g in (data if isinstance(data, list) else []):
        guilds.append({"id": str(g.get("id")), "name": g.get("name", str(g.get("id")))})
    return {"guilds": guilds}


@router.get("/api/bots/{bot_id}/guilds/{guild_id}/channels", dependencies=[Depends(get_api_key)])
async def get_guild_channels(bot_id: str, guild_id: str):
    token = _get_bot_token(bot_id)
    data = await _discord_rest_get(token, f"/guilds/{guild_id}/channels")
    channels = []
    for ch in (data if isinstance(data, list) else []):
        if ch.get("type", 0) == 0:
            channels.append({"id": str(ch.get("id")), "name": ch.get("name", str(ch.get("id")))})
    return {"channels": channels}


@router.get("/api/bots/{bot_id}/guilds/{guild_id}/roles", dependencies=[Depends(get_api_key)])
async def get_guild_roles(bot_id: str, guild_id: str):
    token = _get_bot_token(bot_id)
    data = await _discord_rest_get(token, f"/guilds/{guild_id}/roles")
    roles = []
    for r in (data if isinstance(data, list) else []):
        roles.append({
            "id": str(r.get("id")),
            "name": r.get("name", str(r.get("id"))),
            "position": r.get("position", 0),
            "color": r.get("color", 0),
        })
    return {"roles": roles}


@router.get("/api/bots/{bot_id}/guilds/{guild_id}/members", dependencies=[Depends(get_api_key)])
async def search_guild_members(
    bot_id: str,
    guild_id: str,
    query: Optional[str] = "",
    timeout_ms: int = Query(5000, alias="timeout_ms"),
):
    token = _get_bot_token(bot_id)
    limit = 1000
    path = f"/guilds/{guild_id}/members?limit={limit}"
    if query:
        from urllib.parse import quote
        path = f"/guilds/{guild_id}/members/search?query={quote(query)}&limit=100"
    real_timeout = min(max(timeout_ms, 1000), 30000) / 1000.0
    try:
        headers = {"Authorization": f"Bot {token}"}
        async with httpx.AsyncClient(timeout=real_timeout) as client:
            resp = await client.get(f"{DISCORD_API_BASE}{path}", headers=headers)
            if resp.status_code == 429:
                return {"error": "rate_limited", "message": "Discord rate limited", "members": []}
            if resp.status_code >= 400:
                return {"error": "api_error", "message": f"Discord API error {resp.status_code}", "members": []}
            data = resp.json()
        members = []
        items = data if isinstance(data, list) else data.get("members", data if isinstance(data, list) else [])
        for m in items:
            user = m.get("user", m)
            members.append({
                "id": str(user.get("id")),
                "username": user.get("username", ""),
                "display_name": m.get("nick") or user.get("global_name") or user.get("username", ""),
                "roles": [str(r) for r in m.get("roles", [])],
            })
        return {"members": members}
    except asyncio.TimeoutError:
        return {"error": "search_timeout", "message": "成员搜索超时，请手动输入用户 ID", "members": []}


@router.get("/api/bots/{bot_id}/diagnostics", dependencies=[Depends(get_api_key)])
async def get_bot_diagnostics(bot_id: str):
    instance = _get_bot_instance(bot_id)
    is_running = instance.is_running()
    guild_count = 0
    intents = {}
    warnings = []
    config_intents = instance.config.get("discord_intents", {})
    # Intents are now determined from config only (no NoneBot driver to introspect)
    if config_intents:
        intents = {k: bool(v) for k, v in config_intents.items() if k in ("guilds", "guild_members", "message_content")}
        intents.setdefault("guilds", config_intents.get("guilds", False))
        intents.setdefault("guild_members", config_intents.get("members") or config_intents.get("guild_members", False))
        intents.setdefault("message_content", config_intents.get("message_content", False))
    if not intents:
        intents = {"guild_members": False, "message_content": False, "guilds": False}
    if is_running:
        try:
            token = instance.config.get("discord_token", "")
            if token:
                data = await _discord_rest_get(token, "/users/@me/guilds")
                guild_count = len(data) if isinstance(data, list) else 0
        except Exception:
            pass
    if not is_running:
        warnings.append("Bot 未运行，无法获取服务器列表")
    if is_running and not intents.get("guild_members"):
        warnings.append("GUILD_MEMBERS intent 未启用，无法获取成员列表")
    return {
        "online": is_running,
        "guild_count": guild_count,
        "intents": intents,
        "warnings": warnings,
    }
