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


class TestLoadConfig:
    def test_loads_config_from_file(self, tmp_path, monkeypatch, test_config_dict):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(test_config_dict, indent=2), encoding="utf-8")

        import app.config_cache as cc
        monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
        cc.invalidate_cache()

        result = load_config()
        assert result["api_secret_key"] == test_config_dict["api_secret_key"]
        assert result["llm_provider"] == test_config_dict["llm_provider"]

    def test_missing_defaults_filled_in(self, tmp_path, monkeypatch):
        partial_config = {"api_secret_key": "my-key", "llm_provider": "google"}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(partial_config), encoding="utf-8")

        import app.config_cache as cc
        monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
        cc.invalidate_cache()

        result = load_config()
        assert result["api_secret_key"] == "my-key"
        assert result["system_prompt"] == DEFAULT_CONFIG["system_prompt"]

    def test_caches_result_on_same_mtime(self, tmp_path, monkeypatch, test_config_dict):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(test_config_dict, indent=2), encoding="utf-8")

        import app.config_cache as cc
        monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
        cc.invalidate_cache()

        result1 = load_config()
        result2 = load_config()
        assert result1 is result2

    def test_mtime_change_refreshes_cache(self, tmp_path, monkeypatch, test_config_dict):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(test_config_dict, indent=2), encoding="utf-8")

        import app.config_cache as cc
        monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
        cc.invalidate_cache()

        result1 = load_config()
        assert result1["api_secret_key"] == test_config_dict["api_secret_key"]

        time.sleep(0.01)
        modified = dict(test_config_dict, api_secret_key="new-secret-key")
        config_file.write_text(json.dumps(modified, indent=2), encoding="utf-8")

        result2 = load_config()
        assert result2["api_secret_key"] == "new-secret-key"

    def test_corrupted_json_falls_back_to_defaults(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.json"
        config_file.write_text("this is not valid json {{{", encoding="utf-8")

        import app.config_cache as cc
        monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
        cc.invalidate_cache()

        result = load_config()
        assert result["system_prompt"] == DEFAULT_CONFIG["system_prompt"]
        assert result["model_name"] == DEFAULT_CONFIG["model_name"]

    def test_nonexistent_file_auto_creates(self, tmp_path, monkeypatch):
        config_file = tmp_path / "nonexistent_config.json"

        import app.config_cache as cc
        monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
        cc.invalidate_cache()

        result = load_config()
        assert config_file.exists()
        assert result["system_prompt"] == DEFAULT_CONFIG["system_prompt"]


class TestSaveConfig:
    def test_save_and_reload(self, tmp_path, monkeypatch, test_config_dict):
        config_file = tmp_path / "config.json"

        import app.config_cache as cc
        monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
        cc.invalidate_cache()

        save_config(test_config_dict)
        assert config_file.exists()

        cc.invalidate_cache()
        loaded = load_config()
        assert loaded["api_secret_key"] == test_config_dict["api_secret_key"]

    def test_save_updates_cache(self, tmp_path, monkeypatch, test_config_dict):
        config_file = tmp_path / "config.json"

        import app.config_cache as cc
        monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
        cc.invalidate_cache()

        save_config(test_config_dict)
        result = load_config()
        assert result["api_secret_key"] == test_config_dict["api_secret_key"]


class TestInvalidateCache:
    def test_invalidate_causes_reread(self, tmp_path, monkeypatch, test_config_dict):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(test_config_dict, indent=2), encoding="utf-8")

        import app.config_cache as cc
        monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
        cc.invalidate_cache()

        result1 = load_config()

        modified = dict(test_config_dict, api_secret_key="changed-key")
        config_file.write_text(json.dumps(modified, indent=2), encoding="utf-8")

        invalidate_cache()
        result2 = load_config()
        assert result2["api_secret_key"] == "changed-key"
        assert result1 is not result2


class TestDefaultConfig:
    def test_default_config_has_required_keys(self):
        required_keys = [
            "api_secret_key",
            "system_prompt",
            "trigger_keywords",
            "stream_response",
            "context_mode",
            "user_personas",
            "role_based_config",
            "scoped_prompts",
            "plugins",
        ]
        for key in required_keys:
            assert key in DEFAULT_CONFIG

    def test_default_config_api_key_is_random(self):
        key1 = DEFAULT_CONFIG["api_secret_key"]
        assert len(key1) == 64
