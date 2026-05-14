import threading
import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_SIZE = 50
DEFAULT_TIMEOUT_SECONDS = 120


class MessageQueue:
    def __init__(self, max_size: int = DEFAULT_QUEUE_SIZE):
        self._max_size = max_size
        self._queues: Dict[str, asyncio.Queue] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
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
            except asyncio.TimeoutError:
                if q.empty():
                    del self._queues[channel_id]
                    del self._locks[channel_id]
                    logger.info("Channel %s queue idle, cleaned up", channel_id)
                    return
            except asyncio.CancelledError:
                logger.info("Channel %s queue processing cancelled", channel_id)
                return
            except Exception:
                logger.exception("Error processing queued message in channel %s", channel_id)
                try:
                    q.put_nowait(item)
                except (UnboundLocalError, NameError):
                    pass
                except asyncio.QueueFull:
                    logger.warning("Channel %s queue full, also dropping previously dequeued message", channel_id)
