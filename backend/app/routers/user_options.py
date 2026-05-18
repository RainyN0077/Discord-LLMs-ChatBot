import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from .. import state
from ..dependencies import get_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_running_client(bot_id: str):
    mgr = state.bot_manager
    if not mgr:
        raise HTTPException(status_code=503, detail="Bot manager not available")
    instance = mgr._instances.get(bot_id)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found")
    if not instance.is_running():
        raise HTTPException(status_code=503, detail=f"Bot '{bot_id}' is not running")
    client = getattr(instance, '_client', None)
    if not client:
        instance2 = getattr(mgr, '_adapters', {}).get(bot_id)
        if instance2 and hasattr(instance2, 'bot'):
            client = instance2.bot
    if not client:
        raise HTTPException(status_code=503, detail=f"Bot '{bot_id}' client not connected")
    return client


@router.get("/api/bots/{bot_id}/guilds", dependencies=[Depends(get_api_key)])
async def get_bot_guilds(bot_id: str):
    client = _get_running_client(bot_id)
    guilds = []
    if hasattr(client, 'guilds'):
        for g in client.guilds:
            guilds.append({"id": str(g.id), "name": getattr(g, 'name', str(g.id))})
    return {"guilds": guilds}


@router.get("/api/bots/{bot_id}/guilds/{guild_id}/channels", dependencies=[Depends(get_api_key)])
async def get_guild_channels(bot_id: str, guild_id: str):
    client = _get_running_client(bot_id)
    guild = None
    if hasattr(client, 'get_guild'):
        guild = client.get_guild(int(guild_id))
    if not guild and hasattr(client, 'guilds'):
        guild = next((g for g in client.guilds if str(g.id) == guild_id), None)
    if not guild:
        raise HTTPException(status_code=404, detail=f"Guild '{guild_id}' not found")
    channels = []
    if hasattr(guild, 'channels'):
        for ch in guild.channels:
            ch_type = str(getattr(ch, 'type', 'text'))
            if ch_type in ('text', 'TextChannel', '0'):
                channels.append({"id": str(ch.id), "name": getattr(ch, 'name', str(ch.id)), "type": "text"})
    return {"channels": channels}


@router.get("/api/bots/{bot_id}/guilds/{guild_id}/roles", dependencies=[Depends(get_api_key)])
async def get_guild_roles(bot_id: str, guild_id: str):
    client = _get_running_client(bot_id)
    guild = None
    if hasattr(client, 'get_guild'):
        guild = client.get_guild(int(guild_id))
    if not guild and hasattr(client, 'guilds'):
        guild = next((g for g in client.guilds if str(g.id) == guild_id), None)
    if not guild:
        raise HTTPException(status_code=404, detail=f"Guild '{guild_id}' not found")
    roles = []
    if hasattr(guild, 'roles'):
        for role in guild.roles:
            roles.append({
                "id": str(role.id),
                "name": getattr(role, 'name', str(role.id)),
                "color": str(getattr(role, 'color', '#ffffff')),
            })
    return {"roles": roles}


@router.get("/api/bots/{bot_id}/guilds/{guild_id}/members", dependencies=[Depends(get_api_key)])
async def search_guild_members(
    bot_id: str,
    guild_id: str,
    query: str = Query(default="", description="Search by display_name, username, or user ID"),
    timeout_ms: int = Query(default=5000, ge=1000, le=30000, description="Search timeout in milliseconds"),
):
    client = _get_running_client(bot_id)
    guild = None
    if hasattr(client, 'get_guild'):
        guild = client.get_guild(int(guild_id))
    if not guild and hasattr(client, 'guilds'):
        guild = next((g for g in client.guilds if str(g.id) == guild_id), None)
    if not guild:
        raise HTTPException(status_code=404, detail=f"Guild '{guild_id}' not found")

    query_lower = query.strip().lower() if query else ""

    async def _search():
        members = []
        if not hasattr(guild, 'members'):
            try:
                async for member in guild.fetch_members(limit=100):
                    members.append(member)
            except Exception:
                pass
        else:
            members = list(guild.members)

        results = []
        for member in members:
            display_name = getattr(member, 'display_name', '') or ''
            username = getattr(member, 'name', '') or ''
            member_id = str(member.id)

            if not query_lower:
                match = True
            else:
                match = (
                    query_lower in display_name.lower()
                    or query_lower in username.lower()
                    or query == member_id
                )

            if match:
                results.append({
                    "id": member_id,
                    "display_name": display_name or username,
                    "username": username,
                })
                if len(results) >= 25:
                    break

        return results

    try:
        results = await asyncio.wait_for(_search(), timeout=timeout_ms / 1000.0)
        return {"members": results}
    except asyncio.TimeoutError:
        return {
            "error": "search_timeout",
            "message": "成员搜索超时，请手动输入用户 ID",
            "members": [],
        }
