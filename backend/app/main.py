import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .app_context import AppContext
from .bot_manager import BotManager
from .middleware.rate_limit import register_rate_limit_middleware
from .usage_tracker import UsageTracker
from .utils import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = AppContext.get()

    from .paths import DataPaths
    DataPaths.ensure_dirs()
    setup_logging()

    # Initialize AstrBotProcessManager singleton
    from .astrbot_manager import AstrBotProcessManager
    ctx.astrbot_process_manager = AstrBotProcessManager()

    ctx.bot_manager = BotManager()
    await ctx.bot_manager.load_all()

    ctx.usage_tracker = UsageTracker()
    await ctx.usage_tracker.initialize()

    yield
    if ctx.usage_tracker:
        await ctx.usage_tracker.close()
    if ctx.astrbot_process_manager:
        await ctx.astrbot_process_manager.shutdown()
    await ctx.bot_manager.shutdown()


app = FastAPI(
    title="Discord LLM ChatBot API",
    description=(
        "REST API for the Discord LLM ChatBot — a multi-bot Discord/QQ chatbot "
        "powered by AstrBot, supporting 12 LLM providers with a web control panel, "
        "persistent knowledge engine, OCR image recognition, plugin system, and "
        "multi-instance management.\n\n"
        "## Authentication\n"
        "Most endpoints require an `X-API-Key` header matching the configured "
        "`api_secret_key`.  The `/health` and `/metrics` endpoints are "
        "unauthenticated for load-balancer / orchestrator access.\n\n"
        "## Internal Endpoints\n"
        "Endpoints under `/internal` are for inter-process communication between "
        "AstrBot subprocesses and the management server.  They require an "
        "`X-Internal-Token` header.\n\n"
        "## Rate Limiting\n"
        "Global rate limiting is applied (default: 60 requests/minute).  "
        "Configured via the `RATE_LIMIT_PER_MINUTE` environment variable."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

_cors_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:8094,http://127.0.0.1:8094")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "X-Timezone"],
)

register_rate_limit_middleware(app)

# ---------------------------------------------------------------------------
# Observability middleware
# ---------------------------------------------------------------------------
from .middleware.request_id import RequestIDMiddleware
from .middleware.metrics import MetricsMiddleware

app.add_middleware(RequestIDMiddleware)
app.add_middleware(MetricsMiddleware)

from .routers.config import router as config_router
from .routers.chat import router as chat_router
from .routers.debug import router as debug_router
from .routers.memory import router as memory_router
from .routers.usage import router as usage_router
from .routers.plugins import router as plugins_router
from .routers.models_test import router as models_test_router
from .routers.logs import router as logs_router
from .routers.bots import router as bots_router
from .routers.state import router as state_router
from .routers.user_options import router as user_options_router
from .routers.interactions import router as interactions_router
from .routers.internal import internal_router

app.include_router(config_router)
app.include_router(chat_router)
app.include_router(debug_router)
app.include_router(memory_router)
app.include_router(usage_router)
app.include_router(plugins_router)
app.include_router(models_test_router)
app.include_router(logs_router)
app.include_router(bots_router)
app.include_router(state_router)
app.include_router(user_options_router)
app.include_router(interactions_router)
app.include_router(internal_router)

# ---------------------------------------------------------------------------
# Observability routes (unauthenticated)
# ---------------------------------------------------------------------------
from .routers.health import router as health_router

app.include_router(health_router)
