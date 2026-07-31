"""Tests for app.llm_providers.factory."""
import pytest
from unittest.mock import patch, MagicMock
from app.llm_providers.factory import get_llm_provider, PROVIDER_MAP
from app.llm_providers.base import LLMProvider, normalize_provider_name
from app.ports.llm_provider import ProviderHealth, QuotaInfo
from app.llm_providers.openai_provider import OpenAIProvider
from app.llm_providers.google_provider import GoogleProvider
from app.llm_providers.anthropic_provider import AnthropicProvider
from app.llm_providers.xai_provider import XAIProvider


class TestProviderMap:
    def test_all_providers_registered(self):
        assert "openai" in PROVIDER_MAP
        assert "google" in PROVIDER_MAP
        assert "anthropic" in PROVIDER_MAP
        assert "grok" in PROVIDER_MAP

    def test_openai_maps_to_correct_class(self):
        assert PROVIDER_MAP["openai"] == OpenAIProvider

    def test_google_maps_to_correct_class(self):
        assert PROVIDER_MAP["google"] == GoogleProvider

    def test_anthropic_maps_to_correct_class(self):
        assert PROVIDER_MAP["anthropic"] == AnthropicProvider

    def test_grok_maps_to_correct_class(self):
        assert PROVIDER_MAP["grok"] == XAIProvider


class TestGetLlmProvider:
    def test_returns_openai_by_default(self):
        with patch.object(OpenAIProvider, "__init__", lambda self, config: None):
            provider = get_llm_provider({})
        assert isinstance(provider, OpenAIProvider)

    def test_returns_openai_explicit(self):
        with patch.object(OpenAIProvider, "__init__", lambda self, config: None):
            provider = get_llm_provider({"llm_provider": "openai"})
        assert isinstance(provider, OpenAIProvider)

    def test_returns_google(self):
        with patch.object(GoogleProvider, "__init__", lambda self, config: None):
            provider = get_llm_provider({"llm_provider": "google"})
        assert isinstance(provider, GoogleProvider)

    def test_returns_anthropic(self):
        with patch.object(AnthropicProvider, "__init__", lambda self, config: None):
            provider = get_llm_provider({"llm_provider": "anthropic"})
        assert isinstance(provider, AnthropicProvider)

    def test_returns_grok_for_xai(self):
        with patch.object(XAIProvider, "__init__", lambda self, config: None):
            provider = get_llm_provider({"llm_provider": "xai"})
        assert isinstance(provider, XAIProvider)

    def test_returns_grok_explicit(self):
        with patch.object(XAIProvider, "__init__", lambda self, config: None):
            provider = get_llm_provider({"llm_provider": "grok"})
        assert isinstance(provider, XAIProvider)

    def test_case_insensitive(self):
        with patch.object(OpenAIProvider, "__init__", lambda self, config: None):
            provider = get_llm_provider({"llm_provider": "OPENAI"})
        assert isinstance(provider, OpenAIProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            get_llm_provider({"llm_provider": "nonexistent_provider_v2"})

    def test_provider_receives_config(self):
        with patch.object(OpenAIProvider, "__init__", lambda self, config: None):
            provider = get_llm_provider({"llm_provider": "openai", "api_key": "sk-test"})
        assert isinstance(provider, OpenAIProvider)


class TestProviderContract:
    """Task 1.3.1: 契约对齐 — LLMProvider 显式实现 ProviderHealth/QuotaInfo."""

    @staticmethod
    def _fresh_provider(config):
        """构造带真实 config 的 provider 实例（跳过网络客户端构造）."""
        from app.llm_providers.factory import clear_provider_cache
        clear_provider_cache()
        provider_class = PROVIDER_MAP[normalize_provider_name(config.get("llm_provider"))]
        with patch.object(
            provider_class,
            "__init__",
            lambda self, cfg: setattr(self, "config", cfg),
        ):
            return get_llm_provider(config)

    @pytest.mark.parametrize(
        ("config", "expected_name"),
        [
            ({"llm_provider": "openai"}, "openai"),
            ({"llm_provider": "google"}, "google"),
            ({"llm_provider": "anthropic"}, "anthropic"),
            ({"llm_provider": "grok"}, "grok"),
        ],
    )
    def test_provider_implements_contract(self, config, expected_name):
        config = dict(config)
        config["openai_model_name"] = "test-model"
        provider = self._fresh_provider(config)
        assert isinstance(provider, LLMProvider)
        assert isinstance(provider, ProviderHealth)
        assert isinstance(provider, QuotaInfo)
        assert provider.provider_name == expected_name
        assert provider.model_name == "test-model"

    def test_provider_name_default(self):
        provider = self._fresh_provider({})
        assert provider.provider_name == "openai"
        assert provider.model_name == ""

    def test_provider_name_xai_normalized(self):
        provider = self._fresh_provider({"llm_provider": "xai"})
        assert provider.provider_name == "grok"
        assert provider.model_name == ""

    async def test_get_usage_stats_async(self):
        provider = self._fresh_provider({})
        stats = await provider.get_usage_stats()
        assert set(stats.keys()) == {
            "total_requests",
            "total_input_tokens",
            "total_output_tokens",
            "last_request_at",
            "errors_last_hour",
        }
