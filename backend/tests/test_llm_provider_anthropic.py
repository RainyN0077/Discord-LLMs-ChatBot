import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm_providers.anthropic_provider import AnthropicProvider

pytestmark = [pytest.mark.unit]


@pytest.fixture
def anthropic_config():
    return {
        "api_key": "sk-ant-test",
        "model_name": "claude-sonnet-4-20250514",
        "stream_response": False,
        "custom_parameters": [],
    }


class FakeContentBlock:
    def __init__(self, block_type, text):
        self.type = block_type
        self.text = text


class FakeResponse:
    def __init__(self, text, stop_reason="end_turn"):
        self.content = [FakeContentBlock("text", text)]
        self.stop_reason = stop_reason


@pytest.fixture
def mock_anthropic_client():
    with patch("anthropic.AsyncAnthropic") as mock:
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.create = AsyncMock()
        client.messages.stream = MagicMock()
        mock.return_value = client
        yield mock


class TestPrepareMessages:
    def test_no_images_returns_unchanged(self, anthropic_config, mock_anthropic_client):
        provider = AnthropicProvider(anthropic_config)
        messages = [{"role": "user", "content": "Hello"}]
        result = provider._prepare_messages(messages, images=None)
        assert result == messages

    def test_with_images_last_message_content_becomes_list(self, anthropic_config, mock_anthropic_client):
        provider = AnthropicProvider(anthropic_config)
        messages = [{"role": "user", "content": "Describe these images"}]
        image_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        result = provider._prepare_messages(messages, images=[image_bytes])

        assert len(result) == 1
        assert result[0]["role"] == "user"
        content = result[0]["content"]
        assert isinstance(content, list)
        assert len(content) == 2
        assert content[0] == {"type": "text", "text": "Describe these images"}
        assert content[1]["type"] == "image"
        assert content[1]["source"]["type"] == "base64"
        assert content[1]["source"]["media_type"] == "image/jpeg"
        assert content[1]["source"]["data"] == base64.b64encode(image_bytes).decode("utf-8")

    def test_with_multiple_images(self, anthropic_config, mock_anthropic_client):
        provider = AnthropicProvider(anthropic_config)
        messages = [{"role": "user", "content": "Look at these"}]
        img1 = b"\xff\xd8AA"
        img2 = b"\xff\xd8BB"
        result = provider._prepare_messages(messages, images=[img1, img2])

        content = result[0]["content"]
        assert len(content) == 3
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image"
        assert content[2]["type"] == "image"
        assert content[1]["source"]["data"] == base64.b64encode(img1).decode("utf-8")
        assert content[2]["source"]["data"] == base64.b64encode(img2).decode("utf-8")

    def test_original_messages_not_mutated(self, anthropic_config, mock_anthropic_client):
        provider = AnthropicProvider(anthropic_config)
        messages = [{"role": "user", "content": "Hello"}]
        original = messages.copy()
        provider._prepare_messages(messages, images=[b"\xff\xd8"])
        assert messages == original


class TestHandleError:
    def test_returns_llm_provider_error_string(self, anthropic_config, mock_anthropic_client):
        provider = AnthropicProvider(anthropic_config)
        result = provider._handle_error(Exception("test error"))
        assert isinstance(result, str)
        assert result.startswith("LLM_PROVIDER_ERROR:")
        assert "AnthropicProvider" in result
        assert "test error" in result


class TestGetResponseStream:
    @pytest.mark.asyncio
    async def test_system_message_extracted_as_system_param(self, anthropic_config, mock_anthropic_client):
        provider = AnthropicProvider(anthropic_config)
        response = FakeResponse("Hi there")
        provider.client.messages.create.return_value = response

        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
        ]
        results = [r async for r in provider.get_response_stream(messages)]

        call_kwargs = provider.client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "You are helpful"
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"
        assert results[0] == ("final", "Hi there")

    @pytest.mark.asyncio
    async def test_no_system_message_no_system_param(self, anthropic_config, mock_anthropic_client):
        provider = AnthropicProvider(anthropic_config)
        response = FakeResponse("Hey")
        provider.client.messages.create.return_value = response

        messages = [{"role": "user", "content": "Hello"}]
        results = [r async for r in provider.get_response_stream(messages)]

        call_kwargs = provider.client.messages.create.call_args.kwargs
        assert "system" not in call_kwargs
        assert results[0] == ("final", "Hey")

    @pytest.mark.asyncio
    async def test_api_exception_yields_error(self, anthropic_config, mock_anthropic_client):
        provider = AnthropicProvider(anthropic_config)
        provider.client.messages.create.side_effect = Exception("API Error")

        messages = [{"role": "user", "content": "Hello"}]
        results = [r async for r in provider.get_response_stream(messages)]

        assert len(results) == 1
        assert results[0][0] == "final"
        assert results[0][1].startswith("LLM_PROVIDER_ERROR:")
        assert "API Error" in results[0][1]

    @pytest.mark.asyncio
    async def test_success_text_response(self, anthropic_config, mock_anthropic_client):
        provider = AnthropicProvider(anthropic_config)
        response = FakeResponse("Claude says hello")
        provider.client.messages.create.return_value = response

        messages = [{"role": "user", "content": "Hi"}]
        results = [r async for r in provider.get_response_stream(messages)]

        assert len(results) == 1
        assert results[0] == ("final", "Claude says hello")


class TestMaxTokensDefault:
    def test_max_tokens_default_applied_when_not_in_custom_params(self, anthropic_config, mock_anthropic_client):
        provider = AnthropicProvider(anthropic_config)
        assert "max_tokens" in provider.custom_params
        assert provider.custom_params["max_tokens"] == 4096

    def test_max_tokens_preserved_when_already_in_custom_params(self, mock_anthropic_client):
        config = {
            "api_key": "sk-ant-test",
            "model_name": "claude-sonnet-4-20250514",
            "stream_response": False,
            "custom_parameters": [{"name": "max_tokens", "value": 1024}],
        }
        provider = AnthropicProvider(config)
        assert provider.custom_params["max_tokens"] == 1024
