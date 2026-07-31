"""SecretsManager v2 嵌套加密测试 (MEDIUM-5 宽容策略).

覆盖 v2 §4 表格: 幂等、正常模式嵌套明文宽容、迁移模式透传、round-trip、
错误 key 行为、输入不可变性、跳过规则等。
"""
import copy
import logging

import pytest

from app.security.secrets_manager import SecretsManager


def _sample_data() -> dict:
    return {
        "api_key": "sk-top-secret",
        "quota_alert": {
            "webhook_url": "https://hooks.example.com/abc",
            "enabled": True,
        },
        "other": "plain-value",
    }


def _assert_encrypted(value: str) -> None:
    assert isinstance(value, str)
    assert value.startswith("gAAAAA")


class TestEncryptDictNested:
    def test_encrypt_dict_idempotent_top_and_nested(self):
        sm = SecretsManager("test-key-123")
        data = _sample_data()
        once = sm.encrypt_dict(data)
        twice = sm.encrypt_dict(once)
        assert twice == once  # 幂等: 二次加密不再变化
        _assert_encrypted(once["api_key"])
        _assert_encrypted(once["quota_alert"]["webhook_url"])
        assert once["other"] == "plain-value"  # 非敏感字段不动

    def test_encrypt_dict_does_not_mutate_input(self):
        sm = SecretsManager("test-key-123")
        data = _sample_data()
        snapshot = copy.deepcopy(data)
        sm.encrypt_dict(data)
        assert data == snapshot  # 纯函数语义

    def test_encrypt_dict_migration_mode_raises(self, monkeypatch):
        monkeypatch.setenv("DISABLE_ENCRYPTION", "1")
        sm = SecretsManager("test-key-123")
        with pytest.raises(RuntimeError, match="DISABLE_ENCRYPTION"):
            sm.encrypt_dict(_sample_data())


class TestDecryptDictNested:
    def test_nested_round_trip(self):
        sm = SecretsManager("test-key-123")
        data = _sample_data()
        encrypted = sm.encrypt_dict(data)
        decrypted = sm.decrypt_dict(encrypted)
        assert decrypted["quota_alert"]["webhook_url"] == data["quota_alert"]["webhook_url"]
        assert decrypted["api_key"] == data["api_key"]
        assert decrypted["other"] == "plain-value"

    def test_normal_mode_nested_plaintext_lenient(self, caplog):
        sm = SecretsManager("test-key-123")
        data = _sample_data()
        encrypted = sm.encrypt_dict(data)  # 顶层已加密
        # 仅嵌套字段手工改回明文（模拟迁移前的旧配置）
        encrypted["quota_alert"]["webhook_url"] = "https://hooks.example.com/abc"
        with caplog.at_level(logging.WARNING, logger="app.security.secrets_manager"):
            result = sm.decrypt_dict(encrypted)
        # 不抛、透传、记录路径、warning
        assert result["quota_alert"]["webhook_url"] == "https://hooks.example.com/abc"
        assert sm.last_migrated_paths == ["quota_alert.webhook_url"]
        assert any("quota_alert.webhook_url" in r.message for r in caplog.records)

    def test_normal_mode_top_level_plaintext_lenient(self, caplog):
        """v3: 顶层明文不再严格报错，改为宽容透传 + 记录路径（保存时自动写回加密）."""
        sm = SecretsManager("test-key-123")
        with caplog.at_level(logging.WARNING, logger="app.security.secrets_manager"):
            result = sm.decrypt_dict(
                {"api_key": "sk-plain", "quota_alert": {"webhook_url": "https://x"}}
            )
        assert result["api_key"] == "sk-plain"
        assert sm.last_migrated_paths == ["api_key", "quota_alert.webhook_url"]
        assert any("api_key" in r.message for r in caplog.records)

    def test_migration_mode_nested_plaintext_passthrough(self, monkeypatch, caplog):
        monkeypatch.setenv("DISABLE_ENCRYPTION", "1")
        sm = SecretsManager("test-key-123")
        data = _sample_data()
        with caplog.at_level(logging.INFO, logger="app.security.secrets_manager"):
            result = sm.decrypt_dict(data)
        assert result["quota_alert"]["webhook_url"] == data["quota_alert"]["webhook_url"]
        assert sm.last_migrated_paths == ["quota_alert.webhook_url"]
        assert result["api_key"] == "sk-top-secret"  # 顶层明文也透传（迁移模式）

    def test_invalid_token_normal_mode_raises_value_error(self):
        sm_a = SecretsManager("key-a")
        encrypted = sm_a.encrypt_dict(_sample_data())
        sm_b = SecretsManager("key-b")  # 错误 key
        with pytest.raises(ValueError, match="invalid Fernet token"):
            sm_b.decrypt_dict(encrypted)

    def test_invalid_token_migration_mode_warning_original(self, monkeypatch, caplog):
        sm_a = SecretsManager("key-a")  # 先以正常模式加密
        encrypted = sm_a.encrypt_dict(_sample_data())
        monkeypatch.setenv("DISABLE_ENCRYPTION", "1")
        sm_b = SecretsManager("key-b")  # 错误 key + 迁移模式
        with caplog.at_level(logging.WARNING, logger="app.security.secrets_manager"):
            result = sm_b.decrypt_dict(encrypted)
        # 原样保留（不解密也不丢弃）
        assert result["quota_alert"]["webhook_url"] == encrypted["quota_alert"]["webhook_url"]
        assert result["api_key"] == encrypted["api_key"]
        assert sm_b.last_migrated_paths == []

    def test_decrypt_dict_does_not_mutate_input(self):
        sm = SecretsManager("test-key-123")
        data = _sample_data()
        encrypted = sm.encrypt_dict(data)
        snapshot = copy.deepcopy(encrypted)
        sm.decrypt_dict(encrypted)
        assert encrypted == snapshot

    def test_missing_empty_non_str_and_non_dict_container_skipped(self):
        sm = SecretsManager("test-key-123")
        # quota_alert 缺失
        assert sm.decrypt_dict({}) == {}
        # 空串
        result = sm.decrypt_dict({"quota_alert": {"webhook_url": ""}})
        assert result["quota_alert"]["webhook_url"] == ""
        # 非 str
        result = sm.decrypt_dict({"quota_alert": {"webhook_url": 123}})
        assert result["quota_alert"]["webhook_url"] == 123
        # 容器非 dict
        result = sm.decrypt_dict({"quota_alert": "not-a-dict"})
        assert result["quota_alert"] == "not-a-dict"
        assert sm.last_migrated_paths == []

    def test_last_migrated_paths_reset_per_call(self):
        sm = SecretsManager("test-key-123")
        data = sm.encrypt_dict(_sample_data())
        data["quota_alert"]["webhook_url"] = "https://plain.example.com"  # 嵌套明文
        sm.decrypt_dict(data)
        assert sm.last_migrated_paths == ["quota_alert.webhook_url"]
        sm.decrypt_dict(sm.encrypt_dict(_sample_data()))  # 全密文
        assert sm.last_migrated_paths == []


class TestWriteEnabled:
    def test_write_enabled_property(self, monkeypatch):
        assert SecretsManager("test-key-123").write_enabled is True
        monkeypatch.setenv("DISABLE_ENCRYPTION", "1")
        assert SecretsManager("test-key-123").write_enabled is False
