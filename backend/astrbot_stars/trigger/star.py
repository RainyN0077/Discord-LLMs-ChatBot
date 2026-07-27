"""Trigger Detection Star (AstrBot v4.26.2).

Determines whether the bot should respond to an incoming message.
Handles: @mention, reply-to-bot, keyword matching.
Auto-interject and repeat-parrot are in separate stars.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

logger = logging.getLogger(__name__)


class TriggerCheck(star.Star):
    """Detects whether the bot should wake and respond to a message."""

    name = "trigger_check"
    author = "Discord-LLMs-ChatBot"

    def __init__(self, context: star.Context) -> None:
        super().__init__(context)
        self._session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # IPC infrastructure (mirrors knowledge_bridge pattern)
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
            logger.debug("Trigger API GET %s: %s", endpoint, e)
            return {}

    # ------------------------------------------------------------------
    # Keyword matching
    # ------------------------------------------------------------------

    @staticmethod
    def _matches_keywords(
        text: str,
        keywords: List[str],
        match_mode: str = "contains",
        case_sensitive: bool = False,
    ) -> bool:
        if not keywords:
            return False
        compare_text = text if case_sensitive else text.lower()

        for kw in keywords:
            compare_kw = kw if case_sensitive else kw.lower()
            if match_mode == "contains" and compare_kw in compare_text:
                return True
            elif match_mode == "exact" and compare_text == compare_kw:
                return True
            elif match_mode == "starts_with" and compare_text.startswith(compare_kw):
                return True
            elif match_mode == "regex":
                try:
                    flags = 0 if case_sensitive else re.IGNORECASE
                    if re.search(kw, text, flags):
                        return True
                except re.error:
                    logger.warning("Invalid regex keyword: %s", kw)
        return False

    # ------------------------------------------------------------------
    # Wake detection
    # ------------------------------------------------------------------

    def _check_should_wake(
        self, event: AstrMessageEvent, config: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Determine if the bot should wake and the trigger source."""
        # @mention
        if event.is_at_or_wake_command:
            return True, "mention"

        # Reply-to-bot
        raw_msg = getattr(event, "message_obj", None)
        if raw_msg and hasattr(raw_msg, "raw_message"):
            msg = raw_msg.raw_message
            if hasattr(msg, "reference") and msg.reference:
                ref = msg.reference
                if hasattr(ref, "resolved") and ref.resolved:
                    resolved = ref.resolved
                    bot_id = str(event.get_self_id())
                    if hasattr(resolved, "author") and resolved.author:
                        if (
                            bot_id
                            and str(getattr(resolved.author, "id", "")) == bot_id
                        ):
                            return True, "reply"

        # Keyword matching
        keywords = config.get("trigger_keywords", [])
        match_mode = config.get("trigger_match_mode", "contains")
        case_sensitive = bool(config.get("trigger_case_sensitive", False))
        text = event.get_message_str()

        if self._matches_keywords(text, keywords, match_mode, case_sensitive):
            return True, "keyword"

        return False, ""

    # ------------------------------------------------------------------
    # User block check (user_options)
    # ------------------------------------------------------------------

    @staticmethod
    def _user_in_rule(rule: Dict[str, Any], user_id: str) -> bool:
        """Check if a user exists in a user_options rule's user list.

        Mirrors backend/app/core_logic/user_options_manager._user_in_rule.
        """
        users = rule.get("users") or {}
        user_id_str = str(user_id)
        for user_entry in users.values():
            if (
                isinstance(user_entry, dict)
                and str(user_entry.get("user_id", "")) == user_id_str
            ):
                return True
        return False

    @staticmethod
    def _find_user_in_rule(
        rule: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """Find a user's specific entry within a user_options rule.

        Returns the user entry dict or empty dict if not found.
        """
        users = rule.get("users") or {}
        user_id_str = str(user_id)
        for user_entry in users.values():
            if (
                isinstance(user_entry, dict)
                and str(user_entry.get("user_id", "")) == user_id_str
            ):
                return user_entry
        return {}

    @staticmethod
    def _match_user_rule(
        rules: Dict[str, Any],
        user_id: str,
        guild_id: Optional[str],
        channel_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Match a user to the most specific user_options rule.

        Priority: channel > guild > global > dm.
        Mirrors backend/app/core_logic/user_options_manager._match_rule.
        """
        channel_rule = None
        guild_rule = None
        global_rule = None
        dm_rule = None

        for rule in rules.values():
            if not isinstance(rule, dict):
                continue
            scope_type = rule.get("scope_type", "")
            scope_id = str(rule.get("scope_id", ""))
            if scope_type == "channel" and scope_id == channel_id:
                channel_rule = rule
            elif scope_type == "guild" and scope_id == guild_id:
                guild_rule = rule
            elif scope_type == "global" or (not scope_id and scope_type != "dm"):
                global_rule = rule
            elif scope_type == "dm" and scope_id == channel_id:
                dm_rule = rule

        for candidate in [
            channel_rule,
            guild_rule,
            global_rule,
            dm_rule,
        ]:
            if candidate and TriggerCheck._user_in_rule(candidate, user_id):
                return candidate
        return None

    async def _check_user_blocked(
        self, event: AstrMessageEvent, config: Dict[str, Any]
    ) -> bool:
        """Check if this user is blocked from response by user_options rules.

        Fetches the full config from the management layer via IPC (source of truth
        for user_options), then resolves the block decision locally.

        Returns True if the user is blocked and the trigger should stop
        (silently return without setting trigger_source).
        """
        # Fetch user_options from management layer via IPC
        ipc_config = await self._call_api("config")
        user_options = ipc_config.get("user_options", {})

        # If IPC returned empty or user_options is disabled, no blocking
        if not user_options or not user_options.get("enabled", False):
            return False

        guild_id = event.get_group_id()
        channel_id = event.get_session_id()
        user_id = event.get_sender_id()

        rules = user_options.get("rules", {})
        if not rules:
            return False

        rule = self._match_user_rule(rules, user_id, guild_id, channel_id)
        if not rule:
            return False

        mode = rule.get("mode", "blacklist")
        if mode == "blacklist":
            user_entry = self._find_user_in_rule(rule, user_id)
            blacklist_mode = (
                user_entry.get("blacklist_mode", "deny_response")
                if user_entry
                else "deny_response"
            )
            blocked = blacklist_mode in ("deny_response", "block_messages")
            logger.info(
                "Trigger user block check: user=%s mode=blacklist "
                "blacklist_mode=%s blocked=%s",
                user_id,
                blacklist_mode,
                blocked,
            )
            return blocked

        if mode == "whitelist":
            whitelist_behavior = rule.get("whitelist_behavior", "triggers_only")
            blocked = whitelist_behavior == "triggers_only"
            logger.info(
                "Trigger user block check: user=%s mode=whitelist "
                "whitelist_behavior=%s blocked=%s",
                user_id,
                whitelist_behavior,
                blocked,
            )
            return blocked

        logger.info(
            "Trigger user block check: user=%s unknown_mode=%s blocked=False",
            user_id,
            mode,
        )
        return False

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent) -> None:
        """Check if this message should wake the bot.

        Pipeline logic:
          1. Fetch local AstrBot config for trigger parameters.
          2. Check user_options blocking via IPC (management-layer source of truth).
             If blocked, return silently — let event flow through but don't wake.
          3. Check normal wake conditions (mention, reply, keyword).
             If none match, stop downstream stars and return.
          4. Set trigger_source extra for downstream stars.
        """
        config = self._get_config(event)
        if not config:
            return

        # ---- User block check ----
        if await self._check_user_blocked(event, config):
            logger.info(
                "Trigger blocked user=%s guild=%s channel=%s",
                event.get_sender_id(),
                event.get_group_id(),
                event.get_session_id(),
            )
            # Blocked: let event flow through but don't set trigger_source.
            return

        # ---- Trigger detection ----
        should_wake, trigger_source = self._check_should_wake(event, config)
        if not should_wake:
            # Stop downstream stars from processing this event.
            try:
                event.stop_event()
            except AttributeError:
                # stop_event not available in this AstrBot version;
                # fall back to silent return.
                pass
            return

        event.set_extra("trigger_source", trigger_source)
        logger.debug("TriggerCheck woke bot: source=%s", trigger_source)

    def _get_config(self, event: AstrMessageEvent) -> Dict[str, Any]:
        """Get bot config from the AstrBot context.

        Fallback to empty dict on any error (defence-in-depth).
        """
        try:
            return self.context.get_config(umo=event.unified_msg_origin)
        except Exception:
            return {}
