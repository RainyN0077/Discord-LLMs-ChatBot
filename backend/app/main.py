# backend/app/main.py
import asyncio
import json
import os
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from collections import deque
import secrets
from unittest.mock import MagicMock
import discord

from fastapi import FastAPI, HTTPException, Response, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, ValidationError

from .bot import run_bot, get_llm_response
from .utils import _execute_http_request, _format_with_placeholders
from .core_logic.persona_manager import determine_bot_persona, build_system_prompt
from .core_logic.context_builder import format_user_message_for_llm

# --- 日志设置 ---
logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"
LOG_FILE = "logs/bot.log"
bot_task = None
MEMORY_CUTOFFS: Dict[int, datetime] = {}
USER_USAGE_TRACKER: Dict[int, Dict[str, Any]] = {}

def load_config():
    """加载配置，并为新字段设置默认值，增加错误日志。"""
    default_config = {
        'discord_token': '', 'llm_provider': 'openai', 'api_key': '', 'base_url': None,
        'model_name': 'gpt-4o', 'system_prompt': 'You are a helpful assistant.',
        'blocked_prompt_response': '抱歉，通讯出了一些问题，这是一条自动回复：【{reason}】',
        'trigger_keywords': [], 'stream_response': True,
        'user_personas': {}, 'role_based_config': {}, 'scoped_prompts': {'guilds': {}, 'channels': {}},
        'context_mode': 'channel',
        'channel_context_settings': {'message_limit': 10, 'char_limit': 4000},
        'memory_context_settings': {'message_limit': 15, 'char_limit': 6000},
        'custom_parameters': [], 'plugins': {},
        'api_secret_key': secrets.token_hex(32)
    }
    if not os.path.exists(CONFIG_FILE):
        logger.warning(f"Config file not found at {CONFIG_FILE}. Creating a default one.")
        save_config(default_config)
        return default_config
        
    try:
        with open(CONFIG_FILE, "r", encoding='utf-8') as f:
            data = json.load(f)
        def set_defaults_recursive(default, config):
            for key, value in default.items():
                if isinstance(value, dict):
                    config.setdefault(key, {})
                    set_defaults_recursive(value, config[key])
                else:
                    config.setdefault(key, value)
        set_defaults_recursive(default_config, data)
        return data

    except json.JSONDecodeError as e:
        logger.error(f"FATAL: config.json is corrupted and cannot be parsed. Error: {e}. Please fix it manually.")
        return default_config
    except Exception as e:
        logger.error(f"FATAL: An unexpected error occurred while loading config.json: {e}", exc_info=True)
        return default_config

def save_config(config_data):
    with open(CONFIG_FILE, "w", encoding='utf-8') as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_task
    loop = asyncio.get_event_loop()
    bot_task = loop.create_task(run_bot(MEMORY_CUTOFFS, USER_USAGE_TRACKER))
    yield
    if bot_task and not bot_task.done():
        bot_task.cancel()
        try: await bot_task
        except asyncio.CancelledError: print("Bot task successfully cancelled.")

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Pydantic Models ---
class Persona(BaseModel):
    id: Optional[str] = None
    nickname: Optional[str] = None
    prompt: Optional[str] = None

class RoleConfig(BaseModel):
    id: Optional[str] = None
    title: str = ""
    prompt: str = ""
    enable_message_limit: bool = False
    message_limit: int = Field(0, ge=0)
    message_refresh_minutes: int = Field(60, ge=1)
    message_output_budget: int = Field(1, ge=1)
    enable_char_limit: bool = False
    char_limit: int = Field(0, ge=0)
    char_refresh_minutes: int = Field(60, ge=1)
    char_output_budget: int = Field(300, ge=0)
    display_color: str = "#ffffff"

class ContextSettings(BaseModel):
    message_limit: int = Field(ge=0)
    char_limit: int = Field(ge=0)

class CustomParameter(BaseModel):
    name: str
    type: str
    value: Any

class PluginHttpRequestConfig(BaseModel):
    url: str = ""
    method: str = "GET"
    headers: str = "{}"
    body_template: str = "{}"

class PluginConfig(BaseModel):
    name: str = "New Plugin"
    enabled: bool = True
    trigger_type: str = "command"
    injection_mode: str = "override"
    triggers: List[str] = Field(default_factory=list)
    action_type: str = "http_request"
    http_request_config: PluginHttpRequestConfig = Field(default_factory=PluginHttpRequestConfig)
    llm_prompt_template: str = "Summarize: {api_result}"

class ScopedPromptItem(BaseModel):
    id: Optional[str] = None
    enabled: bool = True
    mode: str = "append"
    prompt: str = ""

class ScopedPrompts(BaseModel):
    guilds: Dict[str, ScopedPromptItem] = Field(default_factory=dict)
    channels: Dict[str, ScopedPromptItem] = Field(default_factory=dict)

