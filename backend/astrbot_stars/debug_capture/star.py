"""Debug Capture Star (AstrBot v4.26.2).

Captures LLM pipeline state (system prompt, history, LLM messages,
response, usage, provider, model, etc.) from event extras and the
response result into local in-memory storage for the Debugger WebUI
to query via the management layer API.

Phase 1 (current): local memory storage with per-channel and global
caps.  Phase 2 will add IPC upload to the management layer for
persistence.

Never blocks or raises — capture failures are silently logged at DEBUG
level.  Large string fields are truncated to 5000 characters to bound
memory usage.

Security:
  - ``_captures`` is an *instance* variable (not shared across instances).
  - ``get_captures()`` requires a ``bot_id`` argument for caller
    identification.
  - ``system_prompt`` is sanitized to remove potential API keys/tokens
    before storage.
  - Global cap of 200 total captures across all channels (oldest channel
    evicted first when exceeded).
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)

_MAX_CAPTURES_PER_CHANNEL = 50
_GLOBAL_MAX_CAPTURES = 200
_MAX_STR_LEN = 5000

# Regex patterns for sanitizing sensitive fields (e.g. API keys in system_prompt)
_SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|apikey|api[_-]?secret|token|secret[_-]?key)\s*[=:]\s*['\"][^'\"]+['\"]"),
    re.compile(r"(?i)(authorization|bearer)\s+['\"][^'\"]+['\"]"),
]


def _truncate(value: Any, max_len: int = _MAX_STR_LEN) -> Any:
    """Truncate string values to *max_len*; pass all other types through."""
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + f"... [truncated {len(value) - max_len} chars]"
    return value


def _sanitize_text(text: str) -> str:
    """Remove sensitive patterns (API keys, tokens) from text."""
    for pattern in _SENSITIVE_PATTERNS:
        text = pattern.sub(
            lambda m: m.group(0).split("=", 1)[0] + "=***REDACTED***"
            if "=" in m.group(0)
            else m.group(0).split()[0] + " ***REDACTED***",
            text,
        )
    return text


class DebugCapture(star.Star):
    """Captures LLM pipeline state for debugging."""

    name = "debug_capture"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        # Instance-level storage (NOT shared across instances)
        self._captures: Dict[str, List[Dict[str, Any]]] = {}
        # Whether capture is enabled; can be toggled via config
        self._enabled: bool = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_captures(
        self, bot_id: str, channel_id: str = "", limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retrieve debug captures from local memory.

        Args:
            bot_id: Caller bot identifier (for access tracing).
            channel_id: If non-empty, only return captures for this channel.
            limit: Maximum number of captures to return (default 20, max 100).

        Returns:
            List of capture records sorted newest-first.
        """
        if not bot_id:
            logger.warning("get_captures called without bot_id — returning empty")
            return []

        limit = max(1, min(limit, 100))

        if channel_id:
            captures = self._captures.get(channel_id, [])
        else:
            captures = []
            for caps in self._captures.values():
                captures.extend(caps)

        captures.sort(key=lambda c: c.get("timestamp", ""), reverse=True)
        return captures[:limit]

    # ------------------------------------------------------------------
    # Handler
    # ------------------------------------------------------------------

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Capture pipeline state from event extras and response result.

        Should be placed late in the star chain so all upstream extras
        (system_prompt, history, llm_messages, etc.) are available.
        """
        # Check enabled flag from config
        try:
            config = self.context.get_config()
            if config and not config.get("debug_capture_enabled", self._enabled):
                return
        except Exception:
            pass  # If config read fails, proceed with default enabled

        try:
            await self._capture(event)
        except Exception as e:
            logger.debug("DebugCapture failed: %s", e)

    async def _capture(self, event: AstrMessageEvent) -> None:
        """Extract capture data from the event and store in local memory."""
        result = event.get_result()
        if result is None:
            return  # No LLM response — nothing meaningful to capture

        # ---- Identify the channel this capture belongs to ----
        channel_id = (
            event.get_group_id() if hasattr(event, "get_group_id") else ""
        )
        if not channel_id:
            channel_id = (
                event.get_session_id()
                if hasattr(event, "get_session_id")
                else "unknown"
            )
        guild_id = event.get_extra("guild_id", "") or None

        # ---- Trigger message ID ----
        trigger_message_id = str(getattr(event, "message_id", "")) or ""

        # ---- User info ----
        user_id = (
            event.get_sender_id() if hasattr(event, "get_sender_id") else "unknown"
        )
        user_name = (
            event.get_sender_name() if hasattr(event, "get_sender_name") else ""
        )
        user_display_name = event.get_extra("user_display_name", user_name)

        # ---- Pipeline state from event extras ----
        trigger_sources = event.get_extra("trigger_source", "unknown")
        plugin_outputs = event.get_extra("plugin_outputs", [])
        raw_user_message = event.get_extra(
            "raw_user_message",
            event.get_message_str() if hasattr(event, "get_message_str") else "",
        )
        formatted_user_request = event.get_extra("formatted_user_request", "")
        system_prompt = event.get_extra("system_prompt", "")
        history_for_llm = event.get_extra("history", [])
        llm_messages = event.get_extra("llm_messages", [])
        intermediate_llm_responses = event.get_extra(
            "intermediate_llm_responses", []
        )

        # ---- Response data from the result object ----
        raw_llm_response = getattr(result, "raw_response", "") or ""
        cleaned_llm_response = getattr(result, "message", "") or ""
        usage = getattr(result, "usage", None) or {}

        # ---- Provider / model from config ----
        config = self.context.get_config()
        provider = config.get("llm_provider", "") if config else ""
        model = config.get("model_name", "") if config else ""

        # ---- Sanitize sensitive content ----
        system_prompt = _sanitize_text(system_prompt)

        # ---- Truncate large fields to bound memory usage ----
        system_prompt = _truncate(system_prompt)
        raw_llm_response = _truncate(raw_llm_response)
        cleaned_llm_response = _truncate(cleaned_llm_response)
        raw_user_message = _truncate(raw_user_message, 2000)
        formatted_user_request = _truncate(formatted_user_request, 2000)

        # ---- Build capture record ----
        capture: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger_message_id": trigger_message_id,
            "channel_id": channel_id,
            "guild_id": guild_id,
            "user_id": user_id,
            "user_name": user_name,
            "user_display_name": user_display_name,
            "trigger_sources": trigger_sources,
            "plugin_outputs": plugin_outputs,
            "raw_user_message": raw_user_message,
            "formatted_user_request": formatted_user_request,
            "system_prompt": system_prompt,
            "history_for_llm": history_for_llm,
            "llm_messages": llm_messages,
            "intermediate_llm_responses": intermediate_llm_responses,
            "raw_llm_response": raw_llm_response,
            "cleaned_llm_response": cleaned_llm_response,
            "usage": usage,
            "provider": provider,
            "model": model,
        }

        # ---- Store in instance-level memory with eviction ----
        self._store_capture(channel_id, capture)

        logger.debug(
            "Debug capture stored: channel=%s msg=%s provider=%s model=%s",
            channel_id,
            trigger_message_id,
            provider,
            model,
        )

    def _store_capture(self, channel_id: str, capture: Dict[str, Any]) -> None:
        """Store a capture record, enforcing per-channel and global caps.

        Eviction policy (when global cap is exceeded):
        Remove the oldest capture from the channel with the oldest
        newest-capture timestamp (i.e. least recently active channel).
        """
        # Insert at front (newest first)
        channel_captures = self._captures.setdefault(channel_id, [])
        channel_captures.insert(0, capture)

        # Per-channel cap
        if len(channel_captures) > _MAX_CAPTURES_PER_CHANNEL:
            channel_captures.pop()

        # Global cap — evict from the staleest channel if exceeded
        total = sum(len(caps) for caps in self._captures.values())
        while total > _GLOBAL_MAX_CAPTURES:
            # Find the channel with the oldest newest-capture timestamp
            stalest_channel = min(
                self._captures,
                key=lambda cid: (
                    self._captures[cid][0].get("timestamp", "")
                    if self._captures[cid]
                    else ""
                ),
            )
            stalest_caps = self._captures[stalest_channel]
            if stalest_caps:
                stalest_caps.pop()  # remove oldest from stalest channel
                if not stalest_caps:
                    del self._captures[stalest_channel]
            total -= 1
