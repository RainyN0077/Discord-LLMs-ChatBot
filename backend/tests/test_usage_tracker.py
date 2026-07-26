"""Tests for app.usage_tracker — UsageTracker class."""
import json
import pytest
from unittest.mock import patch, MagicMock

from app.usage_tracker import UsageTracker


@pytest.fixture
async def tracker(tmp_path):
    data_file = str(tmp_path / "data" / "usage_data.json")
    t = UsageTracker(data_file=data_file)
    await t.initialize()
    return t


class TestUsageTrackerInit:
    @pytest.mark.asyncio
    async def test_creates_data_dir(self, tmp_path):
        data_file = str(tmp_path / "sub" / "usage.json")
        t = UsageTracker(data_file=data_file)
        await t.initialize()
        import os
        assert os.path.isdir(os.path.dirname(data_file))

    @pytest.mark.asyncio
    async def test_initial_structure(self, tracker):
        assert "daily" in tracker.usage_data
        assert "metadata" in tracker.usage_data
        assert "users" in tracker.usage_data["metadata"]
        assert "channel_users" in tracker.usage_data["metadata"]

    @pytest.mark.asyncio
    async def test_loads_existing_data(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        data_file = data_dir / "usage.json"
        existing = {"daily": {}, "metadata": {"users": {"123": {"name": "Alice"}}}}
        data_file.write_text(json.dumps(existing), encoding="utf-8")
        t = UsageTracker(data_file=str(data_file))
        await t.initialize()
        assert t.usage_data["metadata"]["users"]["123"]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_corrupted_file_backup(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        data_file = data_dir / "usage.json"
        data_file.write_text("not json {{{", encoding="utf-8")
        t = UsageTracker(data_file=str(data_file))
        await t.initialize()
        assert t.usage_data["metadata"]["users"] == {}
        backup = str(data_file) + ".corrupt"
        import os
        assert os.path.exists(backup)

    @pytest.mark.asyncio
    async def test_metadata_defaults_handled(self, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        data_file = data_dir / "usage.json"
        data_file.write_text(json.dumps({"daily": {}, "metadata": {}}), encoding="utf-8")
        t = UsageTracker(data_file=str(data_file))
        await t.initialize()
        assert "channel_users" in t.usage_data["metadata"]


class TestRecordUsage:
    @pytest.mark.asyncio
    async def test_records_basic_usage(self, tracker):
        await tracker.record_usage("openai", "gpt-4o", 100, 50)
        today = tracker.usage_data["daily"]
        keys = list(today.keys())
        assert len(keys) == 1
        day = today[keys[0]]
        assert day["requests"] == 1
        assert day["input_tokens"] == 100
        assert day["output_tokens"] == 50
        assert day["total_tokens"] == 150

    @pytest.mark.asyncio
    async def test_records_user_info(self, tracker):
        await tracker.record_usage(
            "openai", "gpt-4o", 100, 50,
            user_id="user1", user_name="Alice", user_display_name="AliceD",
        )
        meta = tracker.usage_data["metadata"]
        assert meta["users"]["user1"]["name"] == "Alice"
        assert meta["users"]["user1"]["display_name"] == "AliceD"

    @pytest.mark.asyncio
    async def test_records_channel_users(self, tracker):
        await tracker.record_usage(
            "openai", "gpt-4o", 100, 50,
            channel_id="ch1", user_id="user1",
        )
        channel_users = tracker.usage_data["metadata"]["channel_users"]
        assert "ch1" in channel_users
        assert "user1" in channel_users["ch1"]["user_ids"]

    @pytest.mark.asyncio
    async def test_records_role_and_guild(self, tracker):
        await tracker.record_usage(
            "openai", "gpt-4o", 100, 50,
            role_id="role1", role_name="Admin",
            guild_id="guild1", guild_name="Test Guild",
        )
        meta = tracker.usage_data["metadata"]
        assert meta["roles"]["role1"]["name"] == "Admin"
        assert meta["guilds"]["guild1"]["name"] == "Test Guild"

    @pytest.mark.asyncio
    async def test_user_model_detail(self, tracker):
        await tracker.record_usage("openai", "gpt-4o", 100, 50, user_id="u1")
        today = list(tracker.usage_data["daily"].keys())[0]
        day = tracker.usage_data["daily"][today]
        by_user = day["detailed"]["by_user"]
        assert "u1" in by_user
        assert by_user["u1"]["total"]["requests"] == 1
        assert "openai:gpt-4o" in by_user["u1"]["models"]

    @pytest.mark.asyncio
    async def test_role_model_detail(self, tracker):
        await tracker.record_usage("openai", "gpt-4o", 100, 50, role_id="r1")
        today = list(tracker.usage_data["daily"].keys())[0]
        by_role = tracker.usage_data["daily"][today]["detailed"]["by_role"]
        assert by_role["r1"]["total"]["requests"] == 1

    @pytest.mark.asyncio
    async def test_channel_model_detail(self, tracker):
        await tracker.record_usage("openai", "gpt-4o", 100, 50, channel_id="ch1")
        today = list(tracker.usage_data["daily"].keys())[0]
        by_ch = tracker.usage_data["daily"][today]["detailed"]["by_channel"]
        assert by_ch["ch1"]["total"]["requests"] == 1

    @pytest.mark.asyncio
    async def test_guild_model_detail(self, tracker):
        await tracker.record_usage("openai", "gpt-4o", 100, 50, guild_id="g1")
        today = list(tracker.usage_data["daily"].keys())[0]
        by_guild = tracker.usage_data["daily"][today]["detailed"]["by_guild"]
        assert by_guild["g1"]["total"]["requests"] == 1

    @pytest.mark.asyncio
    async def test_multiple_records_accumulate(self, tracker):
        await tracker.record_usage("openai", "gpt-4o", 100, 50, user_id="u1")
        await tracker.record_usage("openai", "gpt-4o", 200, 100, user_id="u1")
        today = list(tracker.usage_data["daily"].keys())[0]
        day = tracker.usage_data["daily"][today]
        assert day["requests"] == 2
        assert day["input_tokens"] == 300
        u1 = day["detailed"]["by_user"]["u1"]
        assert u1["total"]["requests"] == 2


class TestGetStatistics:
    @pytest.mark.asyncio
    async def test_today_period(self, tracker):
        await tracker.record_usage("openai", "gpt-4o", 100, 50, user_id="u1")
        stats = await tracker.get_statistics(period="today", view="user")
        assert stats["period"] == "today"
        assert stats["stats"]["requests"] >= 1

    @pytest.mark.asyncio
    async def test_week_period_empty(self, tracker):
        stats = await tracker.get_statistics(period="week", view="user")
        assert stats["period"] == "week"
        assert stats["stats"]["requests"] == 0

    @pytest.mark.asyncio
    async def test_month_period(self, tracker):
        stats = await tracker.get_statistics(period="month", view="user")
        assert stats["period"] == "month"

    @pytest.mark.asyncio
    async def test_all_time(self, tracker):
        stats = await tracker.get_statistics(period="all", view="user")
        assert stats["period"] == "all"

    @pytest.mark.asyncio
    async def test_different_views(self, tracker):
        await tracker.record_usage("openai", "gpt-4o", 100, 50, user_id="u1", channel_id="ch1")
        user_view = await tracker.get_statistics(period="today", view="user")
        channel_view = await tracker.get_statistics(period="today", view="channel")
        assert "detailed_by_user" in user_view["stats"]
        assert "detailed_by_channel" in channel_view["stats"]

    @pytest.mark.asyncio
    async def test_unknown_timezone_falls_back_to_utc(self, tracker):
        stats = await tracker.get_statistics(period="today", view="user", timezone_str="Not/A_Zone")
        assert stats is not None

    @pytest.mark.asyncio
    async def test_returns_metadata(self, tracker):
        stats = await tracker.get_statistics(period="today", view="user")
        assert "metadata" in stats


class TestSaveData:
    @pytest.mark.asyncio
    async def test_save_writes_json(self, tracker):
        await tracker.record_usage("openai", "gpt-4o", 100, 50)
        await tracker.save_data()
        import os
        assert os.path.exists(tracker.data_file)
        with open(tracker.data_file, encoding="utf-8") as f:
            data = json.load(f)
        assert "daily" in data
        assert "metadata" in data
