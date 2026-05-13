import json
import logging

from fastapi import APIRouter, HTTPException, Depends

from ..config_cache import load_config, save_config
from ..dependencies import get_api_key
from ..models import PluginTriggerRequest
from ..utils import _execute_http_request, Stub

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/plugins/trigger", dependencies=[Depends(get_api_key)])
async def trigger_plugin_endpoint(request: PluginTriggerRequest):
    config = load_config()
    plugins_dict = config.get("plugins", {})
    target_plugin = next((p for p in plugins_dict.values() if p.get("name") == request.plugin_name and p.get("enabled")), None)
    if not target_plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{request.plugin_name}' not found or is disabled.")

    mock_message = Stub()
    mock_message.content = request.message_content or ""
    mock_author = Stub()
    mock_author.id = request.author_id or 0
    mock_author.name = request.author_name or "API"
    mock_author.display_name = request.author_display_name or request.author_name or "API"
    mock_message.author = mock_author
    mock_channel = Stub()
    mock_channel.id = request.channel_id or "0"
    mock_message.channel = mock_channel
    mock_guild = Stub()
    mock_guild.id = request.guild_id or "0"
    mock_message.guild = mock_guild
    args_str = json.dumps(request.args)
    action_type = target_plugin.get('action_type')

    if action_type == 'http_request':
        result = await _execute_http_request(target_plugin, mock_message, args_str)
        try:
            return json.loads(result) if result else {}
        except json.JSONDecodeError:
            return {"result": result}

    raise HTTPException(status_code=400, detail=f"Unsupported action type '{action_type}'.")


@router.get("/api/plugins/{plugin_name}/config", dependencies=[Depends(get_api_key)])
async def get_plugin_config_endpoint(plugin_name: str):
    config = load_config()
    plugin_config = config.get("plugins", {}).get(plugin_name)
    if not plugin_config:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found.")
    return plugin_config


@router.post("/api/plugins/{plugin_name}/config", dependencies=[Depends(get_api_key)])
async def update_plugin_config_endpoint(plugin_name: str, plugin_data: dict):
    import asyncio
    from ..bot import run_bot
    from .. import state
    config = load_config()
    if plugin_name not in config.get("plugins", {}):
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found.")

    config["plugins"][plugin_name] = plugin_data
    save_config(config)

    if state.bot_task and not state.bot_task.done():
        state.bot_task.cancel()
        try:
            await state.bot_task
        except asyncio.CancelledError:
            pass

    loop = asyncio.get_event_loop()
    state.bot_task = loop.create_task(run_bot(state.MEMORY_CUTOFFS))

    logger.info(f"Plugin '{plugin_name}' configuration updated and bot restarted.")
    return {"message": f"Plugin '{plugin_name}' configuration updated and bot restarted."}
