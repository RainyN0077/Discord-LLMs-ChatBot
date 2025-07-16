import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from bot import run_bot

CONFIG_FILE = "config.json"
bot_task = None

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(config_data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=2)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_task
    loop = asyncio.get_event_loop()
    bot_task = loop.create_task(run_bot())
    yield
    if bot_task:
        bot_task.cancel()

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

class Config(BaseModel):
    discord_token: str
    llm_provider: str
    api_key: str
    base_url: str = None
    model_name: str
    system_prompt: str
    trigger_keywords: list[str]
    stream_response: bool
    user_personas: dict[str, Persona] = Field(default_factory=dict) # Updated Structure
    context_message_limit: int = Field(default=10, ge=0)
    context_char_limit: int = Field(default=2000, ge=0)

@app.get("/api/config")
async def get_config():
    return load_config()

@app.post("/api/config")
async def update_config(config: Config):
    global bot_task
    save_config(config.dict(by_alias=True)) # Use by_alias to handle Pydantic model correctly
    
    if bot_task and not bot_task.done():
        bot_task.cancel()
    
    loop = asyncio.get_event_loop()
    bot_task = loop.create_task(run_bot())
    return {"message": "Configuration updated and bot restarted."}
