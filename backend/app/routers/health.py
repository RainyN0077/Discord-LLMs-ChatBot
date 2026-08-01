"""
Observability endpoints: health check and lightweight metrics.

* ``GET /health``  — returns JSON with database and Redis connectivity status.
* ``GET /metrics`` — returns in-memory request metrics (counts, timing).

Both endpoints are **unauthenticated** so that load balancers and
orchestrators can reach them without an API key.
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["observability"])


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

@router.get("/health", summary="健康检查", description="返回应用整体健康状态及各依赖项（数据库、Redis）的连接状态。用于负载均衡器和编排器的存活检查。")
async def health_check():
    """Health-check endpoint.

    Returns the overall application health along with per-dependency status::

        {
            "status": "healthy",
            "database": "ok",
            "redis": "ok"
        }

    When a dependency is unavailable *status* becomes ``"degraded"`` and
    the corresponding field shows ``"unavailable"``.
    """
    db_ok = await _check_database()
    redis_ok = _check_redis()

    return {
        "status": "healthy" if (db_ok and redis_ok) else "degraded",
        "database": "ok" if db_ok else "unavailable",
        "redis": "ok" if redis_ok else "unavailable",
    }


async def _check_database() -> bool:
    """Verify SQLite is reachable by executing ``SELECT 1``."""
    try:
        from app.paths import DataPaths

        import aiosqlite

        async with aiosqlite.connect(str(DataPaths.KNOWLEDGE_DB)) as db:
            cursor = await db.execute("SELECT 1")
            await cursor.fetchone()
        return True
    except Exception as exc:
        logger.warning("Health check — database unavailable: %s", exc)
        return False


def _check_redis() -> bool:
    """Verify Redis is reachable by calling ``PING``."""
    try:
        from app.core_shared import get_redis

        client = get_redis()
        if client is None:
            return False
        client.ping()
        return True
    except Exception as exc:
        logger.warning("Health check — Redis unavailable: %s", exc)
        return False


# ---------------------------------------------------------------------------
# /metrics
# ---------------------------------------------------------------------------

@router.get("/metrics", summary="获取指标", description="返回进程内请求指标（请求总数、路径分布、状态码分布、响应时间统计）。")
async def metrics_endpoint():
    """Return lightweight in-memory request metrics as JSON.

    Exposed fields::

        {
            "total_requests": 42,
            "requests_by_path": {"/api/config": 10, "/health": 32},
            "responses_by_status": {"200": 38, "404": 4},
            "response_time": {
                "avg_seconds": 0.1234,
                "min_seconds": 0.0012,
                "max_seconds": 1.2345,
                "samples": 42
            }
        }
    """
    from app.middleware.metrics import get_metrics

    return get_metrics()
