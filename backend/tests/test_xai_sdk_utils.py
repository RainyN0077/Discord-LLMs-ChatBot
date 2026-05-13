from unittest.mock import MagicMock, patch

import pytest

from app.xai_sdk_utils import (
    build_xai_api_host,
    xai_sampling_usage_to_dict,
    xai_embedding_usage_to_dict,
    DEFAULT_XAI_API_HOST,
)


class TestBuildXaiApiHost:
    def test_build_xai_api_host_default(self):
        assert build_xai_api_host(None) == DEFAULT_XAI_API_HOST
        assert build_xai_api_host("") == DEFAULT_XAI_API_HOST

    def test_build_xai_api_host_custom(self):
        result = build_xai_api_host("https://custom.api.example.com")
        assert result == "custom.api.example.com"

    def test_build_xai_api_host_with_path(self):
        result = build_xai_api_host("https://api.example.com/v1/chat")
        assert result == "api.example.com"

    def test_build_xai_api_host_with_scheme(self):
        result = build_xai_api_host("api.x.ai")
        assert result == "api.x.ai"

    def test_build_xai_api_host_whitespace(self):
        result = build_xai_api_host("  https://host.io  ")
        assert result == "host.io"


class TestXaiSamplingUsageToDict:
    def test_xai_sampling_usage_to_dict(self):
        usage = MagicMock()
        usage.prompt_tokens = 100
        usage.completion_tokens = 50
        result = xai_sampling_usage_to_dict(usage)
        assert result == {"input_tokens": 100, "output_tokens": 50}

    def test_xai_sampling_usage_to_dict_none(self):
        assert xai_sampling_usage_to_dict(None) is None

    def test_xai_sampling_usage_to_dict_zero_tokens(self):
        usage = MagicMock()
        usage.prompt_tokens = 0
        usage.completion_tokens = 0
        result = xai_sampling_usage_to_dict(usage)
        assert result == {"input_tokens": 0, "output_tokens": 0}

    def test_xai_sampling_usage_to_dict_missing_attrs(self):
        usage = MagicMock(spec=[])
        result = xai_sampling_usage_to_dict(usage)
        assert result is None


class TestXaiEmbeddingUsageToDict:
    def test_xai_embedding_usage_to_dict(self):
        usage = MagicMock()
        usage.num_text_embeddings = 5
        usage.num_image_embeddings = 3
        result = xai_embedding_usage_to_dict(usage)
        assert result == {"num_text_embeddings": 5, "num_image_embeddings": 3}

    def test_xai_embedding_usage_to_dict_none(self):
        assert xai_embedding_usage_to_dict(None) is None

    def test_xai_embedding_usage_to_dict_missing_attrs(self):
        usage = MagicMock(spec=[])
        result = xai_embedding_usage_to_dict(usage)
        assert result is None
