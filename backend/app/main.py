import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict
from datetime import datetime, timezone
from collections import deque

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 机器人代码的导入保持不变
from bot import run_bot

CONFIG_FILE = "config.json"
LOG_FILE = "logs/bot.log" # 定义日志文件路径
bot_task = None

# This dictionary will store memory cutoff timestamps in memory.
MEMORY_CUTOFFS: Dict[int, datetime] = {}

def load_config():
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
        'context_mode': 'channel',
        'channel_context_settings': {'message_limit': 10, 'char_limit': 4000},
        'memory_context_settings': {'message_limit': 15, 'char_limit': 6000},
        'custom_parameters': []
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                data = json.load(f)
                for key, value in default_config.items():
                    data.setdefault(key, value)
                return data
            except json.JSONDecodeError:
                return default_config
    return default_config

def save_config(config_data):
    config_data.pop('context_message_limit', None)
    config_data.pop('context_char_limit', None)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=2)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_task
    loop = asyncio.get_event_loop()
    bot_task = loop.create_task(run_bot(MEMORY_CUTOFFS))
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

class Persona(BaseModel):
    nickname: str
    prompt: str

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
    trigger_keywords: list[str]
    stream_response: bool
    user_personas: dict[str, Persona] = Field(default_factory=dict)
    context_mode: str = Field(default='channel')
    channel_context_settings: ContextSettings = Field(default_factory=lambda: ContextSettings(message_limit=10, char_limit=4000))
    memory_context_settings: ContextSettings = Field(default_factory=lambda: ContextSettings(message_limit=15, char_limit=6000))
    custom_parameters: list[CustomParameter] = Field(default_factory=list)

class ClearMemoryRequest(BaseModel):
    channel_id: str

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
    bot_task = loop.create_task(run_bot(MEMORY_CUTOFFS))
    return {"message": "Configuration updated and bot restarted."}

@app.post("/api/memory/clear")
async def clear_channel_memory(request: ClearMemoryRequest):
    if not request.channel_id.isdigit():
        raise HTTPException(status_code=400, detail="Channel ID must be a number.")
    
    channel_id_int = int(request.channel_id)
    MEMORY_CUTOFFS[channel_id_int] = datetime.now(timezone.utc)
    # 使用 print 或 logging 查看 FastAPI 侧的日志
    print(f"Memory cutoff set for channel {channel_id_int} at {MEMORY_CUTOFFS[channel_id_int]}")
    return {"message": f"Memory for channel {request.channel_id} will be ignored before this point."}

# --- 新增日志查看接口 ---
@app.get("/api/logs", response_class=Response)
async def get_logs():
    """读取并返回最新的100条机器人日志。"""
    try:
        # 使用 deque 高效地获取文件末尾的行
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            last_100_lines = deque(f, 100)
        
        log_content = "".join(last_100_lines)
        # 返回纯文本内容，浏览器会直接显示
        return Response(content=log_content, media_type="text/plain")

    except FileNotFoundError:
        return Response(content=f"Log file not found at '{LOG_FILE}'. The bot may not have run yet or the path is incorrect.", media_type="text/plain", status_code=404)
    except Exception as e:
        return Response(content=f"An error occurred while reading logs: {e}", media_type="text/plain", status_code=500)

