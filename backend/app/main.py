import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from bot import run_bot

CONFIG_FILE = "config.json"
bot_task = None

# This dictionary will store memory cutoff timestamps in memory.
# Key: channel_id (int), Value: datetime object
# It will be passed to the bot task.
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
                # Ensure all keys exist, adding defaults for missing ones
                for key, value in default_config.items():
                    data.setdefault(key, value)
                return data
            except json.JSONDecodeError:
                return default_config
    return default_config

def save_config(config_data):
    # Clean up old, now-unused top-level keys if they exist
    config_data.pop('context_message_limit', None)
    config_data.pop('context_char_limit', None)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=2)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_task
    loop = asyncio.get_event_loop()
    # Pass the shared memory dictionary to the bot task
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
    type: str  # 'text', 'number', 'boolean', 'json'
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
        try:
            await bot_task
        except asyncio.CancelledError:
            pass # Expected
    
    loop = asyncio.get_event_loop()
    bot_task = loop.create_task(run_bot(MEMORY_CUTOFFS))
    return {"message": "Configuration updated and bot restarted."}

@app.post("/api/memory/clear")
async def clear_channel_memory(request: ClearMemoryRequest):
    if not request.channel_id.isdigit():
        raise HTTPException(status_code=400, detail="Channel ID must be a number.")
    
    channel_id_int = int(request.channel_id)
    MEMORY_CUTOFFS[channel_id_int] = datetime.now(timezone.utc)
    print(f"Memory cutoff set for channel {channel_id_int} at {MEMORY_CUTOFFS[channel_id_int]}")
    return {"message": f"Memory for channel {request.channel_id} will be ignored before this point."}
