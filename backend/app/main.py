import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List
from datetime import datetime, timezone, timedelta
from collections import deque

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from bot import run_bot

CONFIG_FILE = "config.json"
LOG_FILE = "logs/bot.log"
bot_task = None

# --- 状态追踪器 ---
# 存储频道记忆清除时间戳
MEMORY_CUTOFFS: Dict[int, datetime] = {}
# 追踪用户用量以进行频率限制
# 结构: { user_id: { "count": int, "chars": int, "timestamp": datetime } }
USER_USAGE_TRACKER: Dict[int, Dict[str, Any]] = {}


def load_config():
    """加载配置，并为新字段设置默认值。"""
    default_config = {
        'discord_token': '',
        'llm_provider': 'openai',
        'api_key': '',
        'base_url': None,
        'model_name': 'gpt-4o',
        'system_prompt': 'You are a helpful assistant.',
        'trigger_keywords': [],
        'stream_response': True,
        'user_personas': {},
        'role_based_config': {},
        'context_mode': 'channel',
        'channel_context_settings': {'message_limit': 10, 'char_limit': 4000},
        'memory_context_settings': {'message_limit': 15, 'char_limit': 6000},
        'custom_parameters': []
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding='utf-8') as f:
            try:
                data = json.load(f)
                # 确保所有默认键都存在
                for key, value in default_config.items():
                    data.setdefault(key, value)
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
    # 将两个状态追踪器传递给机器人
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
    message_limit: int = Field(0, ge=0)
    message_refresh_minutes: int = Field(60, ge=0)
    char_limit: int = Field(0, ge=0)
    char_refresh_minutes: int = Field(60, ge=0)

class ContextSettings(BaseModel):
    message_limit: int = Field(ge=0)
    char_limit: int = Field(ge=0)

class CustomParameter(BaseModel):
    name: str
    type: str
    value: Any

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
        try: await bot_task
        except asyncio.CancelledError: pass
    
    loop = asyncio.get_event_loop()
    # 重启机器人时传递状态追踪器
    bot_task = loop.create_task(run_bot(MEMORY_CUTOFFS, USER_USAGE_TRACKER))
    return {"message": "Configuration updated and bot restarted."}

@app.post("/api/memory/clear")
async def clear_channel_memory(request: ClearMemoryRequest):
    if not request.channel_id.isdigit():
        raise HTTPException(status_code=400, detail="Channel ID must be a number.")
    
    channel_id_int = int(request.channel_id)
    MEMORY_CUTOFFS[channel_id_int] = datetime.now(timezone.utc)
    print(f"Memory cutoff set for channel {channel_id_int} at {MEMORY_CUTOFFS[channel_id_int]}")
    return {"message": f"Memory for channel {request.channel_id} will be ignored before this point."}

@app.get("/api/logs", response_class=Response)
async def get_logs():
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            last_lines = deque(f, 200)
        log_content = "".join(last_lines)
        return Response(content=log_content, media_type="text/plain; charset=utf-8")
    except FileNotFoundError:
        return Response(content=f"Log file not found at '{LOG_FILE}'. The bot may not have run yet or path is incorrect.", media_type="text/plain; charset=utf-8", status_code=404)
    except Exception as e:
        return Response(content=f"An error occurred while reading logs: {e}", media_type="text/plain; charset=utf-8", status_code=500)
