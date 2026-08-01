"""Tests for app.usage_tracker — UsageTracker class."""
import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.usage_tracker import UsageTracker


@pytest.fixture
async def tracker(tmp_path):
    data_file = str(tmp_path / "data" / "usage_data.json")
    t = UsageTracker(data_file=data_file)
    await t.initialize()
    return t


@pytest.fixture
def mock_bot_config(monkeypatch):
    from app.app_context import AppContext
    from app.bot_manager import BotManager
    from app.bot_instance import BotInstance
    mgr = MagicMock(spec=BotManager)
    inst = MagicMock(spec=BotInstance)
    inst.config = {}
    mgr.get = MagicMock(return_value=inst)
    monkeypatch.setattr(AppContext.get(), "bot_manager", mgr)
    return mgr, inst


async def _wait_for_call(mock_fn, *, max_iters=100):
    """Spin the event loop until mock_fn has been awaited (scheduled task ran)."""
    for _ in range(max_iters):
        if mock_fn.await_count > 0:
            return
        await asyncio.sleep(0.01)


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


class TestReadBotQuotaConfig:
    """_read_bot_quota_config None 语义 (H1/M1/M2)."""

    @pytest.mark.asyncio
    async def test_no_bot_manager_returns_none(self, tmp_path, monkeypatch):
        from app.app_context import AppContext
        monkeypatch.setattr(AppContext.get(), "bot_manager", None)
        t = UsageTracker(data_file=str(tmp_path / "usage.json"))
        assert t._read_bot_quota_config("bot-a") is None

    @pytest.mark.asyncio
    async def test_bot_not_found_returns_none(self, tmp_path, mock_bot_config):
        mgr, inst = mock_bot_config
        mgr.get = MagicMock(return_value=None)
        t = UsageTracker(data_file=str(tmp_path / "usage.json"))
        assert t._read_bot_quota_config("bot-a") is None

    @pytest.mark.asyncio
    async def test_missing_quota_alert_returns_none(self, tmp_path, mock_bot_config):
        """H1 回归: 未配置 quota_alert 不再回退默认配额 (旧实现误报)."""
        mgr, inst = mock_bot_config
        inst.config = {}
        t = UsageTracker(data_file=str(tmp_path / "usage.json"))
        assert t._read_bot_quota_config("bot-a") is None

    @pytest.mark.asyncio
    async def test_disabled_quota_alert_returns_none(self, tmp_path, mock_bot_config):
        """H1: enabled=False → None → 不触发告警."""
        mgr, inst = mock_bot_config
        inst.config = {"quota_alert": {"enabled": False}}
        t = UsageTracker(data_file=str(tmp_path / "usage.json"))
        assert t._read_bot_quota_config("bot-a") is None

    @pytest.mark.asyncio
    async def test_enabled_returns_full_config(self, tmp_path, mock_bot_config):
        mgr, inst = mock_bot_config
        inst.config = {"quota_alert": {
            "enabled": True,
            "token_limit": 5000,
            "request_limit": 200,
            "webhook_url": "https://hooks.example.com/hook",
            "warning_threshold": 0.5,
            "critical_threshold": 0.9,
        }}
        t = UsageTracker(data_file=str(tmp_path / "usage.json"))
        result = t._read_bot_quota_config("bot-a")
        assert result is not None
        assert result["token_limit"] == 5000
        assert result["request_limit"] == 200
        assert result["webhook_url"] == "https://hooks.example.com/hook"
        assert result["warning_threshold"] == 0.5
        assert result["critical_threshold"] == 0.9
        assert "enabled" not in result

    @pytest.mark.asyncio
    async def test_empty_webhook_url_omitted(self, tmp_path, mock_bot_config):
        """M2: webhook_url 空串 → 键省略 → check_and_alert 回退全局."""
        mgr, inst = mock_bot_config
        inst.config = {"quota_alert": {"enabled": True, "webhook_url": ""}}
        t = UsageTracker(data_file=str(tmp_path / "usage.json"))
        result = t._read_bot_quota_config("bot-a")
        assert result is not None
        assert "webhook_url" not in result

    @pytest.mark.asyncio
    async def test_invalid_config_returns_none(self, tmp_path, mock_bot_config):
        """M1: 配置无效 (ValidationError) → None → 告警跳过."""
        mgr, inst = mock_bot_config
        inst.config = {"quota_alert": {"enabled": True, "token_limit": -5}}
        t = UsageTracker(data_file=str(tmp_path / "usage.json"))
        assert t._read_bot_quota_config("bot-a") is None


class TestRecordUsageAlertTrigger:
    """record_usage 锁外异步触发配额告警 (P1-1/P1-5)."""

    @pytest.mark.asyncio
    async def test_record_usage_triggers_alert(self, tmp_path, mock_bot_config):
        mgr, inst = mock_bot_config
        inst.config = {"quota_alert": {
            "enabled": True,
            "token_limit": 1000,
            "request_limit": 100,
            "webhook_url": "https://hooks.example.com/hook",
            "warning_threshold": 0.5,
            "critical_threshold": 0.9,
        }}
        mock_manager = MagicMock()
        mock_manager.check_and_alert = AsyncMock(return_value=None)
        t = UsageTracker(
            data_file=str(tmp_path / "usage.json"),
            quota_alert_manager=mock_manager,
        )
        await t.initialize()
        await t.record_usage("openai", "gpt-4o", 600, 0, bot_id="test-bot")
        await _wait_for_call(mock_manager.check_and_alert)
        mock_manager.check_and_alert.assert_awaited_once()
        kwargs = mock_manager.check_and_alert.call_args.kwargs
        assert kwargs["bot_id"] == "test-bot"
        assert kwargs["daily_quota"]["token_limit"] == 1000
        assert kwargs["daily_quota"]["webhook_url"] == "https://hooks.example.com/hook"
        assert "enabled" not in kwargs["daily_quota"]
        assert kwargs["daily_usage"]["requests"] == 1

    @pytest.mark.asyncio
    async def test_record_usage_skips_when_quota_disabled(self, tmp_path, mock_bot_config):
        """H1: quota_alert 未启用 → 不调度告警任务."""
        mgr, inst = mock_bot_config
        inst.config = {"quota_alert": {"enabled": False}}
        mock_manager = MagicMock()
        mock_manager.check_and_alert = AsyncMock(return_value=None)
        t = UsageTracker(
            data_file=str(tmp_path / "usage.json"),
            quota_alert_manager=mock_manager,
        )
        await t.initialize()
        await t.record_usage("openai", "gpt-4o", 600, 0, bot_id="test-bot")
        await asyncio.sleep(0.05)
        mock_manager.check_and_alert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_record_usage_skips_without_bot_id(self, tmp_path, mock_bot_config):
        """无 bot_id → 无快照 → 不调度告警任务."""
        mgr, inst = mock_bot_config
        inst.config = {"quota_alert": {"enabled": True, "token_limit": 1000}}
        mock_manager = MagicMock()
        mock_manager.check_and_alert = AsyncMock(return_value=None)
        t = UsageTracker(
            data_file=str(tmp_path / "usage.json"),
            quota_alert_manager=mock_manager,
        )
        await t.initialize()
        await t.record_usage("openai", "gpt-4o", 600, 0)
        await asyncio.sleep(0.05)
        mock_manager.check_and_alert.assert_not_awaited()
