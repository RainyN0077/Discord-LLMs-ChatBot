import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends

from ..config_cache import load_config, save_config
from ..dependencies import get_api_key
from ..feature_flags import is_flag_enabled
from ..models import PluginTriggerRequest
from ..utils import _execute_http_request, Stub

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_plugin_registry(bot_id: Optional[str] = None):
    """获取指定 Bot 或第一个 Bot 的 PluginRegistry.

    Args:
        bot_id: Bot ID，为 None 时返回第一个使用 PluginRegistry 的 Bot

    Returns:
        PluginRegistry 实例

    Raises:
        HTTPException: 未找到符合条件的 Bot 或未使用 PluginRegistry
    """
    from ..app_context import AppContext
    from ..ports.plugin_registry import PluginRegistry

    ctx = AppContext.get()
    manager = ctx.bot_manager

    if bot_id:
        instance = manager.get(bot_id)
        if not instance:
            raise HTTPException(status_code=404, detail=f"Bot '{bot_id}' not found.")
        registry = getattr(instance, "_plugin_manager", None)
        if not isinstance(registry, PluginRegistry):
            raise HTTPException(status_code=400, detail="Bot is not using PluginRegistry.")
        return registry

    # 默认返回第一个使用 PluginRegistry 的 Bot
    for inst in manager.get_all_instances().values():
        registry = getattr(inst, "_plugin_manager", None)
        if isinstance(registry, PluginRegistry):
            return registry

    raise HTTPException(status_code=404, detail="No Bot using PluginRegistry found.")


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
    from .. import state
    from ..config_bridge import generate_env_file
    config = load_config()
    if plugin_name not in config.get("plugins", {}):
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found.")

    config["plugins"][plugin_name] = plugin_data
    save_config(config)

    generate_env_file()

    if state.bot_manager:
        for bot_id in list(state.bot_manager._instances.keys()):
            await state.bot_manager.restart(bot_id)

    logger.info(f"Plugin '{plugin_name}' configuration updated and bots restarted.")
    return {"message": f"Plugin '{plugin_name}' configuration updated and bots restarted."}


@router.post("/api/plugins/{plugin_name}/reload", dependencies=[Depends(get_api_key)])
async def reload_plugin(plugin_name: str, body: Optional[Dict[str, Any]] = None):
    """热加载/重新加载指定插件.

    仅支持 PluginRegistry 模式（USE_ENHANCED_PLUGIN_REGISTRY=True）。

    Args:
        plugin_name: 插件名称
        body: 可选请求体，支持 bot_id 和 config 覆盖

    Returns:
        加载结果信息
    """
    if not is_flag_enabled("USE_ENHANCED_PLUGIN_REGISTRY"):
        raise HTTPException(
            status_code=501,
            detail="Plugin hot reload requires USE_ENHANCED_PLUGIN_REGISTRY feature flag.",
        )

    registry = _resolve_plugin_registry((body or {}).get("bot_id"))

    # 卸载旧实例
    old = registry.get(plugin_name)
    if old:
        registry.unregister(plugin_name)

    # 重新加载
    config = load_config()
    plugins_config = dict(config.get("plugins", {}))
    if plugin_name not in plugins_config:
        plugins_config[plugin_name] = {"enabled": True}

    # 使用 BotInstance 的 llm_caller 重新发现
    from ..app_context import AppContext
    ctx = AppContext.get()
    bot_id = (body or {}).get("bot_id")
    instance = ctx.bot_manager.get(bot_id) if bot_id else None
    if instance is None:
        for inst in ctx.bot_manager.get_all_instances().values():
            if getattr(inst, "_plugin_manager", None) is registry:
                instance = inst
                break

    llm_caller = getattr(instance, "_get_llm_response", None) if instance else None
    registry.discover_and_load(plugins_config, llm_caller)

    new_plugin = registry.get(plugin_name)
    if not new_plugin:
        raise HTTPException(
            status_code=404,
            detail=f"Plugin '{plugin_name}' could not be reloaded.",
        )

    return {
        "message": f"Plugin '{plugin_name}' reloaded.",
        "name": plugin_name,
        "tools_count": len(new_plugin.get_tools()),
        "status": "loaded",
    }


@router.post("/api/plugins/{plugin_name}/unload", dependencies=[Depends(get_api_key)])
async def unload_plugin(plugin_name: str, body: Optional[Dict[str, Any]] = None):
    """热卸载指定插件.

    仅支持 PluginRegistry 模式（USE_ENHANCED_PLUGIN_REGISTRY=True）。

    Args:
        plugin_name: 插件名称
        body: 可选请求体，支持 bot_id

    Returns:
        卸载结果信息
    """
    if not is_flag_enabled("USE_ENHANCED_PLUGIN_REGISTRY"):
        raise HTTPException(
            status_code=501,
            detail="Plugin hot unload requires USE_ENHANCED_PLUGIN_REGISTRY feature flag.",
        )

    registry = _resolve_plugin_registry((body or {}).get("bot_id"))

    old = registry.get(plugin_name)
    if not old:
        raise HTTPException(
            status_code=404,
            detail=f"Plugin '{plugin_name}' not found in registry.",
        )

    registry.unregister(plugin_name)
    return {
        "message": f"Plugin '{plugin_name}' unloaded.",
        "name": plugin_name,
        "status": "unloaded",
    }
