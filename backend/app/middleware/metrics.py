"""
Lightweight, in-memory request metrics for FastAPI.

Collects request count, per-path distribution, status-code distribution,
and response-time statistics — all stored in a module-level dictionary so
that a separate endpoint (e.g. ``/metrics``) can consume them as JSON.

No external dependencies (not even ``prometheus_client``).
"""

import logging
import time
from collections import defaultdict
from typing import Dict, List

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory metrics store
# ---------------------------------------------------------------------------
#: Total number of requests processed since application start (or last reset).
_total_requests: int = 0

#: Per-URL-path request counts.
_requests_by_path: Dict[str, int] = defaultdict(int)

#: Per-HTTP-status-code counts.
_responses_by_status: Dict[int, int] = defaultdict(int)

#: Rolling window of response times (seconds) — capped to avoid unbounded
#: memory growth.
_response_times: List[float] = []

#: Maximum number of response-time samples retained in memory.
_MAX_SAMPLES = 1000


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class MetricsMiddleware(BaseHTTPMiddleware):
    """Record basic HTTP metrics for every request that passes through."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        elapsed = time.monotonic() - start

        global _total_requests
        _total_requests += 1
        _requests_by_path[request.url.path] += 1
        _responses_by_status[response.status_code] += 1

        _response_times.append(elapsed)
        if len(_response_times) > _MAX_SAMPLES:
            _response_times.pop(0)

        return response


# ---------------------------------------------------------------------------
# Metrics consumer
# ---------------------------------------------------------------------------

def get_metrics() -> Dict:
    """Return a snapshot of the collected metrics as a plain dictionary.

    The returned dict is safe to serialise as JSON.
    """
    times = _response_times
    count = len(times)
    avg_time = sum(times) / count if count else 0.0
    max_time = max(times) if count else 0.0
    min_time = min(times) if count else 0.0

    return {
        "total_requests": _total_requests,
        "requests_by_path": dict(_requests_by_path),
        "responses_by_status": dict(_responses_by_status),
        "response_time": {
            "avg_seconds": round(avg_time, 4),
            "min_seconds": round(min_time, 4),
            "max_seconds": round(max_time, 4),
            "samples": count,
        },
    }


def reset_metrics() -> None:
    """Reset all collected metrics — useful in test fixtures."""
    global _total_requests
    _total_requests = 0
    _requests_by_path.clear()
    _responses_by_status.clear()
    _response_times.clear()
