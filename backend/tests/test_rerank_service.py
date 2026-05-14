import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core_logic.rerank_service import rerank, _get_rerank_client
import app.core_logic.rerank_service as rmod

pytestmark = [pytest.mark.unit]


def _clear_client_cache():
    rmod._rerank_clients.clear()


class _AsyncCtx:
    def __init__(self, val):
        self._val = val

    async def __aenter__(self):
        return self._val

    async def __aexit__(self, *a):
        pass


def _make_config(**overrides):
    cfg = {
        "rerank_provider": "openai",
        "api_key": "sk-test-key",
        "base_url": "https://api.example.com",
    }
    cfg.update(overrides)
    return cfg


class TestGetRerankClient:
    def test_cached_on_second_call(self):
        _clear_client_cache()
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = MagicMock(name="client")
            config = _make_config()
            c1 = _get_rerank_client(config)
            c2 = _get_rerank_client(config)
            assert c1 is c2
            mock_openai.assert_called_once()

    def test_different_config_creates_different_client(self):
        _clear_client_cache()
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_openai.side_effect = lambda **kw: MagicMock(name="client")
            config1 = _make_config(api_key="key1")
            config2 = _make_config(api_key="key2")
            c1 = _get_rerank_client(config1)
            c2 = _get_rerank_client(config2)
            assert c1 is not c2
            assert mock_openai.call_count == 2

    def test_port_added_to_base_url(self):
        _clear_client_cache()
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_openai.return_value = MagicMock(name="client")
            config = _make_config(base_url="https://localhost", rerank_port="8080")
            _get_rerank_client(config)
            assert mock_openai.call_args.kwargs["base_url"] == "https://localhost:8080"


class TestRerank:
    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self):
        result = await rerank("", ["doc1", "doc2"], _make_config())
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_documents_returns_empty(self):
        result = await rerank("query", [], _make_config())
        assert result == []

    @pytest.mark.asyncio
    async def test_successful_response_returns_sorted_tuples(self):
        _clear_client_cache()
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.api_key = "sk-test"
            mock_client.base_url = "https://api.example.com"
            mock_openai.return_value = mock_client

            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value={
                "results": [
                    {"index": 0, "relevance_score": 0.3},
                    {"index": 1, "relevance_score": 0.9},
                    {"index": 2, "relevance_score": 0.5},
                ]
            })

            mock_session = MagicMock()
            mock_session.post.return_value = _AsyncCtx(mock_resp)

            with patch("aiohttp.ClientSession", return_value=_AsyncCtx(mock_session)):
                result = await rerank("test query", ["a", "b", "c"], _make_config())
                assert result == [(1, 0.9), (2, 0.5), (0, 0.3)]

    @pytest.mark.asyncio
    async def test_http_non_200_returns_empty(self):
        _clear_client_cache()
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.api_key = "sk-test"
            mock_client.base_url = "https://api.example.com"
            mock_openai.return_value = mock_client

            mock_resp = MagicMock()
            mock_resp.status = 500
            mock_resp.text = AsyncMock(return_value="Internal Server Error")

            mock_session = MagicMock()
            mock_session.post.return_value = _AsyncCtx(mock_resp)

            with patch("aiohttp.ClientSession", return_value=_AsyncCtx(mock_session)):
                result = await rerank("test query", ["a"], _make_config())
                assert result == []

    @pytest.mark.asyncio
    async def test_api_exception_returns_empty(self):
        _clear_client_cache()
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.api_key = "sk-test"
            mock_client.base_url = "https://api.example.com"
            mock_openai.return_value = mock_client

            mock_session = MagicMock()
            mock_session.post.side_effect = Exception("Connection refused")

            with patch("aiohttp.ClientSession", return_value=_AsyncCtx(mock_session)):
                result = await rerank("test query", ["a"], _make_config())
                assert result == []

    @pytest.mark.asyncio
    async def test_top_n_included_in_payload(self):
        _clear_client_cache()
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.api_key = "sk-test"
            mock_client.base_url = "https://api.example.com"
            mock_openai.return_value = mock_client

            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value={"results": []})

            mock_session = MagicMock()
            mock_session.post.return_value = _AsyncCtx(mock_resp)

            with patch("aiohttp.ClientSession", return_value=_AsyncCtx(mock_session)):
                await rerank("test query", ["a"], _make_config(), top_n=5)
                payload = mock_session.post.call_args[1]["json"]
                assert payload["top_n"] == 5

    @pytest.mark.asyncio
    async def test_api_path_without_leading_slash_prepended(self):
        _clear_client_cache()
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.api_key = "sk-test"
            mock_client.base_url = "https://api.example.com/v1"
            mock_openai.return_value = mock_client

            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value={"results": []})

            mock_session = MagicMock()
            mock_session.post.return_value = _AsyncCtx(mock_resp)

            with patch("aiohttp.ClientSession", return_value=_AsyncCtx(mock_session)):
                config = _make_config(rerank_api_path="v1/rerank")
                await rerank("test query", ["a"], config)
                url = mock_session.post.call_args[0][0]
                assert url == "https://api.example.com/v1/v1/rerank"
