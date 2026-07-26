"""
Rate limiting middleware for FastAPI using a sliding window algorithm.

Tracks request frequency per client IP + endpoint combination.
Returns 429 Too Many Requests when the limit is exceeded.

Env var: RATE_LIMIT_PER_MINUTE (default 60)
"""

import logging
import os
import time
from collections import defaultdict
from typing import Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
WINDOW_SECONDS = 60

# ---------------------------------------------------------------------------
# In-memory sliding-window state (single-worker only)
# ---------------------------------------------------------------------------
_request_counts: Dict[str, List[float]] = defaultdict(list)

# Endpoint path prefixes that are protected by rate limiting.
# All HTTP methods on these paths are subject to the same limit.
_PROTECTED_PREFIXES = frozenset({
    "/api/auth/bootstrap",
    "/api/chat/direct",
    "/api/config",
})


def _is_protected(path: str) -> bool:
    """Check whether *path* should be rate-limited."""
    return any(path.startswith(prefix) for prefix in _PROTECTED_PREFIXES)


def _build_key(request: Request) -> str:
    """Build a rate-limit key from client IP + endpoint path."""
    client_ip = request.client.host if request.client else "unknown"
    return f"{client_ip}:{request.url.path}"


def _prune(key: str, now: float) -> None:
    """Remove timestamps older than *WINDOW_SECONDS* for a given *key*."""
    counts = _request_counts[key]
    cutoff = now - WINDOW_SECONDS
    # Keep only entries within the window
    _request_counts[key] = [t for t in counts if t > cutoff]
    # Clean up empty keys to avoid unbounded memory growth
    if not _request_counts[key]:
        del _request_counts[key]


# ---------------------------------------------------------------------------
# Middleware class
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter based on client IP + URL path.

    Only applies to endpoints listed in ``_PROTECTED_PREFIXES``.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip non-protected endpoints
        if not _is_protected(request.url.path):
            return await call_next(request)

        key = _build_key(request)
        now = time.time()

        # Prune old entries for this key
        _prune(key, now)

        current_count = len(_request_counts.get(key, []))
        if current_count >= RATE_LIMIT_PER_MINUTE:
            logger.warning(
                "Rate limit exceeded for %s — %d requests in window",
                key,
                current_count,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests"},
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )

        # Record this request
        _request_counts[key].append(now)
        return await call_next(request)


def register_rate_limit_middleware(app: FastAPI) -> None:
    """
    Register the :class:`RateLimitMiddleware` on a FastAPI application.

    This is intended to be called from ``main.py`` during app setup.
    """
    app.add_middleware(RateLimitMiddleware)  # type: ignore[arg-type]
    logger.info(
        "RateLimitMiddleware registered (limit=%d req/min)", RATE_LIMIT_PER_MINUTE
    )
