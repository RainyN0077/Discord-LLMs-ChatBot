"""Tests for app.debug_capture_store."""
import asyncio
import pytest
from app.debug_capture_store import (
    add_capture, list_captures, get_capture, delete_capture, clear_captures,
    MAX_CAPTURE_RECORDS,
)


class TestAddCapture:
    @pytest.mark.asyncio
    async def test_adds_record_with_id_and_timestamp(self):
        item = await add_capture({"message": "test"})
        assert "id" in item
        assert "captured_at" in item
        assert item["message"] == "test"

    @pytest.mark.asyncio
    async def test_does_not_modify_original(self):
        original = {"message": "original"}
        await add_capture(original)
        assert "id" not in original

    @pytest.mark.asyncio
    async def test_adds_to_front(self):
        await add_capture({"n": 1})
        await add_capture({"n": 2})
        captures = await list_captures(limit=5)
        assert captures[0]["n"] == 2
        assert captures[1]["n"] == 1

    @pytest.mark.asyncio
    async def test_enforces_max_capacity(self):
        for i in range(MAX_CAPTURE_RECORDS + 20):
            await add_capture({"n": i})
        captures = await list_captures(limit=MAX_CAPTURE_RECORDS + 10)
        assert len(captures) == MAX_CAPTURE_RECORDS
        assert captures[0]["n"] == MAX_CAPTURE_RECORDS + 19

    @pytest.mark.asyncio
    async def test_handles_none_input(self):
        item = await add_capture(None)
        assert "id" in item


class TestListCaptures:
    @pytest.mark.asyncio
    async def test_default_limit_20(self):
        for i in range(30):
            await add_capture({"n": i})
        results = await list_captures()
        assert len(results) == 20

    @pytest.mark.asyncio
    async def test_custom_limit(self):
        for i in range(10):
            await add_capture({"n": i})
        results = await list_captures(limit=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_limit_clamped(self):
        results = await list_captures(limit=999)
        assert len(results) <= 100

    @pytest.mark.asyncio
    async def test_filter_by_channel(self):
        await add_capture({"n": 1, "channel_id": "ch_a"})
        await add_capture({"n": 2, "channel_id": "ch_b"})
        await add_capture({"n": 3, "channel_id": "ch_a"})
        results = await list_captures(limit=10, channel_id="ch_a")
        assert len(results) == 2
        assert all(r["channel_id"] == "ch_a" for r in results)

    @pytest.mark.asyncio
    async def test_returns_deep_copy(self):
        await add_capture({"nested": {"key": "value"}})
        results = await list_captures(limit=1)
        results[0]["nested"]["key"] = "modified"
        results2 = await list_captures(limit=1)
        assert results2[0]["nested"]["key"] == "value"


class TestGetCapture:
    @pytest.mark.asyncio
    async def test_retrieves_by_id(self):
        item = await add_capture({"msg": "hello"})
        result = await get_capture(item["id"])
        assert result["msg"] == "hello"

    @pytest.mark.asyncio
    async def test_returns_none_for_missing(self):
        result = await get_capture("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_id(self):
        result = await get_capture("")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_deep_copy(self):
        item = await add_capture({"data": [1, 2, 3]})
        result = await get_capture(item["id"])
        result["data"].append(4)
        result2 = await get_capture(item["id"])
        assert result2["data"] == [1, 2, 3]


class TestConcurrentAccess:
    @pytest.mark.asyncio
    async def test_concurrent_adds(self):
        from app.debug_capture_store import _captures
        _captures.clear()

        async def add(n):
            await add_capture({"n": n})

        await asyncio.gather(*[add(i) for i in range(50)])
        results = await list_captures(limit=100)
        ids = {r["n"] for r in results}
        assert ids == set(range(50))


class TestDeleteCapture:
    @pytest.mark.asyncio
    async def test_deletes_existing_and_returns_true(self):
        from app.debug_capture_store import _captures
        _captures.clear()
        item = await add_capture({"n": 1})
        before = await list_captures(limit=100)
        assert len(before) == 1
        assert await delete_capture(item["id"]) is True
        after = await list_captures(limit=100)
        assert len(after) == 0
        assert all(row.get("id") != item["id"] for row in after)

    @pytest.mark.asyncio
    async def test_returns_false_for_missing(self):
        from app.debug_capture_store import _captures
        _captures.clear()
        await add_capture({"n": 1})
        assert await delete_capture("nonexistent-id") is False
        assert len(await list_captures(limit=100)) == 1

    @pytest.mark.asyncio
    async def test_returns_false_for_empty_id(self):
        from app.debug_capture_store import _captures
        _captures.clear()
        await add_capture({"n": 1})
        assert await delete_capture("") is False
        assert len(await list_captures(limit=100)) == 1

    @pytest.mark.asyncio
    async def test_deleted_capture_returns_none_from_get(self):
        from app.debug_capture_store import _captures
        _captures.clear()
        item = await add_capture({"n": 1})
        assert await delete_capture(item["id"]) is True
        assert await get_capture(item["id"]) is None


class TestClearCaptures:
    @pytest.mark.asyncio
    async def test_clear_returns_count(self):
        from app.debug_capture_store import _captures
        _captures.clear()
        for i in range(5):
            await add_capture({"n": i})
        assert await clear_captures() == 5

    @pytest.mark.asyncio
    async def test_clear_empties_list(self):
        from app.debug_capture_store import _captures
        _captures.clear()
        await add_capture({"n": 1})
        await add_capture({"n": 2})
        await clear_captures()
        assert await list_captures(limit=100) == []

    @pytest.mark.asyncio
    async def test_clear_on_empty_returns_zero(self):
        from app.debug_capture_store import _captures
        _captures.clear()
        assert await clear_captures() == 0

    @pytest.mark.asyncio
    async def test_concurrent_add_delete_does_not_raise(self):
        from app.debug_capture_store import _captures
        _captures.clear()
        ids = []

        async def add(n):
            item = await add_capture({"n": n})
            ids.append(item["id"])

        async def delete_existing():
            while ids:
                target = ids.pop()
                await delete_capture(target)

        async def delete_missing():
            await delete_capture("missing-id")

        # 两阶段：先填满再并发删除，避免调度竞态导致残留断言不稳定
        await asyncio.gather(*[add(i) for i in range(20)])
        await asyncio.gather(
            *[delete_existing() for _ in range(5)],
            *[delete_missing() for _ in range(10)],
        )
        assert await clear_captures() == 0
