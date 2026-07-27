"""Plugin Bridge Star (AstrBot v4.26.2).

Bridges the legacy custom plugin system (plugins/manager.py) to AstrBot
via IPC calls to the management layer.

Design Decision (D-4): plugin_bridge does NOT load plugins directly in the
AstrBot subprocess (import path differences, plugin isolation). Instead, it
delegates all plugin message processing to the management-layer PluginManager
through the internal HTTP API at ``POST /{bot_id}/plugins/process_message``.

Result handling:
  - "consumed" → mark ``plugin_consumed`` on event extras and stop the
    pipeline (plugin fully handled the message).
  - "append"  → store ``plugin_append_blocks`` on event extras for
    downstream stars (e.g. context_assembler) to inject into the user
    message.
  - "none"    → continue normally.
"""

import logging
from typing import Any, Dict, Optional

import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class PluginBridge(star.Star):
    """Bridge to legacy plugin system in management layer.

    Delegates ``PluginManager.process_message()`` to the management server
    via internal HTTP IPC.  Never blocks the pipeline on failure.
    """

    name = "plugin_bridge"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        self._session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # IPC infrastructure (mirrors knowledge_bridge / trigger pattern)
    # ------------------------------------------------------------------

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

    async def _call_api(
        self, endpoint: str, payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """POST to the management-layer internal API with connection-pool reuse.

        Returns the JSON response dict on success, or empty dict on any
        failure (connection error, timeout, non-200 status).
        """
        config = self.context.get_config()
        internal = config.get("internal_api", {})
        base_url = internal.get("base_url", "http://127.0.0.1:8093/internal")
        token = internal.get("secret_token", "")
        bot_id = config.get("bot_id", "")

        url = f"{base_url}/{bot_id}/{endpoint}"
        headers = {"X-Internal-Token": token, "X-Bot-Id": bot_id}

        try:
            session = await self._get_session()
            async with session.post(
                url,
                json=payload or {},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                return await resp.json() if resp.status == 200 else {}
        except Exception as e:
            logger.debug("PluginBridge API POST %s: %s", endpoint, e)
            return {}

    # ------------------------------------------------------------------
    # Message data extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_message_data(event: AstrMessageEvent) -> Dict[str, Any]:
        """Extract serialisable message fields from the AstrBot event.

        Returns a dict matching the IPC endpoint's expected body schema.
        """
        # TODO: verify AstrBot API — get_message_str(), get_sender_id(),
        # get_session_id(), get_group_id() should be available.
        message_content = event.get_message_str()
        user_id = event.get_sender_id()
        channel_id = event.get_session_id()
        guild_id = event.get_group_id()

        # Attempt to extract author display information.
        # AstrBot may expose this via raw message_obj or via extra fields.
        author_name = ""
        author_display_name = ""
        try:
            raw_msg = getattr(event, "message_obj", None)
            if raw_msg:
                if hasattr(raw_msg, "author"):
                    author = raw_msg.author
                    author_name = getattr(author, "name", "") or ""
                    author_display_name = (
                        getattr(author, "display_name", "") or author_name
                    )
                elif hasattr(raw_msg, "sender"):
                    sender = raw_msg.sender
                    author_name = getattr(sender, "nickname", "") or ""
                    author_display_name = author_name
        except Exception:
            pass

        return {
            "message_content": message_content,
            "user_id": user_id,
            "channel_id": channel_id,
            "guild_id": guild_id,
            "author_name": author_name,
            "author_display_name": author_display_name,
        }

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Allow legacy plugins to handle the message via IPC.

        Pipeline:
          1. Extract message data and config.
          2. POST to ``/plugins/process_message``.
          3. Handle the response:
             - ``consumed`` → stop the event pipeline.
             - ``append``   → inject append blocks into event extras.
             - ``none``     → continue.
          4. On any IPC failure → skip (log and continue).
        """
        # ---- Step 1: Extract payload and config ----
        payload = self._extract_message_data(event)
        config = self.context.get_config()

        # Include the bot's plugins config so the management layer knows
        # which plugins to activate for this bot instance.
        plugins_config = config.get("plugins", {})
        if plugins_config:
            payload["plugins_config"] = plugins_config

        # ---- Step 2: IPC call to management-layer PluginManager ----
        result = await self._call_api("plugins/process_message", payload)

        # ---- Step 3: Handle response ----
        response_result = result.get("result", "none")

        if response_result == "consumed":
            # Plugin fully handled the message — stop downstream stars.
            event.set_extra("plugin_consumed", True)
            logger.info("Plugin bridge: message consumed by legacy plugin")
            # TODO: verify AstrBot API — event.stop_event() should be available.
            try:
                event.stop_event()
            except AttributeError:
                pass
            return

        if response_result == "append":
            append_blocks = result.get("append_blocks")
            if append_blocks:
                event.set_extra("plugin_append_blocks", append_blocks)
                logger.info(
                    "Plugin bridge: %d append blocks injected",
                    len(append_blocks),
                )

        # "none" or unknown → continue normally
        logger.debug("Plugin bridge: result=%s", response_result)
