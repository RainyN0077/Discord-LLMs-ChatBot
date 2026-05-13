import pytest
pytestmark = [pytest.mark.unit]
import json
import os
import time

import pytest
from app.config_cache import (
    load_config,
    save_config,
    invalidate_cache,
    DEFAULT_CONFIG,
    _set_defaults_recursive,
)


class TestSetDefaultsRecursive:
    def test_adds_missing_keys(self):
        config = {}
        default = {"a": 1, "b": 2}
        _set_defaults_recursive(default, config)
        assert config == {"a": 1, "b": 2}

    def test_preserves_existing_values(self):
        config = {"a": 100}
        default = {"a": 1, "b": 2}
        _set_defaults_recursive(default, config)
        assert config["a"] == 100
        assert config["b"] == 2

    def test_nested_dict_recursive(self):
        config = {"outer": {"inner1": "keep_me"}}
        default = {"outer": {"inner1": "default1", "inner2": "default2"}}
        _set_defaults_recursive(default, config)
        assert config["outer"]["inner1"] == "keep_me"
        assert config["outer"]["inner2"] == "default2"

    def test_nested_default_copies_all(self):
        config = {}
        default = {"a": {"b": {"c": 1}}, "d": 2}
        _set_defaults_recursive(default, config)
        assert config["a"]["b"]["c"] == 1
        assert config["d"] == 2

    def test_nested_no_overwrite(self):
        config = {"level1": {"level2": {"key": "original"}}}
        default = {"level1": {"level2": {"key": "default", "extra": 42}}}
        _set_defaults_recursive(default, config)
        assert config["level1"]["level2"]["key"] == "original"
        assert config["level1"]["level2"]["extra"] == 42

    def test_mutates_in_place(self):
        config = {}
        original_id = id(config)
        _set_defaults_recursive({"a": 1}, config)
        assert id(config) == original_id


class TestDefaultConfig:
    def test_has_essential_keys(self):
        assert "api_secret_key" in DEFAULT_CONFIG
        assert "discord_token" in DEFAULT_CONFIG
        assert "llm_provider" in DEFAULT_CONFIG
        assert "model_name" in DEFAULT_CONFIG
        assert "system_prompt" in DEFAULT_CONFIG
        assert "trigger_keywords" in DEFAULT_CONFIG
        assert "context_mode" in DEFAULT_CONFIG

    def test_trigger_keywords_is_list(self):
        assert isinstance(DEFAULT_CONFIG["trigger_keywords"], list)

    def test_role_based_config_exists(self):
        assert "role_based_config" in DEFAULT_CONFIG
        assert isinstance(DEFAULT_CONFIG["role_based_config"], dict)

    def test_scoped_prompts_exists(self):
        assert "scoped_prompts" in DEFAULT_CONFIG
        assert "guilds" in DEFAULT_CONFIG["scoped_prompts"]
        assert "channels" in DEFAULT_CONFIG["scoped_prompts"]

    def test_scoped_prompts_exists(self):
        assert "scoped_prompts" in DEFAULT_CONFIG
        assert "guilds" in DEFAULT_CONFIG["scoped_prompts"]
        assert "channels" in DEFAULT_CONFIG["scoped_prompts"]

    def test_channel_context_settings(self):
        assert "channel_context_settings" in DEFAULT_CONFIG


class TestLoadSaveConfig:
    def test_load_creates_default(self, tmp_path):
        import app.config_cache as cc
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        config_file = data_dir / "config.json"

        original = (cc.DATA_DIR, cc.CONFIG_FILE)
        try:
            cc.DATA_DIR = data_dir
            cc.CONFIG_FILE = config_file
            cc.invalidate_cache()

            config = cc.load_config()
            assert "api_secret_key" in config
        finally:
            cc.DATA_DIR, cc.CONFIG_FILE = original
            cc.invalidate_cache()

    def test_save_and_load_roundtrip(self, tmp_path):
        import app.config_cache as cc
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        config_file = data_dir / "config.json"

        original = (cc.DATA_DIR, cc.CONFIG_FILE)
        try:
            cc.DATA_DIR = data_dir
            cc.CONFIG_FILE = config_file
            cc.invalidate_cache()

            config = cc.load_config()
            config["test_field"] = "hello"
            cc.save_config(config)
            cc.invalidate_cache()
            loaded = cc.load_config()
            assert loaded["test_field"] == "hello"
        finally:
            cc.DATA_DIR, cc.CONFIG_FILE = original
            cc.invalidate_cache()

    def test_invalidate_cache_forces_reload(self, tmp_path):
        import app.config_cache as cc
        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        config_file = data_dir / "config.json"

        original = (cc.DATA_DIR, cc.CONFIG_FILE)
        try:
            cc.DATA_DIR = data_dir
            cc.CONFIG_FILE = config_file
            cc.invalidate_cache()

            config1 = cc.load_config()
            config1["field"] = "value1"
            cc.save_config(config1)

            config2 = cc.load_config()
            assert config2["field"] == "value1"

            config1["field"] = "value2"
            cc.save_config(config1)
            cc.invalidate_cache()
            config3 = cc.load_config()
            assert config3["field"] == "value2"
        finally:
            cc.DATA_DIR, cc.CONFIG_FILE = original
            cc.invalidate_cache()
