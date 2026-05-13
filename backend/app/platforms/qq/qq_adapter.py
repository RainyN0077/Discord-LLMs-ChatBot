import asyncio
import logging
import re
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from .onebot_client import OneBotClient
from .message_converter import (
    convert_to_platform_message,
    extract_cq_images,
    QQ_ROLE_MAP,
    strip_cq_codes,
)
from ..models import PlatformMessage, PlatformUser

from ...utils import matches_trigger_keywords, split_message, download_image
from ...ocr_service import is_multimodal_llm, extract_ocr_text
from ...config_cache import load_config

logger = logging.getLogger(__name__)


class QQAdapter:
    def __init__(self, config: Dict[str, Any]):
        qq_config = config.get("qq_bot", {})
        self.config = config
        self.qq_config = qq_config
        self.onebot = OneBotClient(
            napcat_http_url=qq_config.get("napcat_http_url", "http://127.0.0.1:3000"),
            ws_host="127.0.0.1",
            ws_port=qq_config.get("napcat_ws_port", 8095),
            ws_path=qq_config.get("napcat_ws_path", "/qq/ws"),
        )
        self.group_role_cache: Dict[str, Dict[str, str]] = {}
        self.message_history: Dict[str, deque] = {}
        self._send_lock = asyncio.Lock()
        self._last_send_time: Dict[str, float] = {}
        self._running = False
        self._ws_task: Optional[asyncio.Task] = None
        self._message_handler: Optional[Callable] = None

    def set_message_handler(self, handler: Callable) -> None:
        self._message_handler = handler

    async def start(self) -> None:
        import uvicorn

        self._running = True
        await self.onebot.start()
        self.onebot.add_event_handler(self._on_event)

        ws_port = self.qq_config.get("napcat_ws_port", 8095)
        ws_host = "127.0.0.1"

        class _WSApp:
            def __init__(self, adapter):
                self.adapter = adapter

            async def __call__(self, scope, receive, send):
                if scope["type"] == "websocket":
                    from starlette.websockets import WebSocket
                    ws = WebSocket(scope, receive=receive, send=send)
                    await self.adapter.onebot._handle_websocket(ws)

        ws_app = _WSApp(self)
        config = uvicorn.Config(
            app=ws_app,
            host=ws_host,
            port=ws_port,
            log_level="warning",
            ws="wsproto",
        )
        server = uvicorn.Server(config)

        self._ws_task = asyncio.create_task(server.serve())
        logger.info("QQ WebSocket server started on ws://%s:%s%s", ws_host, ws_port, self.qq_config.get("napcat_ws_path", "/qq/ws"))

    async def stop(self) -> None:
        self._running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        await self.onebot.stop()

    async def _on_event(self, event: Dict[str, Any]) -> None:
        plat_msg = convert_to_platform_message(event)
        if not plat_msg:
            return

        if plat_msg.author.is_bot:
            return

        qq_config = load_config().get("qq_bot", {})
        if not qq_config.get("enabled", False):
            return

        allowed_groups = qq_config.get("allowed_group_ids", [])
        blocked_groups = qq_config.get("blocked_group_ids", [])
        channel_id = plat_msg.channel.id

        if blocked_groups and channel_id in blocked_groups:
            return

        if allowed_groups and channel_id not in allowed_groups:
            return

        if self._message_handler:
            try:
                await self._message_handler(plat_msg)
            except Exception:
                logger.error("Error in QQ message handler", exc_info=True)

    async def _get_sender_role(self, group_id: str, user_id: str) -> str:
        if group_id not in self.group_role_cache:
            self.group_role_cache[group_id] = {}

        if user_id in self.group_role_cache[group_id]:
            return self.group_role_cache[group_id][user_id]

        try:
            member_info = await self.onebot.get_group_member_info(group_id, user_id)
            if member_info:
                role = member_info.get("role", "member")
                self.group_role_cache[group_id][user_id] = role
                return role
        except Exception:
            logger.warning("Failed to get member info for %s in group %s", user_id, group_id, exc_info=True)

        self.group_role_cache[group_id][user_id] = "member"
        return "member"

    async def _download_qq_images(self, plat_msg: PlatformMessage) -> List[Dict[str, Any]]:
        images = extract_cq_images(plat_msg.content)
        downloaded: List[Dict[str, Any]] = []
        seen_urls: set = set()

        for img in images:
            url = img.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            try:
                img_data = await asyncio.wait_for(download_image(url), timeout=10.0)
                if img_data:
                    downloaded.append({
                        "bytes": img_data,
                        "url": url,
                        "kind": img.get("kind", "cq_image"),
                        "source": "QQ图片",
                    })
            except asyncio.TimeoutError:
                logger.warning("QQ image download timed out: %s", url)
            except Exception:
                logger.warning("Failed to download QQ image: %s", url, exc_info=True)

        return downloaded

    async def _send_response(self, plat_msg: PlatformMessage, text: str) -> None:
        config = load_config()
        qq_config = config.get("qq_bot", {})
        max_len = qq_config.get("max_split_length", 2000)
        chunks = split_message(text.strip(), max_len)

        channel_id = plat_msg.channel.id
        now = datetime.now(timezone.utc).timestamp()

        async with self._send_lock:
            last_time = self._last_send_time.get(channel_id, 0)
            elapsed = now - last_time
            if elapsed < 3.0:
                await asyncio.sleep(3.0 - elapsed)
            self._last_send_time[channel_id] = datetime.now(timezone.utc).timestamp()

        if plat_msg.guild:
            send_func = self.onebot.send_group_msg
            target_id = channel_id
        else:
            send_func = self.onebot.send_private_msg
            target_id = plat_msg.author.id

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            try:
                await send_func(target_id, chunk)
            except Exception:
                logger.error("Failed to send QQ message chunk %d", i, exc_info=True)
            if i < len(chunks) - 1:
                await asyncio.sleep(0.5)

    def _get_qq_role_config(
        self, role: str, role_based_configs: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        mapped_role = QQ_ROLE_MAP.get(role, "qq_group_member")
        for cfg in role_based_configs.values():
            if cfg.get("id") == mapped_role:
                return mapped_role, cfg
        return None, None

    def _add_to_history(self, plat_msg: PlatformMessage) -> None:
        channel_key = plat_msg.channel.id
        if channel_key not in self.message_history:
            self.message_history[channel_key] = deque(maxlen=50)
        self.message_history[channel_key].append(plat_msg)

    def _get_channel_history(self, channel_id: str) -> List[PlatformMessage]:
        return list(self.message_history.get(channel_id, []))

    async def refresh_group_cache(self, group_id: str) -> None:
        try:
            members = await self.onebot.get_group_member_list(group_id)
            if group_id not in self.group_role_cache:
                self.group_role_cache[group_id] = {}
            for member in members:
                user_id = str(member.get("user_id", ""))
                role = member.get("role", "member")
                self.group_role_cache[group_id][user_id] = role
            logger.info("Refreshed QQ group %s cache: %d members", group_id, len(members))
        except Exception:
            logger.warning("Failed to refresh group %s cache", group_id, exc_info=True)
