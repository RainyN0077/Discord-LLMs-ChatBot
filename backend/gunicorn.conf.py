"""
Gunicorn configuration for ELA-Bot.

IMPORTANT: Multi-worker mode is NOT supported.
See "Deployment" section in README.md for details.
"""

# ---------------------------------------------------------------------------
# Single-worker enforcement
# ---------------------------------------------------------------------------
# config_cache uses an in-process memory cache (_cache / _cache_mtime).
# With multiple workers, each worker process has its own independent cache
# copy, so configuration updates made via one worker are invisible to others.
# Redis fallback mode (when Redis is unavailable) also suffers from the same
# per-worker state inconsistency. Therefore we force workers = 1.
# ---------------------------------------------------------------------------
workers = 1

# ---------------------------------------------------------------------------
# Binding
# ---------------------------------------------------------------------------
bind = "0.0.0.0:8080"

# ---------------------------------------------------------------------------
# Timeout settings
# ---------------------------------------------------------------------------
timeout = 120           # Maximum seconds a worker can handle a request
graceful_timeout = 30   # Seconds to wait for worker shutdown after SIGTERM
keepalive = 5           # Seconds to keep idle HTTP connections alive

# ---------------------------------------------------------------------------
# Worker class
# ---------------------------------------------------------------------------
# Use UvicornWorker for ASGI (FastAPI) compatibility.
worker_class = "uvicorn.workers.UvicornWorker"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
loglevel = "info"
accesslog = "-"         # stdout
errorlog = "-"          # stdout
