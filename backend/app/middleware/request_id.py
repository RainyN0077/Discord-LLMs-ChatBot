"""
Request-ID middleware for FastAPI.

Adds a unique ``X-Request-ID`` header to every response.  If the incoming
request already carries an ``X-Request-ID`` header that value is propagated;
otherwise a new ``uuid4`` is generated.

Usage::

    from app.middleware.request_id import RequestIDMiddleware
    app.add_middleware(RequestIDMiddleware)
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique ``X-Request-ID`` header into every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
