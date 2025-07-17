# backend/app/main.py

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List
from datetime import datetime, timezone
from collections import deque
import secrets

from fastapi import FastAPI, HTTPException, Response, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from .bot import run_bot, get_llm_response
from .utils import _execute_http_request, _format_with_placeholders

CONFIG_FILE = "config.json"
LOG_FILE = "logs/bot.log"
bot_task = None

# --- 状态追踪器 ---
MEMORY_CUTOFFS: Dict[int, datetime] = {}
USER_USAGE_TRACKER: Dict[int, Dict[str, Any]] = {}

def load_config():
    """加载配置，并为新字段设置默认值。"""
    default_role_config_fields = {
        'title': '', 'prompt': '',
        'enable_message_limit': False, 'message_limit': 0, 'message_refresh_minutes': 60,
        'message_output_budget': 1, 'enable_char_limit': False, 'char_limit': 0, 
        'char_refresh_minutes': 60, 'char_output_budget': 300, 'display_color': '#ffffff'
    }
    default_config = {
        'discord_token': '', 'llm_provider': 'openai', 'api_key': '', 'base_url': None,
        'model_name': 'gpt-4o', 'system_prompt': 'You are a helpful assistant.',
        'blocked_prompt_response': '抱歉，通讯出了一些问题，这是一条自动回复：【{reason}】',
        'trigger_keywords': [], 'stream_response': True,
        'user_personas': {}, 'role_based_config': {},
        'context_mode': 'channel',
        'channel_context_settings': {'message_limit': 10, 'char_limit': 4000},
        'memory_context_settings': {'message_limit': 15, 'char_limit': 6000},
        'custom_parameters': [], 'plugins': [],
        'scoped_prompts': {'guilds': {}, 'channels': {}},
        'api_secret_key': secrets.token_hex(32)
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding='utf-8') as f:
            try:
                data = json.load(f)
                for key, value in default_config.items():
                    data.setdefault(key, value)
                if isinstance(data.get('role_based_config'), dict):
                    for role_id, role_cfg in data['role_based_config'].items():
                        for field, default_val in default_role_config_fields.items():
                            role_cfg.setdefault(field, default_val)
                if 'guilds' not in data.get('scoped_prompts', {}): data['scoped_prompts']['guilds'] = {}
                if 'channels' not in data.get('scoped_prompts', {}): data['scoped_prompts']['channels'] = {}
                return data
            except json.JSONDecodeError:
                return default_config
    return default_config

