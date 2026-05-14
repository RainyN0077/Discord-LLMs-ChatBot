import threading
import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_SIZE = 50
DEFAULT_TIMEOUT_SECONDS = 120


def _make_item_key(item: Any) -> str:
    if not isinstance(item, dict):
        return str(id(item))
    msg_ctx = item.get("message_ctx")
    msg_id = getattr(msg_ctx, "id", id(item)) if msg_ctx else id(item)
    return str(msg_id)


class MessageQueue:
    def __init__(self, max_size: int = DEFAULT_QUEUE_SIZE):
        self._max_size = max_size
        self._queues: Dict[str, asyncio.Queue] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._fail_counts: Dict[str, int] = {}
        self._dicts_guard = threading.Lock()

    def _get_queue(self, channel_id: str) -> asyncio.Queue:
        with self._dicts_guard:
            if channel_id not in self._queues:
                self._queues[channel_id] = asyncio.Queue(maxsize=self._max_size)
            return self._queues[channel_id]

    def _get_lock(self, channel_id: str) -> asyncio.Lock:
        with self._dicts_guard:
            if channel_id not in self._locks:
                self._locks[channel_id] = asyncio.Lock()
            return self._locks[channel_id]

    async def enqueue(self, channel_id: str, item: Any) -> bool:
        q = self._get_queue(channel_id)
        try:
            q.put_nowait(item)
            logger.info("Enqueued message in channel %s (queue size: %s)", channel_id, q.qsize())
            return True
        except asyncio.QueueFull:
            q.get_nowait()
            try:
                q.put_nowait(item)
                logger.warning("Channel %s queue full, dropped oldest message", channel_id)
                return True
            except asyncio.QueueFull:
                logger.warning("Channel %s queue full, could not enqueue", channel_id)
                return False

    async def process_channel(
        self,
        channel_id: str,
        handler: Callable[[Any], Coroutine[Any, Any, None]],
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        lock = self._get_lock(channel_id)
        q = self._get_queue(channel_id)
        while True:
            try:
                async with lock:
                    item = await asyncio.wait_for(q.get(), timeout=timeout)
                await handler(item)
                self._fail_counts.pop(_make_item_key(item), None)
            except asyncio.TimeoutError:
                if q.empty():
                    with self._dicts_guard:
                        self._queues.pop(channel_id, None)
                        self._locks.pop(channel_id, None)
                    logger.info("Channel %s queue idle, cleaned up", channel_id)
                    return
            except asyncio.CancelledError:
                logger.info("Channel %s queue processing cancelled", channel_id)
                try:
                    self._fail_counts.pop(_make_item_key(item), None)
                except (UnboundLocalError, NameError):
                    pass
                return
            except Exception:
                logger.exception("Error processing queued message in channel %s", channel_id)
                item_key = _make_item_key(item)
                fail_count = self._fail_counts.get(item_key, 0) + 1
                self._fail_counts[item_key] = fail_count
                if fail_count < 3:
                    logger.warning("Re-queuing failed message in channel %s (attempt %s)", channel_id, fail_count)
                    try:
                        q.put_nowait(item)
                    except asyncio.QueueFull:
                        logger.warning("Channel %s queue full, dropping failed message", channel_id)
                else:
                    logger.warning("Dropping message in channel %s after %s failures", channel_id, fail_count)
                    self._fail_counts.pop(item_key, None)
