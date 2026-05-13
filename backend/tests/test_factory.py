"""Tests for app.llm_providers.factory."""
import pytest
from unittest.mock import patch, MagicMock
from app.llm_providers.factory import get_llm_provider, PROVIDER_MAP
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
