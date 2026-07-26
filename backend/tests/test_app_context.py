"""Tests for AppContext singleton.

Covers:
  - get() returns the same instance across calls
  - reset() clears the singleton
  - Multi-coroutine singleton correctness
"""

import asyncio
import sys

import pytest

pytestmark = [pytest.mark.unit]


class TestAppContextSingleton:
    """AppContext should behave as a proper singleton."""

    def test_get_returns_same_instance(self):
        from app.app_context import AppContext

        AppContext.reset()
        a = AppContext.get()
        b = AppContext.get()
        assert a is b

    def test_reset_clears_singleton(self):
        from app.app_context import AppContext

        AppContext.reset()
        a = AppContext.get()
        AppContext.reset()
        b = AppContext.get()
        assert a is not b

    def test_reset_allows_new_instance(self):
        from app.app_context import AppContext

        AppContext.reset()
        first = AppContext.get()
        first.bot_manager = "test-bot"
        AppContext.reset()
        second = AppContext.get()
        assert second.bot_manager is None
        assert second is not first

    def test_default_attributes_are_none(self):
        from app.app_context import AppContext

        AppContext.reset()
        ctx = AppContext.get()
        assert ctx.bot_manager is None
        assert ctx.nonebot_driver is None
        assert ctx.astrbot_process_manager is None
        assert ctx.memory_cutoffs == {}
        assert ctx.bot_tasks == {}
        assert ctx.usage_tracker is None

    async def test_multi_coroutine_singleton(self):
        """Multiple concurrent coroutines should see the same instance."""
        from app.app_context import AppContext

        AppContext.reset()

        async def get_id() -> int:
            return id(AppContext.get())

        results = await asyncio.gather(*[get_id() for _ in range(20)])
        first = results[0]
        assert all(r == first for r in results)

    async def test_multi_coroutine_modification_visible(self):
        """Changes from one coroutine should be visible from another."""
        from app.app_context import AppContext

        AppContext.reset()

        async def set_bot(val: str) -> None:
            AppContext.get().bot_manager = val

        async def get_bot() -> object:
            return AppContext.get().bot_manager

        await asyncio.gather(set_bot("shared-bot"))
        result = await get_bot()
        assert result == "shared-bot"
