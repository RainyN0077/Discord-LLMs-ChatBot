import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .app_context import AppContext
from .bot_manager import BotManager
from .config_bridge import generate_env_file
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

    generate_env_file()

    import nonebot
    nonebot.init()
    ctx.nonebot_driver = nonebot.get_driver()

    from .discord_patch import apply_component_emoji_fix
    apply_component_emoji_fix()

    from nonebot.adapters.discord import Adapter as DiscordAdapter
    driver = nonebot.get_driver()
    driver.register_adapter(DiscordAdapter)

    nonebot.load_plugins("nb_plugins")

    from .adapters.message_bus_impl import DefaultMessageBus
    from .adapters.discord_platform_adapter import DiscordPlatformAdapter

    ctx.message_bus = DefaultMessageBus()
    ctx.message_bus.register_platform_adapter("discord", DiscordPlatformAdapter())
    logger.info("MessageBus initialized with Discord platform adapter")

    ctx.bot_manager = BotManager()
    await ctx.bot_manager.load_all()

    from .adapters.factory import create_bot_runtime
    for bot_id, instance in ctx.bot_manager.get_all_instances().items():
        try:
            runtime = create_bot_runtime(bot_id, instance.config)
            ctx.message_bus.register_bot_runtime(bot_id, runtime)
        except Exception as e:
            logger.warning("Failed to create BotRuntime for '%s': %s", bot_id, e)

    logger.info("Using ProviderPool for LLM provider management")
    from .llm_providers.provider_pool import ProviderPool
    ctx.provider_pool = ProviderPool(
        max_concurrent_per_provider=5,
        circuit_breaker_threshold=3,
        circuit_breaker_reset_seconds=60.0,
        health_check_interval_seconds=300.0,
    )
    logger.info("ProviderPool initialized")

    ctx.usage_tracker = UsageTracker()
    await ctx.usage_tracker.initialize()

    generate_env_file()

    if hasattr(driver, '_startup'):
        await driver._startup()
        logger.info("NoneBot driver startup complete — Discord adapters connected.")

    yield
    if hasattr(driver, '_shutdown'):
        await driver._shutdown()
    if ctx.usage_tracker:
        await ctx.usage_tracker.close()
    await ctx.bot_manager.shutdown()


app = FastAPI(
    title="Discord LLM ChatBot API",
    description=(
        "REST API for the Discord LLM ChatBot — a multi-bot Discord/QQ chatbot "
        "powered by NoneBot2, supporting 12 LLM providers with a web control panel, "
        "persistent knowledge engine, OCR image recognition, plugin system, and "
        "multi-instance management.\n\n"
        "## Authentication\n"
        "Most endpoints require an `X-API-Key` header matching the configured "
        "`api_secret_key`.  The `/health` and `/metrics` endpoints are "
        "unauthenticated for load-balancer / orchestrator access.\n\n"
        "## Internal Endpoints\n"
        "Endpoints under `/internal` are for inter-process communication between "
        "NoneBot subprocesses and the management server.  They require an "
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
from .routers.providers import router as providers_router

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
app.include_router(providers_router)

# ---------------------------------------------------------------------------
# Observability routes (unauthenticated)
# ---------------------------------------------------------------------------
from .routers.health import router as health_router

app.include_router(health_router)
