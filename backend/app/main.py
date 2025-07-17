import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List
from datetime import datetime, timezone
from collections import deque

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .bot import run_bot

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
        'enable_message_limit': False,
        'message_limit': 0, 'message_refresh_minutes': 60,
        'message_output_budget': 1,
        'enable_char_limit': False, # 后端保留此字段名，但语义为 token
        'char_limit': 0, 'char_refresh_minutes': 60,
        'char_output_budget': 300,
        'display_color': '#ffffff'
    }
    default_config = {
        'discord_token': '', 'llm_provider': 'openai', 'api_key': '', 'base_url': None,
        'model_name': 'gpt-4o', 'system_prompt': 'You are a helpful assistant.',
        'trigger_keywords': [], 'stream_response': True,
        'user_personas': {}, 'role_based_config': {},
        'context_mode': 'channel',
        'channel_context_settings': {'message_limit': 10, 'char_limit': 4000},
        'memory_context_settings': {'message_limit': 15, 'char_limit': 6000},
        'custom_parameters': [],
        'plugins': []  # 新增插件列表默认值
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic 模型定义 ---
class Persona(BaseModel):
    nickname: str
    prompt: str

class RoleConfig(BaseModel):
    title: str = ""
    prompt: str = ""
    enable_message_limit: bool = False
    message_limit: int = Field(0, ge=0)
    message_refresh_minutes: int = Field(60, ge=1)
    message_output_budget: int = Field(1, ge=1)
    
    enable_char_limit: bool = False # 在后端，'char'相关字段的语义是'token'
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
    headers: str = "{}" # 以JSON字符串形式存储
    body_template: str = "{}" # 以JSON字符串形式存储

class PluginConfig(BaseModel):
    name: str = "New Plugin"
    enabled: bool = True
    trigger_type: str = "command"
    triggers: List[str] = Field(default_factory=list)
    action_type: str = "http_request"
    http_request_config: PluginHttpRequestConfig = Field(default_factory=PluginHttpRequestConfig)
    llm_prompt_template: str = "Please summarize the following data based on the user's request '{user_input}':\n\n{api_result}"

class Config(BaseModel):
    discord_token: str
    llm_provider: str
    api_key: str
    base_url: str = None
    model_name: str
    system_prompt: str
    trigger_keywords: List[str]
    stream_response: bool
    user_personas: Dict[str, Persona] = Field(default_factory=dict)
    role_based_config: Dict[str, RoleConfig] = Field(default_factory=dict)
    context_mode: str = Field(default='channel')
    channel_context_settings: ContextSettings = Field(default_factory=lambda: ContextSettings(message_limit=10, char_limit=4000))
    memory_context_settings: ContextSettings = Field(default_factory=lambda: ContextSettings(message_limit=15, char_limit=6000))
    custom_parameters: List[CustomParameter] = Field(default_factory=list)
    plugins: List[PluginConfig] = Field(default_factory=list)

class ClearMemoryRequest(BaseModel):
    channel_id: str

# --- API Endpoints ---
@app.get("/api/config")
async def get_config():
    return load_config()

@app.post("/api/config")
async def update_config(config: Config):
    global bot_task
    save_config(config.dict(by_alias=True))
    
    if bot_task and not bot_task.done():
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass
    
    loop = asyncio.get_event_loop()
    bot_task = loop.create_task(run_bot(MEMORY_CUTOFFS, USER_USAGE_TRACKER))
    return {"message": "Configuration updated and bot restarted."}

@app.post("/api/memory/clear")
async def clear_channel_memory(request: ClearMemoryRequest):
    if not request.channel_id.isdigit():
        raise HTTPException(status_code=400, detail="Channel ID must be a number.")
    
    channel_id_int = int(request.channel_id)
    MEMORY_CUTOFFS[channel_id_int] = datetime.now(timezone.utc)
    return {"message": f"Memory for channel {request.channel_id} will be ignored before this point."}

@app.get("/api/logs", response_class=Response)
async def get_logs():
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            log_content = "".join(deque(f, 200))
        return Response(content=log_content, media_type="text/plain; charset=utf-8")
    except FileNotFoundError:
        return Response(content=f"Log file not found at '{LOG_FILE}'.", media_type="text/plain; charset=utf-8", status_code=404)
    except Exception as e:
        return Response(content=f"An error occurred while reading logs: {e}", media_type="text/plain; charset=utf-8", status_code=500)
