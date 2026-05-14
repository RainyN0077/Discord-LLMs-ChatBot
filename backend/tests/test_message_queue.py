import asyncio
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from app.handlers.message_queue import MessageQueue

pytestmark = [pytest.mark.unit]


class TestMessageQueue:
    @pytest.mark.asyncio
    async def test_enqueue_basic(self):
        mq = MessageQueue()
        result = await mq.enqueue("ch1", "item1")
        assert result is True
        q = mq._get_queue("ch1")
        assert q.qsize() == 1

    @pytest.mark.asyncio
    async def test_enqueue_queue_full_drops_oldest(self):
        mq = MessageQueue(max_size=2)
        await mq.enqueue("ch1", "item1")
        await mq.enqueue("ch1", "item2")
        result = await mq.enqueue("ch1", "item3")
        assert result is True
        q = mq._get_queue("ch1")
        assert q.qsize() == 2
        items = [q.get_nowait(), q.get_nowait()]
        assert "item1" not in items
        assert "item2" in items
        assert "item3" in items

    @pytest.mark.asyncio
    async def test_enqueue_queue_full_fails(self):
        mq = MessageQueue(max_size=1)
        await mq.enqueue("ch1", "item1")
        q = mq._get_queue("ch1")
        q.put_nowait = MagicMock(side_effect=asyncio.QueueFull)
        result = await mq.enqueue("ch1", "item2")
        assert result is False

    def test_get_queue_creates_new(self):
        mq = MessageQueue()
        q = mq._get_queue("ch1")
        assert isinstance(q, asyncio.Queue)

    def test_get_queue_caches_same_channel(self):
        mq = MessageQueue()
        q1 = mq._get_queue("ch1")
        q2 = mq._get_queue("ch1")
        assert q1 is q2

    def test_get_lock_creates_new(self):
        mq = MessageQueue()
        lock = mq._get_lock("ch1")
        assert isinstance(lock, asyncio.Lock)

    def test_get_lock_caches_same_channel(self):
        mq = MessageQueue()
        lock1 = mq._get_lock("ch1")
        lock2 = mq._get_lock("ch1")
        assert lock1 is lock2

    @pytest.mark.asyncio
    async def test_process_channel_timeout_cleanup(self):
        mq = MessageQueue()
        channel_id = "ch1"
        handler = AsyncMock()
        await mq.process_channel(channel_id, handler, timeout=0.01)
        assert channel_id not in mq._queues
        assert channel_id not in mq._locks

    @pytest.mark.asyncio
    async def test_process_channel_cancelled(self):
        mq = MessageQueue()
        await mq.enqueue("ch1", "item1")
        handler = AsyncMock()
        task = asyncio.create_task(mq.process_channel("ch1", handler))
        await asyncio.sleep(0.01)
        task.cancel()
        await task

    @pytest.mark.asyncio
    async def test_process_channel_handler_called(self):
        mq = MessageQueue()
        await mq.enqueue("ch1", "item1")
        handler = AsyncMock()
        await mq.process_channel("ch1", handler, timeout=0.01)
        handler.assert_called_once_with("item1")

    @pytest.mark.asyncio
    async def test_process_channel_multiple_items(self):
        mq = MessageQueue()
        await mq.enqueue("ch1", "i1")
        await mq.enqueue("ch1", "i2")
        await mq.enqueue("ch1", "i3")
        handler = AsyncMock()
        await mq.process_channel("ch1", handler, timeout=0.01)
        assert handler.call_count == 3
        handler.assert_has_calls([call("i1"), call("i2"), call("i3")])
