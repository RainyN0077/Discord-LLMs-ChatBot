"""Persona Star (AstrBot v4.26.2).

Retrieves and injects user persona data into the LLM context.
Persona data is passed via event extras for context_assembler to consume.
"""

import logging
from typing import Any, Dict, Optional

import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class Persona(star.Star):
    """Retrieves user persona from management layer via IPC.

    Design (D-1):
      - Does NOT directly modify system_prompt.
      - Sets ``event.set_extra("user_persona", dict)``.
      - Downstream context_assembler star reads the extra and injects
        persona into the system prompt.
      - IPC failure degrades gracefully: sets empty dict and continues.
    """

    name = "persona"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        self._session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # IPC infrastructure (matches knowledge_bridge pattern)
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

    async def _call_api(self, endpoint: str) -> Dict[str, Any]:
        """Call the management-layer internal API with connection-pool reuse.

        Returns the JSON response dict on success, or empty dict on any failure.
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
            async with session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                return await resp.json() if resp.status == 200 else {}
        except Exception as e:
            logger.debug("Persona API GET %s: %s", endpoint, e)
            return {}

    # ------------------------------------------------------------------
    # Handler
    # ------------------------------------------------------------------

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Inject persona for the message sender.

        Fetches persona data from the management-layer IPC endpoint
        ``GET /{bot_id}/persona/{user_id}`` and stores it as event extra.

        The IPC endpoint returns::

            {"user_id": "...", "persona": {"prompt": "...", "nickname": "...", ...}}

        We extract the inner ``persona`` dict for downstream consumption.
        On any failure (network, 4xx/5xx, missing config), we set an empty
        dict and continue — never block the pipeline.
        """
        user_id = event.get_sender_id()

        # ---- Extract persona via IPC ----
        endpoint = f"persona/{user_id}"
        result = await self._call_api(endpoint)

        # Extract the inner persona dict from the response envelope.
        # IPC returns {"user_id": "...", "persona": {...}}.
        persona: Dict[str, Any] = result.get("persona", {}) if result else {}

        # ---- Inject into event extras for downstream stars ----
        # context_assembler reads this extra and calls _inject_persona().
        event.set_extra("user_persona", persona)

        # NOTE: context_assembler also reads event.get_extra("user_role_id", "")
        # for role-based config resolution (Priority 1 in _resolve_role_config).
        # The persona IPC endpoint (persona/{user_id}) does not currently return
        # Discord role information, so user_role_id is NOT set here.
        # Context_assembler falls back to Priority 2 (match by user_id) when
        # user_role_id is absent, so role-based config still works for simple
        # setups where role IDs equal user IDs.
        # TODO: Enrich the management-layer persona endpoint to include Discord
        # role information so this star can set event.set_extra("user_role_id", role_id).

        if persona:
            logger.debug("Persona injected for user %s", user_id)
        else:
            logger.debug("No persona found for user %s", user_id)
