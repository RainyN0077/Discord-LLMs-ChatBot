"""SecretsManager v3 自动 key 管理测试 (傻瓜式启动).

覆盖:
- 无 ENCRYPTION_KEY 时自动生成并持久化到 .env
- .env 已存在 ENCRYPTION_KEY 时复用（不重复生成）
- 生成后的 key 可用于加密/解密往返
- 生成逻辑不污染真实 backend/.env（env_file 指向 tmp_path）
"""
import os

from app.security.secrets_manager import SecretsManager


class TestAutoKey:
    def test_auto_generates_and_persists_key(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        env_file = tmp_path / ".env"

        sm = SecretsManager("", env_file=env_file)

        # key 已生成并写入环境
        assert sm._fernet is not None
        persisted = os.environ.get("ENCRYPTION_KEY")
        assert persisted
        # 已持久化到 .env 文件
        content = env_file.read_text(encoding="utf-8")
        assert f"ENCRYPTION_KEY={persisted}" in content

    def test_reuses_key_from_env_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("LOGURU_LEVEL=INFO\n", encoding="utf-8")

        sm1 = SecretsManager("", env_file=env_file)
        key1 = os.environ.get("ENCRYPTION_KEY")

        # 模拟重启：新进程环境（清掉环境变量），再次初始化
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        sm2 = SecretsManager("", env_file=env_file)
        key2 = os.environ.get("ENCRYPTION_KEY")

        assert key1 == key2  # 复用同一把 key，已加密数据可解

    def test_generated_key_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        sm = SecretsManager("", env_file=tmp_path / ".env")

        data = {"api_key": "sk-secret", "quota_alert": {"webhook_url": "https://x"}}
        encrypted = sm.encrypt_dict(data)
        decrypted = sm.decrypt_dict(encrypted)
        assert decrypted["api_key"] == "sk-secret"
        assert decrypted["quota_alert"]["webhook_url"] == "https://x"

    def test_env_file_write_failure_falls_back_to_in_memory_key(
        self, tmp_path, monkeypatch, caplog
    ):
        """写 .env 失败（如只读目录）时降级为仅当前进程有效的 key，不崩溃."""
        import logging

        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=1\n", encoding="utf-8")
        # 目录设为只读，模拟写入失败（Windows 上目录只读不阻止文件写入，
        # 改为直接把 env_file 指向一个不存在的目录）
        env_file = tmp_path / "no_such_dir" / ".env"

        with caplog.at_level(logging.WARNING, logger="app.security.secrets_manager"):
            sm = SecretsManager("", env_file=env_file)

        assert sm._fernet is not None
        assert os.environ.get("ENCRYPTION_KEY")
        assert any("could not persist" in r.message for r in caplog.records)

    def test_disabled_mode_does_not_generate_key(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        monkeypatch.setenv("DISABLE_ENCRYPTION", "1")
        env_file = tmp_path / ".env"

        sm = SecretsManager("", env_file=env_file)

        assert sm._fernet is None
        assert not env_file.exists()  # 迁移模式不写任何东西
        assert sm.write_enabled is False
