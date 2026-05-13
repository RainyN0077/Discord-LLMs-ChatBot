import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot_manager import BotManager
from app.bot_instance import BotInstance
from app.config_cache import DEFAULT_CONFIG, get_bot_dir, get_bot_config_path


def _setup_bot_paths(monkeypatch, tmp_path):
    import app.config_cache as cc
    import app.bot_instance as bi
    import app.bot_manager as bm

    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    bots_dir = data_dir / "bots"
    bots_dir.mkdir(exist_ok=True)
    config_file = data_dir / "config.json"

    monkeypatch.setattr(cc, "DATA_DIR", data_dir)
    monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
    monkeypatch.setattr(cc, "BOTS_DIR", bots_dir)
    monkeypatch.setattr(bi, "BOTS_DIR", bots_dir)
    monkeypatch.setattr(bm, "BOTS_DIR", bots_dir)
    monkeypatch.setattr(bm, "CONFIG_FILE", config_file)
    cc.invalidate_cache()


class TestBotManager:
    def test_init_empty(self):
        mgr = BotManager()
        assert mgr._instances == {}
        assert mgr._lock is not None

    def test_get_nonexistent(self):
        mgr = BotManager()
        assert mgr.get("nonexistent") is None

    def test_list_empty(self):
        mgr = BotManager()
        assert mgr.list() == []

    @pytest.mark.asyncio
    async def test_create_bot(self, tmp_path, monkeypatch):
        _setup_bot_paths(monkeypatch, tmp_path)
        mgr = BotManager()
        bot_id = await mgr.create({"bot_id": "test-bot-1", "bot_name": "Test", "platform": "qq"})
        assert bot_id == "test-bot-1"
        assert "test-bot-1" in mgr._instances
        assert mgr._instances["test-bot-1"].config["bot_name"] == "Test"
        assert get_bot_config_path("test-bot-1").exists()

    @pytest.mark.asyncio
    async def test_create_duplicate(self, tmp_path, monkeypatch):
        _setup_bot_paths(monkeypatch, tmp_path)
        mgr = BotManager()
        await mgr.create({"bot_id": "dup-bot", "bot_name": "Test"})
        with pytest.raises(ValueError, match="already exists"):
            await mgr.create({"bot_id": "dup-bot", "bot_name": "Test 2"})

    @pytest.mark.asyncio
    async def test_create_missing_bot_id(self):
        mgr = BotManager()
        with pytest.raises(ValueError, match="bot_id is required"):
            await mgr.create({"bot_name": "No ID"})

    @pytest.mark.asyncio
    async def test_delete_bot(self, tmp_path, monkeypatch):
        _setup_bot_paths(monkeypatch, tmp_path)
        mgr = BotManager()
        bot_id = await mgr.create({"bot_id": "del-bot", "platform": "qq"})
        bot_dir = get_bot_dir(bot_id)
        assert bot_dir.exists()

        await mgr.delete(bot_id)
        assert "del-bot" not in mgr._instances
        assert not bot_dir.exists()

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, tmp_path, monkeypatch):
        _setup_bot_paths(monkeypatch, tmp_path)
        mgr = BotManager()
        # Should not raise and should not modify instances
        await mgr.delete("nonexistent")
        assert mgr._instances == {}
        assert "nonexistent" not in mgr._instances

    @pytest.mark.asyncio
    async def test_start_bot_success(self):
        mock_instance = MagicMock(spec=BotInstance)
        mock_instance.start = AsyncMock()

        mgr = BotManager()
        mgr._instances["start-bot"] = mock_instance
        await mgr.start("start-bot")
        mock_instance.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_bot_not_found(self):
        mgr = BotManager()
        with pytest.raises(ValueError, match="not found"):
            await mgr.start("nonexistent")

    @pytest.mark.asyncio
    async def test_stop_bot_success(self):
        mock_instance = MagicMock(spec=BotInstance)
        mock_instance.stop = AsyncMock()

        mgr = BotManager()
        mgr._instances["stop-bot"] = mock_instance
        await mgr.stop("stop-bot")
        mock_instance.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_bot_not_found(self):
        mgr = BotManager()
        with pytest.raises(ValueError, match="not found"):
            await mgr.stop("nonexistent")

    @pytest.mark.asyncio
    async def test_restart_bot_success(self):
        mock_instance = MagicMock(spec=BotInstance)
        mock_instance.restart = AsyncMock()

        mgr = BotManager()
        mgr._instances["restart-bot"] = mock_instance
        await mgr.restart("restart-bot")
        mock_instance.restart.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_load_all(self, tmp_path, monkeypatch):
        _setup_bot_paths(monkeypatch, tmp_path)
        mgr = BotManager()
        await mgr.create({"bot_id": "loaded-bot-1", "platform": "qq", "enabled": False})
        await mgr.create({"bot_id": "loaded-bot-2", "platform": "qq", "enabled": False})
        mgr._instances.clear()

        await mgr.load_all()
        assert "loaded-bot-1" in mgr._instances
        assert "loaded-bot-2" in mgr._instances

    def test_migrate_legacy_config(self, tmp_path, monkeypatch):
        import app.config_cache as cc
        import app.bot_manager as bm
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        bots_dir = data_dir / "bots"
        bots_dir.mkdir(exist_ok=True)
        config_file = data_dir / "config.json"
        config_file.write_text(json.dumps({
            "bot_id": "legacy-bot",
            "bot_name": "Legacy",
            "discord_token": "test-token-value-for-legacy-bot-min-50-chars",
        }), encoding="utf-8")

        monkeypatch.setattr(cc, "DATA_DIR", data_dir)
        monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
        monkeypatch.setattr(cc, "BOTS_DIR", bots_dir)
        monkeypatch.setattr(bm, "CONFIG_FILE", config_file)
        monkeypatch.setattr(bm, "BOTS_DIR", bots_dir)
        import app.bot_instance as bi
        monkeypatch.setattr(bi, "BOTS_DIR", bots_dir)
        cc.invalidate_cache()

        mgr = BotManager()
        migrated_id = mgr._migrate_legacy_config()
        assert migrated_id == "legacy-bot"
        assert not config_file.exists()
        assert (config_file.parent / "config.json.backup").exists()
        bot_config = get_bot_config_path("legacy-bot")
        assert bot_config.exists()
        with open(bot_config, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["bot_id"] == "legacy-bot"

    def test_migrate_skips_if_bots_exist(self, tmp_path, monkeypatch):
        import app.config_cache as cc
        import app.bot_manager as bm
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        bots_dir = data_dir / "bots"
        bots_dir.mkdir(exist_ok=True)
        (bots_dir / "existing-bot").mkdir(exist_ok=True)
        config_file = data_dir / "config.json"
        config_file.write_text(json.dumps({"bot_id": "should-skip"}), encoding="utf-8")

        monkeypatch.setattr(cc, "DATA_DIR", data_dir)
        monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
        monkeypatch.setattr(cc, "BOTS_DIR", bots_dir)
        monkeypatch.setattr(bm, "CONFIG_FILE", config_file)
        monkeypatch.setattr(bm, "BOTS_DIR", bots_dir)
        cc.invalidate_cache()

        mgr = BotManager()
        result = mgr._migrate_legacy_config()
        assert result is None
        assert config_file.exists()

    def test_migrate_no_config_file(self, tmp_path, monkeypatch):
        import app.config_cache as cc
        import app.bot_manager as bm
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        bots_dir = data_dir / "bots"
        bots_dir.mkdir(exist_ok=True)
        config_file = data_dir / "config.json"

        monkeypatch.setattr(cc, "DATA_DIR", data_dir)
        monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
        monkeypatch.setattr(cc, "BOTS_DIR", bots_dir)
        monkeypatch.setattr(bm, "CONFIG_FILE", config_file)
        monkeypatch.setattr(bm, "BOTS_DIR", bots_dir)
        cc.invalidate_cache()

        mgr = BotManager()
        result = mgr._migrate_legacy_config()
        assert result is None

    @pytest.mark.asyncio
    async def test_shutdown(self):
        mock1 = MagicMock(spec=BotInstance)
        mock1.stop = AsyncMock()
        mock1.bot_id = "bot1"
        mock2 = MagicMock(spec=BotInstance)
        mock2.stop = AsyncMock()
        mock2.bot_id = "bot2"

        mgr = BotManager()
        mgr._instances["bot1"] = mock1
        mgr._instances["bot2"] = mock2

        await mgr.shutdown()
        mock1.stop.assert_awaited_once()
        mock2.stop.assert_awaited_once()
        assert mgr._instances == {}
