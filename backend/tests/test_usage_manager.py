"""Tests for app.core_logic.usage_manager — UsageManager class."""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.core_logic.usage_manager import UsageManager
from app.utils import TokenCalculator


@pytest.fixture
def token_calc():
    return TokenCalculator()


@pytest.fixture
def manager(token_calc):
    return UsageManager(token_calc)


@pytest.fixture
def role_config():
    return {
        "id": "test_role",
        "title": "Test",
        "enable_message_limit": True,
        "message_limit": 10,
        "message_refresh_minutes": 60,
        "enable_char_limit": True,
        "token_limit": 10000,
        "char_limit": 10000,
        "char_refresh_minutes": 60,
        "token_output_budget": 500,
    }


class TestUsageManagerInit:
    def test_initialization(self, token_calc):
        um = UsageManager(token_calc)
        assert um._usage_tracker == {}
        assert um._user_locks == {}


class TestCheckQuotaAndGetUsage:
    @pytest.mark.asyncio
    async def test_second_call_returns_existing(self, manager, role_config):
        await manager.check_quota_and_get_usage(123, role_config)
        usage = await manager.check_quota_and_get_usage(123, role_config)
        assert usage["message_count"] == 0

    @pytest.mark.asyncio
    async def test_resets_when_expired(self, manager, role_config):
        usage = await manager.check_quota_and_get_usage(123, role_config)
        old_time = datetime.now(timezone.utc) - timedelta(minutes=120)
        async with manager._get_lock(123):
            manager._usage_tracker[123]["timestamp"] = old_time
        usage_after = await manager.check_quota_and_get_usage(123, role_config)
        assert usage_after["timestamp"] > old_time


class TestCheckPreRequestQuota:
    @pytest.mark.asyncio
    async def test_within_limits_returns_none(self, manager, role_config):
        usage = await manager.check_quota_and_get_usage(123, role_config)
        result = await manager.check_pre_request_quota(123, role_config, usage, 500)
        assert result is None

    @pytest.mark.asyncio
    async def test_exceeds_message_limit(self, manager, role_config):
        role_config_small = {**role_config, "message_limit": 3}
        usage = {"message_count": 3, "total_tokens": 0, "timestamp": datetime.now(timezone.utc)}
        result = await manager.check_pre_request_quota(123, role_config_small, usage, 100)
        assert result is not None
        assert "message" in result.lower()

    @pytest.mark.asyncio
    async def test_exceeds_token_limit(self, manager, role_config):
        role_config_small = {**role_config, "token_limit": 1000}
        usage = {"message_count": 0, "total_tokens": 800, "timestamp": datetime.now(timezone.utc)}
        result = await manager.check_pre_request_quota(123, role_config_small, usage, 300)
        assert result is not None
        assert "token" in result.lower() or "quota" in result.lower()

    @pytest.mark.asyncio
    async def test_disabled_limits_pass(self, manager):
        role_no_limits = {
            "enable_message_limit": False,
            "enable_char_limit": False,
        }
        usage = {"message_count": 9999, "total_tokens": 999999, "timestamp": datetime.now(timezone.utc)}
        result = await manager.check_pre_request_quota(123, role_no_limits, usage, 10000)
        assert result is None


class TestUpdatePostRequestUsage:
    @pytest.mark.asyncio
    async def test_updates_counts(self, manager, role_config):
        await manager.check_quota_and_get_usage(123, role_config)
        await manager.update_post_request_usage(123, 200, 100)
        async with manager._get_lock(123):
            usage = manager._usage_tracker[123]
        assert usage["message_count"] == 1
        assert usage["total_tokens"] == 300

    @pytest.mark.asyncio
    async def test_creates_if_missing(self, manager, role_config):
        await manager.update_post_request_usage(999, 50, 25)
        async with manager._get_lock(999):
            usage = manager._usage_tracker[999]
        assert usage["message_count"] == 1
        assert usage["total_tokens"] == 75

    @pytest.mark.asyncio
    async def test_concurrent_access(self, manager, role_config):
        import asyncio
        await manager.check_quota_and_get_usage(123, role_config)
        async def update(tokens):
            await manager.update_post_request_usage(123, tokens, tokens // 2)
        await asyncio.gather(*[update(i) for i in range(10, 60, 10)])
        async with manager._get_lock(123):
            usage = manager._usage_tracker[123]
        assert usage["message_count"] == 5
        assert usage["total_tokens"] == sum(i + i // 2 for i in range(10, 60, 10))
