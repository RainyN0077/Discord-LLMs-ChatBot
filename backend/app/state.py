"""Application state — backward-compatible proxy to AppContext.

This module is kept for backward compatibility. All application-level state
has been moved to :class:`app.app_context.AppContext`.

Production code SHOULD use ``AppContext.get()`` directly.
Legacy code that does ``from app import state; state.bot_manager`` continues
to work through the module-level ``__getattr__`` proxy below.

Module-level attribute assignment (e.g. ``state.bot_manager = mock``) still
works because it shadows the proxy — this is relied upon by test fixtures
that monkeypatch state.
"""

from typing import Any

from .app_context import AppContext

_ATTR_MAP: dict[str, str] = {
    "bot_manager": "bot_manager",
    "nonebot_driver": "nonebot_driver",
    "MEMORY_CUTOFFS": "memory_cutoffs",
    "bot_task": "bot_tasks",
}


def get_bot_manager() -> Any:
    """Backward-compatible helper — delegates to AppContext."""
    return AppContext.get().bot_manager


def __getattr__(name: str) -> Any:
    """Proxy attribute access to AppContext singleton.

    Called only when normal attribute lookup on this module fails.
    """
    if name == "get_bot_manager":
        return get_bot_manager
    ctx_attr = _ATTR_MAP.get(name)
    if ctx_attr is not None:
        return getattr(AppContext.get(), ctx_attr)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
