import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

import aiohttp
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

logger = logging.getLogger(__name__)

EventHandler = Callable[[Dict[str, Any]], Awaitable[None]]


class OneBotClient:
    def __init__(
        self,
        napcat_http_url: str = "http://127.0.0.1:3000",
        ws_host: str = "127.0.0.1",
        ws_port: int = 8095,
        ws_path: str = "/qq/ws",
    ):
        self.napcat_http_url = napcat_http_url.rstrip("/")
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.ws_path = ws_path
        self._event_handlers: List[EventHandler] = []
        self._connected_clients: Dict[str, WebSocket] = {}
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._server: Optional[asyncio.AbstractServer] = None
        self._running = False

    def add_event_handler(self, handler: EventHandler) -> None:
        self._event_handlers.append(handler)

    async def _broadcast_event(self, event: Dict[str, Any]) -> None:
        for handler in self._event_handlers:
            try:
                await handler(event)
            except Exception:
                logger.error("Error in QQ event handler", exc_info=True)

    async def _handle_websocket(self, ws: WebSocket) -> None:
        await ws.accept()
        client_id = f"{ws.client.host}:{ws.client.port}" if ws.client else "unknown"
        logger.info("QQ WebSocket client connected: %s", client_id)

        # NapCatQQ uses X-Client-Role: Universal for bidirectional communication
        headers = dict(ws.headers)
        client_role = headers.get("x-client-role", "unknown")
        logger.info("QQ WebSocket client role: %s", client_role)

        self._connected_clients[client_id] = ws

        try:
            while self._running and ws.client_state == WebSocketState.CONNECTED:
                try:
                    data = await asyncio.wait_for(ws.receive_json(), timeout=30.0)
                except asyncio.TimeoutError:
                    if ws.client_state == WebSocketState.CONNECTED:
                        continue
                    break

                post_type = data.get("post_type", "")
                if post_type == "meta_event":
                    meta_type = data.get("meta_event_type", "")
                    if meta_type == "heartbeat":
                        continue
                    logger.debug("QQ meta_event: %s", meta_type)
                    continue

                await self._broadcast_event(data)
        except WebSocketDisconnect:
            logger.info("QQ WebSocket client disconnected: %s", client_id)
        except Exception:
            logger.error("QQ WebSocket error for %s", client_id, exc_info=True)
        finally:
            self._connected_clients.pop(client_id, None)
            if ws.client_state != WebSocketState.DISCONNECTED:
                try:
                    await ws.close()
                except Exception:
                    pass

    async def _ws_app(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope["type"] != "websocket":
            return
        ws = WebSocket(scope, receive=receive, send=send)
        await self._handle_websocket(ws)

    async def start(self) -> None:
        self._running = True
        self._http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
        )

    async def stop(self) -> None:
        self._running = False
        if self._http_session:
            await self._http_session.close()
            self._http_session = None
        for client_id, ws in list(self._connected_clients.items()):
            try:
                await ws.close()
            except Exception:
                pass
            self._connected_clients.pop(client_id, None)

    @property
    def ws_app(self):
        return self._ws_app

    async def _http_post(self, endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._http_session:
            logger.error("HTTP session not initialized")
            return None
        url = f"{self.napcat_http_url}/{endpoint.lstrip('/')}"
        try:
            async with self._http_session.post(url, json=payload) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    logger.warning(
                        "NapCatQQ HTTP %s returned %s: %s",
                        endpoint, resp.status, text[:200],
                    )
                    return None
        except asyncio.TimeoutError:
            logger.warning("NapCatQQ HTTP %s timed out", endpoint)
            return None
        except Exception:
            logger.error("NapCatQQ HTTP %s failed", endpoint, exc_info=True)
            return None

    async def send_group_msg(
        self, group_id: str, message: str, auto_escape: bool = False
    ) -> Optional[str]:
        payload = {
            "group_id": int(group_id),
            "message": message,
            "auto_escape": auto_escape,
        }
        result = await self._http_post("send_group_msg", payload)
        if result and result.get("status") == "ok":
            return str(result.get("data", {}).get("message_id", ""))
        return None

    async def send_private_msg(
        self, user_id: str, message: str, auto_escape: bool = False
    ) -> Optional[str]:
        payload = {
            "user_id": int(user_id),
            "message": message,
            "auto_escape": auto_escape,
        }
        result = await self._http_post("send_private_msg", payload)
        if result and result.get("status") == "ok":
            return str(result.get("data", {}).get("message_id", ""))
        return None

    async def get_group_member_list(self, group_id: str) -> List[Dict[str, Any]]:
        payload = {"group_id": int(group_id), "no_cache": False}
        result = await self._http_post("get_group_member_list", payload)
        if result and result.get("status") == "ok":
            return result.get("data", [])
        return []

    async def get_group_member_info(
        self, group_id: str, user_id: str, no_cache: bool = False
    ) -> Optional[Dict[str, Any]]:
        payload = {
            "group_id": int(group_id),
            "user_id": int(user_id),
            "no_cache": no_cache,
        }
        result = await self._http_post("get_group_member_info", payload)
        if result and result.get("status") == "ok":
            return result.get("data")
        return None

    async def get_msg(self, message_id: int) -> Optional[Dict[str, Any]]:
        payload = {"message_id": message_id}
        result = await self._http_post("get_msg", payload)
        if result and result.get("status") == "ok":
            return result.get("data")
        return None
