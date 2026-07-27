"""Interaction Recorder Star (AstrBot v4.26.2).

Records user messages and bot replies to the management layer via
internal HTTP API.  Runs on every message event — when the LLM has not
yet responded it records the user's incoming message (is_bot_reply=False),
and when a bot response is present it also records the reply
(is_bot_reply=True).

Fire-and-forget: never blocks or raises errors to the caller.
"""

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class InteractionRecorder(star.Star):
    """Records user messages and bot replies to management layer."""

    name = "interaction_recorder"
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

    async def _call_api(
        self,
        endpoint: str,
        method: str = "POST",
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call the management-layer internal API with connection-pool reuse."""
        config = self.context.get_config()
        internal = config.get("internal_api", {})
        base_url = internal.get("base_url", "http://127.0.0.1:8093/internal")
        token = internal.get("secret_token", "")
        bot_id = config.get("bot_id", "")

        if not token or not bot_id:
            return {}

        url = f"{base_url}/{bot_id}/{endpoint}"
        headers = {"X-Internal-Token": token, "X-Bot-Id": bot_id}

        try:
            session = await self._get_session()
            if method == "POST":
                async with session.post(
                    url,
                    json=payload or {},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    return await resp.json() if resp.status == 200 else {}
            else:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    return await resp.json() if resp.status == 200 else {}
        except Exception as e:
            logger.debug("InteractionRecorder API %s %s: %s", method, endpoint, e)
            return {}

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Record incoming user message and, if a bot response exists, the reply."""
        config = self.context.get_config()
        internal = config.get("internal_api", {})
        if not internal:
            return

        # ---- Extract common fields from event ----
        # TODO: verify AstrBot API — get_sender_id(), get_sender_name(), etc.
        member_id = (
            event.get_sender_id() if hasattr(event, "get_sender_id") else "unknown"
        )
        member_name = (
            event.get_sender_name() if hasattr(event, "get_sender_name") else ""
        )
        message_text = (
            event.get_message_str() if hasattr(event, "get_message_str") else ""
        )
        channel_id = (
            event.get_group_id() if hasattr(event, "get_group_id") else ""
        )
        if not channel_id:
            channel_id = (
                event.get_session_id()
                if hasattr(event, "get_session_id")
                else ""
            )

        # TODO: verify AstrBot API — guild_id, message_id, attachments,
        # role_id may not be available directly from AstrMessageEvent.
        guild_id = config.get("guild_id", "dm")
        message_id = str(getattr(event, "message_id", "")) or ""
        role_id = "default"

        # ---- Extract image attachments if available ----
        # TODO: verify AstrBot API — message_obj / chain structure.
        attachments: List[str] = []
        if hasattr(event, "message_obj") and event.message_obj:
            try:
                for seg in getattr(event.message_obj, "chain", []):
                    if getattr(seg, "type", "") == "image":
                        url = (
                            getattr(seg, "url", "")
                            or getattr(seg, "file", "")
                            or ""
                        )
                        if url:
                            attachments.append(url)
            except Exception:
                pass

        # Read trigger_source from event extras (set by trigger Star).
        trigger_source = event.get_extra("trigger_source", "unknown")

        # ---- Record user message (fire-and-forget) ----
        try:
            await self._record_via_api(
                guild_id=guild_id,
                channel_id=channel_id,
                member_id=member_id,
                member_name=member_name,
                role_id=role_id,
                content=message_text,
                message_id=message_id,
                attachments=attachments,
                is_bot_reply=False,
                trigger_source=trigger_source,
            )
            logger.debug(
                "User interaction recorded: channel=%s user=%s source=%s",
                channel_id,
                member_id,
                trigger_source,
            )
        except Exception as e:
            logger.debug("Failed to record user interaction: %s", e)

        # ---- Also record bot reply if the LLM has already produced one ----
        result = event.get_result()
        if result is not None and hasattr(result, "message") and result.message:
            bot_content = result.message
            if isinstance(bot_content, str) and bot_content.strip():
                try:
                    reply_message_id = (
                        "bot_reply_" + message_id if message_id else ""
                    )
                    await self._record_via_api(
                        guild_id=guild_id,
                        channel_id=channel_id,
                        member_id=member_id,
                        member_name=member_name,
                        role_id=role_id,
                        content=bot_content,
                        message_id=reply_message_id,
                        attachments=[],
                        is_bot_reply=True,
                        trigger_source=trigger_source,
                    )
                    logger.debug(
                        "Bot reply interaction recorded: channel=%s",
                        channel_id,
                    )
                except Exception as e:
                    logger.debug(
                        "Failed to record bot reply interaction: %s", e
                    )

    async def _record_via_api(
        self,
        guild_id: str,
        channel_id: str,
        member_id: str,
        member_name: str,
        role_id: str,
        content: str,
        message_id: str,
        attachments: List[str],
        is_bot_reply: bool,
        trigger_source: str,
    ) -> None:
        """POST a single interaction record to the management-layer API."""
        await self._call_api(
            "interaction/record",
            payload={
                "guild_id": guild_id,
                "channel_id": channel_id,
                "member_id": member_id,
                "member_name": member_name,
                "role_id": role_id,
                "content": content,
                "message_id": message_id,
                "attachments": attachments,
                "is_bot_reply": is_bot_reply,
                "trigger_source": trigger_source,
            },
        )