def save_config(config_data):
    """保存配置到文件。"""
    with open(CONFIG_FILE, "w", encoding='utf-8') as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI应用的生命周期管理。"""
    global bot_task
    loop = asyncio.get_event_loop()
    bot_task = loop.create_task(run_bot(MEMORY_CUTOFFS, USER_USAGE_TRACKER))
    yield
    if bot_task and not bot_task.done():
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            print("Bot task successfully cancelled.")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# --- Pydantic 模型定义 ---
class Persona(BaseModel):
    nickname: str; prompt: str
class RoleConfig(BaseModel):
    title: str = ""; prompt: str = ""; enable_message_limit: bool = False
    message_limit: int = Field(0, ge=0); message_refresh_minutes: int = Field(60, ge=1)
    message_output_budget: int = Field(1, ge=1); enable_char_limit: bool = False
    char_limit: int = Field(0, ge=0); char_refresh_minutes: int = Field(60, ge=1)
    char_output_budget: int = Field(300, ge=0); display_color: str = "#ffffff"
class ContextSettings(BaseModel):
    message_limit: int = Field(ge=0); char_limit: int = Field(ge=0)
class CustomParameter(BaseModel):
    name: str; type: str; value: Any
class PluginHttpRequestConfig(BaseModel):
    url: str = ""; method: str = "GET"; headers: str = "{}"; body_template: str = "{}"
class PluginConfig(BaseModel):
    name: str = "New Plugin"; enabled: bool = True; trigger_type: str = "command";injection_mode: str = "override";
    triggers: List[str] = Field(default_factory=list); action_type: str = "http_request"
    http_request_config: PluginHttpRequestConfig = Field(default_factory=PluginHttpRequestConfig)
    llm_prompt_template: str = "Summarize: {api_result}"

class ScopedPromptItem(BaseModel):
    enabled: bool = True; mode: str = "append"; prompt: str = ""
class ScopedPrompts(BaseModel):
    guilds: Dict[str, ScopedPromptItem] = Field(default_factory=dict)
    channels: Dict[str, ScopedPromptItem] = Field(default_factory=dict)
class Config(BaseModel):
    discord_token: str; llm_provider: str; api_key: str; base_url: str = None
    model_name: str; system_prompt: str; 
    blocked_prompt_response: str = '抱歉，通讯除了一些问题，这是一条自动回复：【{reason}】'
    trigger_keywords: List[str]; stream_response: bool
    user_personas: Dict[str, Persona] = Field(default_factory=dict)
    role_based_config: Dict[str, RoleConfig] = Field(default_factory=dict)
    scoped_prompts: ScopedPrompts = Field(default_factory=ScopedPrompts)
    context_mode: str = Field(default='channel')
    channel_context_settings: ContextSettings = Field(default_factory=lambda: ContextSettings(message_limit=10, char_limit=4000))
    memory_context_settings: ContextSettings = Field(default_factory=lambda: ContextSettings(message_limit=15, char_limit=6000))
    custom_parameters: List[CustomParameter] = Field(default_factory=list)
    plugins: List[PluginConfig] = Field(default_factory=list)
    api_secret_key: str = Field(default_factory=lambda: secrets.token_hex(32))
class ClearMemoryRequest(BaseModel):
    channel_id: str
class PluginTriggerRequest(BaseModel):
    plugin_name: str
    args: Dict[str, Any] = Field(default_factory=dict)

# --- API Endpoints ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def get_api_key(api_key_received: str = Security(api_key_header)):
    config = load_config()
    if api_key_received == config.get("api_secret_key"):
        return api_key_received
    else:
        raise HTTPException(status_code=403, detail="Could not validate credentials")

@app.get("/api/config")
async def get_config_endpoint():
    return load_config()

@app.post("/api/config")
async def update_config_endpoint(config: Config):
    global bot_task
    save_config(config.dict(by_alias=True))
    if bot_task and not bot_task.done():
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError: pass
    loop = asyncio.get_event_loop()
    bot_task = loop.create_task(run_bot(MEMORY_CUTOFFS, USER_USAGE_TRACKER))
    return {"message": "Configuration updated and bot restarted."}

@app.post("/api/memory/clear")
async def clear_channel_memory(request: ClearMemoryRequest):
    if not request.channel_id.isdigit():
        raise HTTPException(status_code=400, detail="Channel ID must be a number.")
    MEMORY_CUTOFFS[int(request.channel_id)] = datetime.now(timezone.utc)
    return {"message": f"Memory for channel {request.channel_id} will be ignored before this point."}

@app.post("/api/plugins/trigger", dependencies=[Depends(get_api_key)])
async def trigger_plugin_endpoint(request: PluginTriggerRequest):
    config = load_config()
    target_plugin = next((p for p in config.get("plugins", []) if p.get("name") == request.plugin_name and p.get("enabled")), None)
    if not target_plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{request.plugin_name}' not found or is disabled.")
    
    from unittest.mock import MagicMock
    mock_message = MagicMock()
    mock_message.author.id = "api_user"; mock_message.author.name = "API"
    mock_message.author.display_name = "API Trigger"; mock_message.channel.id = "api_channel"
    mock_message.guild = None; mock_message.content = json.dumps(request.args)
    args_str = json.dumps(request.args)
    
    action_type = target_plugin.get('action_type')

    if action_type == 'http_request':
        result = await _execute_http_request(target_plugin, mock_message, args_str)
        if result:
            try: return json.loads(result)
            except json.JSONDecodeError: return {"result": result}
        else: raise HTTPException(status_code=500, detail="Plugin executed but returned no data.")
    
    elif action_type == 'llm_augmented_tool':
        api_result = await _execute_http_request(target_plugin, mock_message, args_str)
        if not api_result:
            raise HTTPException(status_code=500, detail="Tool part of the plugin failed to fetch data.")
        
        prompt_template = target_plugin.get('llm_prompt_template', "Summarize: {api_result}")
        final_prompt = _format_with_placeholders(prompt_template, mock_message, args_str)
        final_prompt = final_prompt.replace("{api_result}", api_result)
        llm_messages = [{"role": "system", "content": "You are an API assistant that processes tool data."}, {"role": "user", "content": final_prompt}]
        
        config["stream_response"] = False
        full_response = ""
        async for _, content in get_llm_response(config, llm_messages):
            full_response = content

        if full_response:
            try: return json.loads(full_response)
            except json.JSONDecodeError: return {"result": full_response}
        else: raise HTTPException(status_code=500, detail="LLM processed the data but returned an empty response.")
            
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action type '{action_type}' for API trigger.")

@app.get("/api/logs", response_class=Response)
async def get_logs():
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            log_content = "".join(deque(f, 200))
        return Response(content=log_content, media_type="text/plain; charset=utf-8")
    except FileNotFoundError:
        return Response(content=f"Log file not found at '{LOG_FILE}'.", status_code=404)
    except Exception as e:
        return Response(content=f"An error occurred while reading logs: {e}", status_code=500)
