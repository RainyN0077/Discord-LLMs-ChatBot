import pytest

pytestmark = [pytest.mark.unit]
from unittest.mock import patch

from fastapi import HTTPException


class TestGetApiKey:
    """Unit tests for get_api_key dependency."""

    @pytest.mark.asyncio
    async def test_valid_api_key_returns_key(self):
        from app.dependencies import get_api_key
        with patch("app.dependencies.load_config") as mock_load:
            mock_load.return_value = {"api_secret_key": "correct-key"}
            result = await get_api_key("correct-key")
            assert result == "correct-key"

    @pytest.mark.asyncio
    async def test_invalid_api_key_raises_403(self):
        from app.dependencies import get_api_key
        with patch("app.dependencies.load_config") as mock_load:
            mock_load.return_value = {"api_secret_key": "correct-key"}
            with pytest.raises(HTTPException) as exc_info:
                await get_api_key("wrong-key")
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_403(self):
        from app.dependencies import get_api_key
        with patch("app.dependencies.load_config") as mock_load:
            mock_load.return_value = {"api_secret_key": "correct-key"}
            with pytest.raises(HTTPException) as exc_info:
                await get_api_key("")
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_configured_key_rejects(self):
        from app.dependencies import get_api_key
        with patch("app.dependencies.load_config") as mock_load:
            mock_load.return_value = {"api_secret_key": ""}
            with pytest.raises(HTTPException) as exc_info:
                await get_api_key("any-key")
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_none_configured_key_rejects(self):
        from app.dependencies import get_api_key
        with patch("app.dependencies.load_config") as mock_load:
            mock_load.return_value = {}
            with pytest.raises(HTTPException) as exc_info:
                await get_api_key("any-key")
            assert exc_info.value.status_code == 401