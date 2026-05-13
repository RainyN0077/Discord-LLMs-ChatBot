import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .bot_manager import BotManager
from .utils import setup_logging
from . import state

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    state.bot_manager = BotManager()
    await state.bot_manager.load_all()
    yield
    await state.bot_manager.shutdown()


app = FastAPI(lifespan=lifespan)

_cors_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:8094,http://127.0.0.1:8094")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

from .routers.config import router as config_router
from .routers.chat import router as chat_router
from .routers.debug import router as debug_router
from .routers.memory import router as memory_router
from .routers.usage import router as usage_router
from .routers.plugins import router as plugins_router
from .routers.models_test import router as models_test_router
from .routers.logs import router as logs_router
from .routers.bots import router as bots_router

app.include_router(config_router)
app.include_router(chat_router)
app.include_router(debug_router)
app.include_router(memory_router)
app.include_router(usage_router)
app.include_router(plugins_router)
app.include_router(models_test_router)
app.include_router(logs_router)
app.include_router(bots_router)