class Config(BaseModel):
    discord_token: str
    llm_provider: str
    api_key: str
    base_url: Optional[str] = None
    model_name: str
    system_prompt: str
    blocked_prompt_response: str
    trigger_keywords: List[str]
    stream_response: bool
    user_personas: Dict[str, Persona] = Field(default_factory=dict)
    role_based_config: Dict[str, RoleConfig] = Field(default_factory=dict)
    scoped_prompts: ScopedPrompts = Field(default_factory=ScopedPrompts)
    context_mode: str
    channel_context_settings: ContextSettings
    memory_context_settings: ContextSettings
    custom_parameters: List[CustomParameter] = Field(default_factory=list)
    plugins: Dict[str, PluginConfig] = Field(default_factory=dict)
    api_secret_key: str

# --- Request/Response Models for Endpoints ---
class ClearMemoryRequest(BaseModel):
    channel_id: str

class PluginTriggerRequest(BaseModel):
    plugin_name: str
    args: Dict[str, Any] = Field(default_factory=dict)

class DebuggerRequest(BaseModel):
    user_id: str
    channel_id: str
    guild_id: Optional[str] = None
    role_id: Optional[str] = None
    message_content: str

# --- API Endpoints ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def get_api_key(api_key_received: str = Security(api_key_header)):
    config = load_config()
    correct_api_key = config.get("api_secret_key")
    if correct_api_key and secrets.compare_digest(api_key_received, correct_api_key):
        return api_key_received
    raise HTTPException(status_code=403, detail="Could not validate credentials")

@app.get("/api/config")
async def get_config_endpoint():
    config_data = load_config()
    try:
        # 尝试验证配置
        Config.parse_obj(config_data)
        logger.info("Config validation successful")
        return config_data
    except ValidationError as e:
        logger.error(f"Config validation failed: {e}")
        # 即使验证失败，也返回配置数据，让前端能够显示
        # 但添加一个警告字段
        config_data["_validation_warning"] = str(e)
        return config_data


@app.post("/api/config")
async def update_config_endpoint(config_data: Config):
    global bot_task
    try:
        # 保存配置
        config_dict = config_data.dict(by_alias=True)
        # 移除可能的验证警告字段
        config_dict.pop("_validation_warning", None)
        save_config(config_dict)
        
        # 重启bot
        if bot_task and not bot_task.done():
            bot_task.cancel()
            try: 
                await bot_task
            except asyncio.CancelledError: 
                pass
        
        loop = asyncio.get_event_loop()
        bot_task = loop.create_task(run_bot(MEMORY_CUTOFFS, USER_USAGE_TRACKER))
        
        logger.info("Configuration updated and bot restarted successfully")
        return {"message": "Configuration updated and bot restarted."}
    except Exception as e:
        logger.error(f"Failed to update configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/memory/clear")
async def clear_channel_memory(request: ClearMemoryRequest):
    if not request.channel_id.isdigit():
        raise HTTPException(status_code=400, detail="Channel ID must be a number.")
    MEMORY_CUTOFFS[int(request.channel_id)] = datetime.now(timezone.utc)
    return {"message": f"Memory for channel {request.channel_id} will be ignored before this point."}

@app.post("/api/plugins/trigger", dependencies=[Depends(get_api_key)])
async def trigger_plugin_endpoint(request: PluginTriggerRequest):
    config = load_config()
    plugins_dict = config.get("plugins", {})
    target_plugin = next((p for p in plugins_dict.values() if p.get("name") == request.plugin_name and p.get("enabled")), None)
    if not target_plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{request.plugin_name}' not found or is disabled.")
    
    mock_message = MagicMock()
    # ... setup mock_message ...
    args_str = json.dumps(request.args)
    action_type = target_plugin.get('action_type')

    if action_type == 'http_request':
        result = await _execute_http_request(target_plugin, mock_message, args_str)
        try: return json.loads(result) if result else {}
        except json.JSONDecodeError: return {"result": result}
    
    # ... other action types ...
    
    raise HTTPException(status_code=400, detail=f"Unsupported action type '{action_type}'.")

@app.post("/api/debug/simulate")
async def simulate_debugger_run(request: DebuggerRequest):
    config = load_config()
    # ... debugger logic ...
    return {"message": "Debugger not fully implemented in this snippet."}


@app.get("/api/logs", response_class=Response)
async def get_logs():
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            log_content = "".join(deque(f, 200))
        return Response(content=log_content, media_type="text/plain; charset=utf-8")
    except FileNotFoundError:
        return Response(content=f"Log file not found at '{LOG_FILE}'.", status_code=404, media_type="text/plain")
    except Exception as e:
        return Response(content=f"An error occurred while reading logs: {e}", status_code=500, media_type="text/plain")

