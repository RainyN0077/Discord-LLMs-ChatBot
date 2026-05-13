import json
from unittest.mock import MagicMock, AsyncMock

import pytest

from app.bot_instance import BotInstance
from app.config_cache import DEFAULT_CONFIG


def _setup_bot_paths(monkeypatch, tmp_path):
    import app.config_cache as cc
    import app.bot_instance as bi

    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    bots_dir = data_dir / "bots"
    bots_dir.mkdir(exist_ok=True)
    config_file = data_dir / "config.json"

    monkeypatch.setattr(cc, "DATA_DIR", data_dir)
    monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
    monkeypatch.setattr(cc, "BOTS_DIR", bots_dir)
    monkeypatch.setattr(bi, "BOTS_DIR", bots_dir)
    cc.invalidate_cache()


class TestBotInstance:
    def test_init(self, tmp_path, monkeypatch):
        _setup_bot_paths(monkeypatch, tmp_path)
        instance = BotInstance("test-bot-id")
        assert instance.bot_id == "test-bot-id"
        assert instance.platform == "discord"
        assert instance.status == "stopped"
        assert instance._task is None

    def test_load_config_creates_default(self, tmp_path, monkeypatch):
        _setup_bot_paths(monkeypatch, tmp_path)
        instance = BotInstance("new-bot")
        config = instance.load_config()
        assert config["bot_id"] == "new-bot"
        assert config["bot_name"] == DEFAULT_CONFIG["bot_name"]
        assert instance.config_path.exists()

    def test_load_config_from_file(self, tmp_path, monkeypatch):
        _setup_bot_paths(monkeypatch, tmp_path)
        instance = BotInstance("file-bot")
        instance.config_dir.mkdir(parents=True, exist_ok=True)
        instance.config_path.write_text(json.dumps({
            "bot_id": "file-bot",
            "bot_name": "Custom Name",
            "platform": "discord",
        }), encoding="utf-8")

        config = instance.load_config()
        assert config["bot_id"] == "file-bot"
        assert config["bot_name"] == "Custom Name"

    def test_save_config(self, tmp_path, monkeypatch):
        _setup_bot_paths(monkeypatch, tmp_path)
        instance = BotInstance("save-bot")
        test_config = {"bot_id": "save-bot", "bot_name": "Saved", "platform": "discord"}
        instance.save_config(test_config)
        assert instance.config == test_config
        assert instance.config_path.exists()
        with open(instance.config_path, "r") as f:
            saved = json.load(f)
        assert saved["bot_name"] == "Saved"

    def test_is_running_not_started(self):
        instance = BotInstance("idle-bot")
        assert instance.is_running() is False

    def test_to_status_dict(self, tmp_path, monkeypatch):
        _setup_bot_paths(monkeypatch, tmp_path)
        instance = BotInstance("status-bot")
        instance.load_config()
        status = instance.to_status_dict()
        assert status["bot_id"] == "status-bot"
        assert status["status"] == "stopped"
        assert status["uptime_seconds"] is None

    def test_config_properties(self, tmp_path, monkeypatch):
        _setup_bot_paths(monkeypatch, tmp_path)
        instance = BotInstance("prop-bot")
        bots_dir = tmp_path / "data" / "bots"
        assert instance.config_dir == bots_dir / "prop-bot"
        assert instance.config_path == bots_dir / "prop-bot" / "config.json"
        assert instance.knowledge_path == bots_dir / "prop-bot" / "knowledge.sqlite"
        assert instance.usage_path == bots_dir / "prop-bot" / "usage_data.json"
