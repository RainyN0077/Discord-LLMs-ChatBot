"""Tests for DataPaths configuration class.

Covers:
  - Default path resolution
  - Environment variable overrides
  - ensure_dirs() directory creation
"""

import os
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]


class TestDataPathsDefaults:
    """DataPaths should resolve sensible defaults when no env vars are set."""

    def test_data_dir_defaults_to_cwd_data(self, monkeypatch):
        """DATA_DIR defaults to <cwd>/data when DATA_DIR env var is unset."""
        monkeypatch.delenv("DATA_DIR", raising=False)
        # Reimport to pick up the fresh default
        from app.paths import DataPaths

        # Force re-evaluation of the class attribute by reloading
        import importlib
        import app.paths
        importlib.reload(app.paths)
        from app.paths import DataPaths

        expected = Path.cwd() / "data"
        assert DataPaths.DATA_DIR == expected

    def test_bots_dir_is_under_data(self):
        from app.paths import DataPaths

        assert str(DataPaths.BOTS_DIR).startswith(str(DataPaths.DATA_DIR))
        assert DataPaths.BOTS_DIR.name == "bots"

    def test_log_dir_defaults_to_data_logs(self, monkeypatch):
        monkeypatch.delenv("LOG_DIR", raising=False)
        import importlib
        import app.paths
        importlib.reload(app.paths)
        from app.paths import DataPaths

        assert DataPaths.LOG_DIR == DataPaths.DATA_DIR / "logs"

    def test_knowledge_db_defaults_to_data_knowledge_base_sqlite(self, monkeypatch):
        monkeypatch.delenv("KNOWLEDGE_DB", raising=False)
        import importlib
        import app.paths
        importlib.reload(app.paths)
        from app.paths import DataPaths

        assert DataPaths.KNOWLEDGE_DB == DataPaths.DATA_DIR / "knowledge_base.sqlite"

    def test_usage_file_defaults_to_data_usage_data_json(self, monkeypatch):
        monkeypatch.delenv("USAGE_FILE", raising=False)
        import importlib
        import app.paths
        importlib.reload(app.paths)
        from app.paths import DataPaths

        assert DataPaths.USAGE_FILE == DataPaths.DATA_DIR / "usage_data.json"

    def test_config_file_is_under_data(self):
        from app.paths import DataPaths

        assert str(DataPaths.CONFIG_FILE).startswith(str(DataPaths.DATA_DIR))
        assert DataPaths.CONFIG_FILE.name == "config.json"

    def test_scripts_dir_defaults_to_project_scripts(self, monkeypatch):
        monkeypatch.delenv("SCRIPTS_DIR", raising=False)
        import importlib
        import app.paths
        importlib.reload(app.paths)
        from app.paths import DataPaths

        expected = Path(__file__).resolve().parent.parent.parent / "scripts"
        assert DataPaths.SCRIPTS_DIR == expected


class TestDataPathsEnvOverrides:
    """Environment variables should override DataPaths defaults."""

    def test_data_dir_env_override(self, monkeypatch):
        monkeypatch.setenv("DATA_DIR", "/custom/data/path")
        import importlib
        import app.paths
        importlib.reload(app.paths)
        from app.paths import DataPaths

        assert DataPaths.DATA_DIR == Path("/custom/data/path")

    def test_log_dir_env_override(self, monkeypatch):
        monkeypatch.setenv("LOG_DIR", "/custom/logs")
        import importlib
        import app.paths
        importlib.reload(app.paths)
        from app.paths import DataPaths

        assert DataPaths.LOG_DIR == Path("/custom/logs")

    def test_knowledge_db_env_override(self, monkeypatch):
        monkeypatch.setenv("KNOWLEDGE_DB", "/custom/kb.sqlite")
        import importlib
        import app.paths
        importlib.reload(app.paths)
        from app.paths import DataPaths

        assert DataPaths.KNOWLEDGE_DB == Path("/custom/kb.sqlite")

    def test_usage_file_env_override(self, monkeypatch):
        monkeypatch.setenv("USAGE_FILE", "/custom/usage.json")
        import importlib
        import app.paths
        importlib.reload(app.paths)
        from app.paths import DataPaths

        assert DataPaths.USAGE_FILE == Path("/custom/usage.json")

    def test_scripts_dir_env_override(self, monkeypatch):
        monkeypatch.setenv("SCRIPTS_DIR", "/custom/scripts")
        import importlib
        import app.paths
        importlib.reload(app.paths)
        from app.paths import DataPaths

        assert DataPaths.SCRIPTS_DIR == Path("/custom/scripts")

    def test_bots_dir_tracks_data_dir(self, monkeypatch):
        """BOTS_DIR should always be relative to DATA_DIR."""
        monkeypatch.setenv("DATA_DIR", "/custom/data")
        import importlib
        import app.paths
        importlib.reload(app.paths)
        from app.paths import DataPaths

        assert DataPaths.BOTS_DIR == Path("/custom/data/bots")

    def test_config_file_tracks_data_dir(self, monkeypatch):
        """CONFIG_FILE should always be relative to DATA_DIR."""
        monkeypatch.setenv("DATA_DIR", "/custom/data")
        import importlib
        import app.paths
        importlib.reload(app.paths)
        from app.paths import DataPaths

        assert DataPaths.CONFIG_FILE == Path("/custom/data/config.json")


class TestDataPathsEnsureDirs:
    """ensure_dirs() should create all required directories."""

    def test_ensure_dirs_creates_data_bots_logs(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path / "testdata"))
        import importlib
        import app.paths
        importlib.reload(app.paths)
        from app.paths import DataPaths

        DataPaths.ensure_dirs()
        assert DataPaths.DATA_DIR.exists()
        assert DataPaths.BOTS_DIR.exists()
        assert DataPaths.LOG_DIR.exists()

    def test_ensure_dirs_is_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_DIR", str(tmp_path / "idempotent"))
        import importlib
        import app.paths
        importlib.reload(app.paths)
        from app.paths import DataPaths

        DataPaths.ensure_dirs()
        DataPaths.ensure_dirs()  # should not raise
        assert DataPaths.DATA_DIR.exists()

    def test_ensure_dirs_does_not_create_knowledge_db(self, tmp_path, monkeypatch):
        """ensure_dirs should NOT create the SQLite DB file, only directories."""
        monkeypatch.setenv("DATA_DIR", str(tmp_path / "nodbfiles"))
        import importlib
        import app.paths
        importlib.reload(app.paths)
        from app.paths import DataPaths

        DataPaths.ensure_dirs()
        assert not DataPaths.KNOWLEDGE_DB.exists()
