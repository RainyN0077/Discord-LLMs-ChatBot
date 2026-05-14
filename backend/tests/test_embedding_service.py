import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit]

from app.core_logic.embedding_service import (
    cosine_similarity,
    get_embedding,
    get_embeddings_batch,
    _get_embedding_client,
)


def _make_config(**overrides):
    config = {
        "embedding_provider": "openai",
        "embedding_api_key": "sk-test",
        "embedding_base_url": "https://api.openai.com/v1",
        "embedding_model_name": "text-embedding-3-small",
    }
    config.update(overrides)
    return config


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert math.isclose(cosine_similarity(v, v), 1.0, rel_tol=1e-9)

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0

    def test_empty_vectors(self):
        assert cosine_similarity([], []) == 0.0
        assert cosine_similarity([1.0], []) == 0.0
        assert cosine_similarity([], [1.0]) == 0.0

    def test_different_length_vectors(self):
        assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0

    def test_zero_vectors(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
        assert cosine_similarity([1.0, 2.0], [0.0, 0.0]) == 0.0
        assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0

    def test_normal_vectors(self):
        assert math.isclose(
            cosine_similarity([1.0, 2.0, 3.0], [4.0, 5.0, 6.0]),
            0.9746318461970762,
            rel_tol=1e-9,
        )

    def test_negative_values(self):
        result = cosine_similarity([-1.0, -2.0], [1.0, 2.0])
        assert result < 0.0


class TestGetEmbeddingClient:
    def _clear_cache(self):
        from app.core_logic import embedding_service
        embedding_service._embedding_clients.clear()

    def test_cache_same_config_same_client(self):
        self._clear_cache()
        config = _make_config()
        with patch("openai.AsyncOpenAI") as mock_async_openai:
            mock_async_openai.side_effect = lambda *a, **kw: MagicMock()
            client1 = _get_embedding_client(config)
            client2 = _get_embedding_client(config)
            assert client1 is client2
            assert mock_async_openai.call_count == 1

    def test_cache_different_api_key_different_client(self):
        self._clear_cache()
        config1 = _make_config(embedding_api_key="sk-aaa")
        config2 = _make_config(embedding_api_key="sk-bbb")
        with patch("openai.AsyncOpenAI") as mock_async_openai:
            mock_async_openai.side_effect = lambda *a, **kw: MagicMock()
            client1 = _get_embedding_client(config1)
            client2 = _get_embedding_client(config2)
            assert client1 is not client2

    def test_cache_different_provider_different_client(self):
        self._clear_cache()
        config1 = _make_config(embedding_provider="openai")
        config2 = _make_config(embedding_provider="google")
        with patch("openai.AsyncOpenAI") as mock_async_openai:
            mock_async_openai.side_effect = lambda *a, **kw: MagicMock()
            client1 = _get_embedding_client(config1)
            client2 = _get_embedding_client(config2)
            assert client1 is not client2

    def test_cache_different_base_url_different_client(self):
        self._clear_cache()
        config1 = _make_config(embedding_base_url="https://api.openai.com/v1")
        config2 = _make_config(embedding_base_url="https://custom.com/v1")
        with patch("openai.AsyncOpenAI") as mock_async_openai:
            mock_async_openai.side_effect = lambda *a, **kw: MagicMock()
            client1 = _get_embedding_client(config1)
            client2 = _get_embedding_client(config2)
            assert client1 is not client2

    def test_cache_with_port_appended_to_base_url(self):
        self._clear_cache()
        config = _make_config(embedding_base_url="https://localhost", embedding_port="8080")
        with patch("openai.AsyncOpenAI") as mock_async_openai:
            mock_async_openai.side_effect = lambda *a, **kw: MagicMock()
            client = _get_embedding_client(config)
            assert client is not None
            call_kwargs = mock_async_openai.call_args.kwargs
            assert call_kwargs["base_url"] == "https://localhost:8080"

    def test_cache_without_port_unchanged_base_url(self):
        self._clear_cache()
        config = _make_config(embedding_base_url="https://localhost", embedding_port="")
        with patch("openai.AsyncOpenAI") as mock_async_openai:
            mock_async_openai.side_effect = lambda *a, **kw: MagicMock()
            client = _get_embedding_client(config)
            assert client is not None
            call_kwargs = mock_async_openai.call_args.kwargs
            assert call_kwargs["base_url"] == "https://localhost"

    def test_cache_fallback_api_key(self):
        self._clear_cache()
        config1 = _make_config(embedding_api_key=None)
        config1["api_key"] = "sk-fallback"
        config2 = _make_config(embedding_api_key="sk-fallback")
        with patch("openai.AsyncOpenAI") as mock_async_openai:
            mock_async_openai.side_effect = lambda *a, **kw: MagicMock()
            client1 = _get_embedding_client(config1)
            client2 = _get_embedding_client(config2)
            assert client1 is client2

    def test_cache_fallback_base_url(self):
        self._clear_cache()
        config1 = _make_config(embedding_base_url=None)
        config1["base_url"] = "https://fallback.com/v1"
        config2 = _make_config(embedding_base_url="https://fallback.com/v1")
        with patch("openai.AsyncOpenAI") as mock_async_openai:
            mock_async_openai.side_effect = lambda *a, **kw: MagicMock()
            client1 = _get_embedding_client(config1)
            client2 = _get_embedding_client(config2)
            assert client1 is client2


class TestGetEmbedding:
    @pytest.mark.asyncio
    async def test_empty_text_returns_none(self):
        config = _make_config()
        result = await get_embedding("", config)
        assert result is None

    @pytest.mark.asyncio
    async def test_whitespace_text_returns_none(self):
        config = _make_config()
        result = await get_embedding("   \t\n  ", config)
        assert result is None

    @pytest.mark.asyncio
    async def test_successful_embedding(self):
        config = _make_config()
        expected_embedding = [0.1, 0.2, 0.3]
        mock_client = MagicMock()
        mock_data = MagicMock()
        mock_data.embedding = expected_embedding
        mock_create = AsyncMock()
        mock_create.return_value.data = [mock_data]
        mock_client.embeddings.create = mock_create

        with patch("app.core_logic.embedding_service._get_embedding_client", return_value=mock_client):
            result = await get_embedding("hello world", config)
        assert result == expected_embedding
        mock_create.assert_awaited_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["model"] == "text-embedding-3-small"
        assert call_kwargs["input"] == "hello world"

    @pytest.mark.asyncio
    async def test_strips_text_before_embedding(self):
        config = _make_config()
        mock_client = MagicMock()
        mock_data = MagicMock()
        mock_data.embedding = [0.1]
        mock_create = AsyncMock()
        mock_create.return_value.data = [mock_data]
        mock_client.embeddings.create = mock_create

        with patch("app.core_logic.embedding_service._get_embedding_client", return_value=mock_client):
            await get_embedding("  hello  ", config)
        assert mock_create.call_args.kwargs["input"] == "hello"

    @pytest.mark.asyncio
    async def test_api_exception_fallback(self):
        config = _make_config()
        mock_client = MagicMock()
        mock_client.embeddings.create = AsyncMock(side_effect=RuntimeError("API error"))

        with patch("app.core_logic.embedding_service._get_embedding_client", return_value=mock_client):
            result = await get_embedding("test", config)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_response_data_returns_none(self):
        config = _make_config()
        mock_client = MagicMock()
        mock_create = AsyncMock()
        mock_create.return_value.data = []
        mock_client.embeddings.create = mock_create

        with patch("app.core_logic.embedding_service._get_embedding_client", return_value=mock_client):
            result = await get_embedding("test", config)
        assert result is None

    @pytest.mark.asyncio
    async def test_uses_custom_model_name(self):
        config = _make_config(embedding_model_name="custom-model")
        mock_client = MagicMock()
        mock_data = MagicMock()
        mock_data.embedding = [0.1]
        mock_create = AsyncMock()
        mock_create.return_value.data = [mock_data]
        mock_client.embeddings.create = mock_create

        with patch("app.core_logic.embedding_service._get_embedding_client", return_value=mock_client):
            await get_embedding("test", config)
        assert mock_create.call_args.kwargs["model"] == "custom-model"


class TestGetEmbeddingsBatch:
    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(self):
        config = _make_config()
        result = await get_embeddings_batch([], config)
        assert result == []

    @pytest.mark.asyncio
    async def test_successful_batch(self):
        config = _make_config()
        embeddings = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        mock_client = MagicMock()
        mock_data_items = []
        for emb in embeddings:
            item = MagicMock()
            item.embedding = emb
            mock_data_items.append(item)
        mock_create = AsyncMock()
        mock_create.return_value.data = mock_data_items
        mock_client.embeddings.create = mock_create

        with patch("app.core_logic.embedding_service._get_embedding_client", return_value=mock_client):
            result = await get_embeddings_batch(["text1", "text2", "text3"], config)
        assert result == embeddings
        mock_create.assert_awaited_once()
        assert mock_create.call_args.kwargs["input"] == ["text1", "text2", "text3"]

    @pytest.mark.asyncio
    async def test_strips_each_text(self):
        config = _make_config()
        mock_client = MagicMock()
        mock_data = MagicMock()
        mock_data.embedding = [0.1]
        mock_create = AsyncMock()
        mock_create.return_value.data = [mock_data, mock_data, mock_data]
        mock_client.embeddings.create = mock_create

        with patch("app.core_logic.embedding_service._get_embedding_client", return_value=mock_client):
            await get_embeddings_batch(["  hello  ", " world ", "\ttest\t"], config)
        assert mock_create.call_args.kwargs["input"] == ["hello", "world", "test"]

    @pytest.mark.asyncio
    async def test_exception_fallback_returns_nones(self):
        config = _make_config()
        mock_client = MagicMock()
        mock_client.embeddings.create = AsyncMock(side_effect=RuntimeError("Batch API error"))

        with patch("app.core_logic.embedding_service._get_embedding_client", return_value=mock_client):
            result = await get_embeddings_batch(["text1", "text2", "text3"], config)
        assert result == [None, None, None]

    @pytest.mark.asyncio
    async def test_partial_missing_embeddings_filled_with_none(self):
        config = _make_config()
        mock_client = MagicMock()
        item1 = MagicMock()
        item1.embedding = [0.1]
        item2 = MagicMock()
        item2.embedding = None
        mock_create = AsyncMock()
        mock_create.return_value.data = [item1, item2]
        mock_client.embeddings.create = mock_create

        with patch("app.core_logic.embedding_service._get_embedding_client", return_value=mock_client):
            result = await get_embeddings_batch(["text1", "text2", "text3"], config)
        assert result == [[0.1], None, None]

    @pytest.mark.asyncio
    async def test_uses_default_model_name(self):
        config = _make_config()
        mock_client = MagicMock()
        mock_data = MagicMock()
        mock_data.embedding = [0.1]
        mock_create = AsyncMock()
        mock_create.return_value.data = [mock_data]
        mock_client.embeddings.create = mock_create

        with patch("app.core_logic.embedding_service._get_embedding_client", return_value=mock_client):
            await get_embeddings_batch(["text"], config)
        assert mock_create.call_args.kwargs["model"] == "text-embedding-3-small"
