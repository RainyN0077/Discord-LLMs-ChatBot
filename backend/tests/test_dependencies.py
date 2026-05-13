import pytest
from unittest.mock import patch, MagicMock

from fastapi import HTTPException


class TestGetApiKey:
    """Unit tests for get_api_key dependency."""

    def test_valid_api_key_returns_key(self):
        from app.dependencies import get_api_key

        with patch("app.dependencies.load_config") as mock_load:
            mock_load.return_value = {"api_secret_key": "correct-key"}

            import asyncio
            result = asyncio.run(get_api_key("correct-key"))
            assert result == "correct-key"

    def test_invalid_api_key_raises_403(self):
        from app.dependencies import get_api_key

        with patch("app.dependencies.load_config") as mock_load:
            mock_load.return_value = {"api_secret_key": "correct-key"}

            import asyncio
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(get_api_key("wrong-key"))
            assert exc_info.value.status_code == 403
            assert "Could not validate credentials" in exc_info.value.detail

    def test_missing_api_key_raises_403(self):
        from app.dependencies import get_api_key

        with patch("app.dependencies.load_config") as mock_load:
            mock_load.return_value = {"api_secret_key": "correct-key"}

            import asyncio
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(get_api_key(""))
            assert exc_info.value.status_code == 403

    def test_empty_configured_key_rejects(self):
        from app.dependencies import get_api_key

        with patch("app.dependencies.load_config") as mock_load:
            mock_load.return_value = {"api_secret_key": ""}

            import asyncio
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(get_api_key("any-key"))
            assert exc_info.value.status_code == 403

    def test_none_configured_key_rejects(self):
        from app.dependencies import get_api_key

        with patch("app.dependencies.load_config") as mock_load:
            mock_load.return_value = {}

            import asyncio
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(get_api_key("any-key"))
            assert exc_info.value.status_code == 403
