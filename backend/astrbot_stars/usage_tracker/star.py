"""Usage Tracker Star (AstrBot v4.26.2).

Records LLM token usage to the management layer via internal HTTP API.
Fire-and-forget: never blocks or raises errors to the user.
"""

import logging
from typing import Any, Dict, Optional

import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class UsageTracker(star.Star):
    """Records LLM token usage to management layer."""

    name = "usage_tracker"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared aiohttp client session (connection pool reuse)."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def __del__(self) -> None:
        """Best-effort cleanup of the shared session on star destruction."""
        if self._session is not None and not self._session.closed:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._session.close())
                else:
                    loop.run_until_complete(self._session.close())
            except Exception:
                logger.debug("Failed to close aiohttp session on cleanup")

    async def _call_api(self, endpoint: str, method: str = "POST",
                        payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call the management-layer internal API with connection-pool reuse."""
        config = self.context.get_config()
        internal = config.get("internal_api", {})
        base_url = internal.get("base_url", "http://127.0.0.1:8093/internal")
        token = internal.get("secret_token", "")
        bot_id = config.get("bot_id", "")

        url = f"{base_url}/{bot_id}/{endpoint}"
        headers = {"X-Internal-Token": token, "X-Bot-Id": bot_id}

        try:
            session = await self._get_session()
            if method == "POST":
                async with session.post(url, json=payload or {}, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    return await resp.json() if resp.status == 200 else {}
            else:
                async with session.get(url, headers=headers,
                                       timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    return await resp.json() if resp.status == 200 else {}
        except Exception as e:
            logger.debug("UsageTracker API %s %s: %s", method, endpoint, e)
            return {}

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Record LLM token usage for the current response.

        Extracts usage data from ``event.get_result()``, user/channel info
        from the event, and provider/model from config.  Posts the payload
        to the management-layer ``/usage/track`` endpoint.

        Fire-and-forget — never raises or blocks.
        """
        result = event.get_result()
        if result is None:
            return

        # ---- Extract usage data ----
        # TODO: verify AstrBot API — LLMResponse may carry usage differently.
        # Current assumption: result has .input_tokens / .output_tokens attrs,
        # or .usage dict, or we fall back to estimation.
        input_tokens: int = 0
        output_tokens: int = 0

        usage = getattr(result, "usage", None)
        if isinstance(usage, dict):
            input_tokens = usage.get("input_tokens", 0) or 0
            output_tokens = usage.get("output_tokens", 0) or 0
        elif hasattr(result, "input_tokens"):
            input_tokens = getattr(result, "input_tokens", 0) or 0
            output_tokens = getattr(result, "output_tokens", 0) or 0
        else:
            # Fallback: rough estimate from message length
            msg = getattr(result, "message", "") or ""
            estimated = max(1, len(msg) // 4)
            output_tokens = estimated
            logger.debug("No usage data available, estimated %d output tokens", estimated)

        # ---- Extract user/channel info from event ----
        # TODO: verify AstrBot API — event.get_sender_id() etc.
        user_id = event.get_sender_id() if hasattr(event, "get_sender_id") else ""
        user_name = event.get_sender_name() if hasattr(event, "get_sender_name") else ""
        # TODO: AstrMessageEvent may not provide display_name directly.
        user_display_name = user_name
        channel_id = event.get_group_id() if hasattr(event, "get_group_id") else ""
        if not channel_id:
            channel_id = event.get_session_id() if hasattr(event, "get_session_id") else ""

        # ---- Extract provider/model from config ----
        config = self.context.get_config()
        provider = config.get("llm_provider", "") if config else ""
        model = config.get("model_name", "") if config else ""

        # ---- Build and fire the usage track request ----
        payload: Dict[str, Any] = {
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "user_id": user_id,
            "user_name": user_name,
            "user_display_name": user_display_name,
            # role_id / role_name — not available from AstrMessageEvent;
            # can be extended when AstrBot provides role information.
            "role_id": None,
            "role_name": None,
            "channel_id": channel_id,
            # channel_name / guild_id / guild_name — not available from
            # AstrMessageEvent in the current abstraction layer.
            "channel_name": "",
            "guild_id": None,
            "guild_name": None,
        }

        try:
            await self._call_api("usage/track", payload=payload)
            logger.debug(
                "Usage tracked: provider=%s model=%s in=%d out=%d user=%s",
                provider, model, input_tokens, output_tokens, user_id,
            )
        except Exception as e:
            # Fire-and-forget: never raise to the caller.
            logger.debug("Failed to track usage: %s", e)
