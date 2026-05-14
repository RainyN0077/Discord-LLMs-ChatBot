import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.llm_providers.openai_provider import OpenAIProvider

pytestmark = [pytest.mark.unit]


class _AsyncIter:
    def __init__(self, items):
        self._items = items

    def __aiter__(self):
        self._iter = iter(self._items)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


@pytest.fixture
def config():
    return {
        "api_key": "sk-test",
        "model_name": "gpt-4o",
        "stream_response": False,
        "custom_parameters": [],
    }


@pytest.fixture
def config_streaming():
    return {
        "api_key": "sk-test",
        "model_name": "gpt-4o",
        "stream_response": True,
        "custom_parameters": [],
    }


class TestInit:
    @patch("openai.AsyncOpenAI")
    def test_init_creates_client_and_sets_env(self, mock_async_openai, config):
        provider = OpenAIProvider(config)

        assert provider.api_key == "sk-test"
        assert provider.model == "gpt-4o"
        assert provider.stream is False
        assert provider.custom_params == {}
        mock_async_openai.assert_called_once_with(api_key="sk-test", base_url=None)

    @patch("openai.AsyncOpenAI")
    def test_init_with_base_url(self, mock_async_openai, config):
        config["base_url"] = "https://custom.openai.com/v1"
        provider = OpenAIProvider(config)

        mock_async_openai.assert_called_once_with(api_key="sk-test", base_url="https://custom.openai.com/v1")

    @patch("openai.AsyncOpenAI")
    def test_init_prefers_openai_base_url_over_base_url(self, mock_async_openai, config):
        config["base_url"] = "https://generic.com/v1"
        config["openai_base_url"] = "https://openai.custom.com/v1"
        provider = OpenAIProvider(config)

        mock_async_openai.assert_called_once_with(api_key="sk-test", base_url="https://openai.custom.com/v1")

    @patch("openai.AsyncOpenAI")
    def test_init_with_custom_parameters(self, mock_async_openai, config):
        config["custom_parameters"] = [
            {"name": "temperature", "value": 0.7},
            {"name": "max_tokens", "value": 500},
        ]
        provider = OpenAIProvider(config)

        assert provider.custom_params == {"temperature": 0.7, "max_tokens": 500}


class TestPrepareMessages:
    def test_no_images_returns_messages_unchanged(self, config):
        provider = OpenAIProvider(config)
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        result = provider._prepare_messages(messages, None)
        assert result == messages
        assert result is messages

    def test_no_images_empty_list_returns_messages_unchanged(self, config):
        provider = OpenAIProvider(config)
        messages = [{"role": "user", "content": "Hello"}]
        result = provider._prepare_messages(messages, [])
        assert result == messages
        assert result is messages

    def test_with_images_modifies_last_message_content(self, config):
        provider = OpenAIProvider(config)
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Describe this image."},
        ]
        img_bytes = b"fake_image_data_123"
        result = provider._prepare_messages(messages, [img_bytes])

        assert len(result) == 2
        assert result[0] == messages[0]
        last_msg = result[1]
        assert last_msg["role"] == "user"
        assert isinstance(last_msg["content"], list)
        assert len(last_msg["content"]) == 2

        text_part = last_msg["content"][0]
        assert text_part["type"] == "text"
        assert text_part["text"] == "Describe this image."

        image_part = last_msg["content"][1]
        assert image_part["type"] == "image_url"
        expected_b64 = base64.b64encode(img_bytes).decode("utf-8")
        assert image_part["image_url"]["url"] == f"data:image/jpeg;base64,{expected_b64}"

    def test_with_multiple_images(self, config):
        provider = OpenAIProvider(config)
        messages = [{"role": "user", "content": "Compare these images."}]
        img1 = b"image_one"
        img2 = b"image_two"

        result = provider._prepare_messages(messages, [img1, img2])

        content = result[0]["content"]
        assert len(content) == 3
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
        assert content[2]["type"] == "image_url"
        assert base64.b64encode(img1).decode("utf-8") in content[1]["image_url"]["url"]
        assert base64.b64encode(img2).decode("utf-8") in content[2]["image_url"]["url"]

    def test_with_images_preserves_other_message_roles(self, config):
        provider = OpenAIProvider(config)
        messages = [
            {"role": "system", "content": "System prompt."},
            {"role": "assistant", "content": "How can I help?"},
            {"role": "user", "content": "Look at this."},
        ]
        result = provider._prepare_messages(messages, [b"img"])

        assert result[0] == messages[0]
        assert result[1] == messages[1]
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "How can I help?"
        assert result[2]["role"] == "user"
        assert isinstance(result[2]["content"], list)


class TestHandleError:
    def test_handle_error_returns_formatted_string(self, config):
        provider = OpenAIProvider(config)
        error = Exception("API connection failed")
        result = provider._handle_error(error)

        assert result.startswith("LLM_PROVIDER_ERROR:")
        assert "OpenAIProvider" in result
        assert "API connection failed" in result


class TestGetResponseStreamNonStreaming:
    @pytest.mark.asyncio
    async def test_simple_text_response_success(self, config):
        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client

            mock_usage = MagicMock()
            mock_usage.prompt_tokens = 50
            mock_usage.completion_tokens = 30

            mock_message = MagicMock()
            mock_message.content = "Hello, how can I help?"
            mock_message.tool_calls = None

            mock_choice = MagicMock()
            mock_choice.message = mock_message

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_response.usage = mock_usage

            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            provider = OpenAIProvider(config)
            messages = [{"role": "user", "content": "Hi"}]

            results = []
            async for event_type, data in provider.get_response_stream(messages):
                results.append((event_type, data))

            assert len(results) == 2
            assert results[0] == ("final", "Hello, how can I help?")
            assert results[1] == ("usage", {"input_tokens": 50, "output_tokens": 30})

    @pytest.mark.asyncio
    async def test_empty_content_defaults_to_empty_string(self, config):
        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client

            mock_usage = MagicMock()
            mock_usage.prompt_tokens = 5
            mock_usage.completion_tokens = 2

            mock_message = MagicMock()
            mock_message.content = None
            mock_message.tool_calls = None

            mock_choice = MagicMock()
            mock_choice.message = mock_message

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_response.usage = mock_usage

            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            provider = OpenAIProvider(config)
            messages = [{"role": "user", "content": "Hi"}]

            results = []
            async for event_type, data in provider.get_response_stream(messages):
                results.append((event_type, data))

            assert results[0] == ("final", "")

    @pytest.mark.asyncio
    async def test_api_exception_yields_error(self, config):
        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("Rate limit exceeded")
            )

            provider = OpenAIProvider(config)
            messages = [{"role": "user", "content": "Hi"}]

            results = []
            async for event_type, data in provider.get_response_stream(messages):
                results.append((event_type, data))

            assert len(results) == 1
            assert results[0][0] == "final"
            assert results[0][1].startswith("LLM_PROVIDER_ERROR:")
            assert "Rate limit exceeded" in results[0][1]

    @pytest.mark.asyncio
    async def test_tool_call_in_non_streaming_mode(self, config):
        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client

            mock_usage = MagicMock()
            mock_usage.prompt_tokens = 100
            mock_usage.completion_tokens = 50

            mock_tool_call = MagicMock()
            mock_tool_call.id = "call_tool_1"
            mock_tool_call.function.name = "get_weather"
            mock_tool_call.function.arguments = '{"city": "NYC"}'

            mock_message = MagicMock()
            mock_message.content = None
            mock_message.tool_calls = [mock_tool_call]

            mock_choice = MagicMock()
            mock_choice.message = mock_message

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_response.usage = mock_usage

            mock_usage2 = MagicMock()
            mock_usage2.prompt_tokens = 80
            mock_usage2.completion_tokens = 40

            mock_message2 = MagicMock()
            mock_message2.content = "The weather in NYC is sunny."

            mock_choice2 = MagicMock()
            mock_choice2.message = mock_message2

            mock_response2 = MagicMock()
            mock_response2.choices = [mock_choice2]
            mock_response2.usage = mock_usage2

            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_response, mock_response2]
            )

            def get_weather(city):
                return '{"temp": 72, "condition": "sunny"}'

            provider = OpenAIProvider(config)
            messages = [{"role": "user", "content": "What's the weather in NYC?"}]
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather",
                        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
                    },
                }
            ]
            tool_functions = {"get_weather": get_weather}

            results = []
            async for event_type, data in provider.get_response_stream(
                messages, tools=tools, tool_functions=tool_functions
            ):
                results.append((event_type, data))

            assert len(results) == 2
            assert results[0] == ("final", "The weather in NYC is sunny.")
            assert results[1] == ("usage", {"input_tokens": 180, "output_tokens": 90})

    @pytest.mark.asyncio
    async def test_tool_call_execution_error_handled(self, config):
        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client

            mock_usage = MagicMock()
            mock_usage.prompt_tokens = 100
            mock_usage.completion_tokens = 50

            mock_tool_call = MagicMock()
            mock_tool_call.id = "call_tool_err"
            mock_tool_call.function.name = "failing_tool"
            mock_tool_call.function.arguments = '{}'

            mock_message = MagicMock()
            mock_message.content = None
            mock_message.tool_calls = [mock_tool_call]

            mock_choice = MagicMock()
            mock_choice.message = mock_message

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_response.usage = mock_usage

            mock_usage2 = MagicMock()
            mock_usage2.prompt_tokens = 120
            mock_usage2.completion_tokens = 60

            mock_message2 = MagicMock()
            mock_message2.content = "I couldn't run that tool."

            mock_choice2 = MagicMock()
            mock_choice2.message = mock_message2

            mock_response2 = MagicMock()
            mock_response2.choices = [mock_choice2]
            mock_response2.usage = mock_usage2

            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_response, mock_response2]
            )

            def failing_tool():
                raise ValueError("Something went wrong")

            provider = OpenAIProvider(config)
            messages = [{"role": "user", "content": "Run the tool."}]
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "failing_tool",
                        "description": "A tool that fails",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ]
            tool_functions = {"failing_tool": failing_tool}

            results = []
            async for event_type, data in provider.get_response_stream(
                messages, tools=tools, tool_functions=tool_functions
            ):
                results.append((event_type, data))

            assert results[0] == ("final", "I couldn't run that tool.")
            assert results[1] == ("usage", {"input_tokens": 220, "output_tokens": 110})

    @pytest.mark.asyncio
    async def test_no_usage_in_response_yields_no_usage_event(self, config):
        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client

            mock_message = MagicMock()
            mock_message.content = "Response text"
            mock_message.tool_calls = None

            mock_choice = MagicMock()
            mock_choice.message = mock_message

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_response.usage = None

            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            provider = OpenAIProvider(config)
            messages = [{"role": "user", "content": "Hi"}]

            results = []
            async for event_type, data in provider.get_response_stream(messages):
                results.append((event_type, data))

            assert len(results) == 1
            assert results[0] == ("final", "Response text")


class TestGetResponseStreamStreaming:
    @pytest.mark.asyncio
    async def test_streaming_yields_partial_then_final_then_usage(self, config_streaming):
        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client

            chunk1 = MagicMock()
            chunk1.usage = None
            chunk1.choices = [MagicMock()]
            chunk1.choices[0].delta = MagicMock()
            chunk1.choices[0].delta.content = "Hello"
            chunk1.choices[0].delta.tool_calls = None

            chunk2 = MagicMock()
            chunk2.usage = None
            chunk2.choices = [MagicMock()]
            chunk2.choices[0].delta = MagicMock()
            chunk2.choices[0].delta.content = " world"
            chunk2.choices[0].delta.tool_calls = None

            chunk3 = MagicMock()
            chunk3.usage = MagicMock()
            chunk3.usage.prompt_tokens = 20
            chunk3.usage.completion_tokens = 5
            chunk3.choices = [MagicMock()]
            chunk3.choices[0].delta = MagicMock()
            chunk3.choices[0].delta.content = "!"
            chunk3.choices[0].delta.tool_calls = None

            mock_response = _AsyncIter([chunk1, chunk2, chunk3])

            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            provider = OpenAIProvider(config_streaming)
            messages = [{"role": "user", "content": "Hi"}]

            results = []
            async for event_type, data in provider.get_response_stream(messages):
                results.append((event_type, data))

            assert ("partial", "Hello") in results
            assert ("partial", "Hello world") in results
            assert ("partial", "Hello world!") in results
            assert results[-2] == ("final", "Hello world!")
            assert results[-1] == ("usage", {"input_tokens": 20, "output_tokens": 5})

    @pytest.mark.asyncio
    async def test_streaming_with_tool_calls(self, config_streaming):
        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client

            tc_chunk1 = MagicMock()
            tc_chunk1.index = 0
            tc_chunk1.id = "call_abc123"
            tc_chunk1.function = MagicMock()
            tc_chunk1.function.name = "search"
            tc_chunk1.function.arguments = '{"q'

            tc_chunk2 = MagicMock()
            tc_chunk2.index = 0
            tc_chunk2.id = None
            tc_chunk2.function = MagicMock()
            tc_chunk2.function.name = None
            tc_chunk2.function.arguments = 'uery": "test"}'

            chunk1 = MagicMock()
            chunk1.usage = None
            chunk1.choices = [MagicMock()]
            chunk1.choices[0].delta = MagicMock()
            chunk1.choices[0].delta.content = None
            chunk1.choices[0].delta.tool_calls = [tc_chunk1]

            chunk2 = MagicMock()
            chunk2.usage = MagicMock()
            chunk2.usage.prompt_tokens = 100
            chunk2.usage.completion_tokens = 20
            chunk2.choices = [MagicMock()]
            chunk2.choices[0].delta = MagicMock()
            chunk2.choices[0].delta.content = None
            chunk2.choices[0].delta.tool_calls = [tc_chunk2]

            mock_stream_response = _AsyncIter([chunk1, chunk2])

            mock_usage2 = MagicMock()
            mock_usage2.prompt_tokens = 80
            mock_usage2.completion_tokens = 30

            mock_message2 = MagicMock()
            mock_message2.content = "Search results: found test data."

            mock_choice2 = MagicMock()
            mock_choice2.message = mock_message2

            mock_response2 = MagicMock()
            mock_response2.choices = [mock_choice2]
            mock_response2.usage = mock_usage2

            mock_client.chat.completions.create = AsyncMock(
                side_effect=[mock_stream_response, mock_response2]
            )

            def search(query):
                return f"Results for {query}"

            provider = OpenAIProvider(config_streaming)
            messages = [{"role": "user", "content": "Search for test"}]
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "search",
                        "description": "Search",
                        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
                    },
                }
            ]
            tool_functions = {"search": search}

            results = []
            async for event_type, data in provider.get_response_stream(
                messages, tools=tools, tool_functions=tool_functions
            ):
                results.append((event_type, data))

            assert results[0] == ("final", "")
            assert results[1] == ("usage", {"input_tokens": 100, "output_tokens": 20})
            assert results[2] == ("final", "Search results: found test data.")
            assert results[3] == ("usage", {"input_tokens": 180, "output_tokens": 50})

    @pytest.mark.asyncio
    async def test_streaming_api_exception_yields_error(self, config_streaming):
        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("Connection timeout")
            )

            provider = OpenAIProvider(config_streaming)
            messages = [{"role": "user", "content": "Hi"}]

            results = []
            async for event_type, data in provider.get_response_stream(messages):
                results.append((event_type, data))

            assert len(results) == 1
            assert results[0][0] == "final"
            assert results[0][1].startswith("LLM_PROVIDER_ERROR:")
            assert "Connection timeout" in results[0][1]

    @pytest.mark.asyncio
    async def test_streaming_no_usage_yields_no_usage_event(self, config_streaming):
        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client

            chunk = MagicMock()
            chunk.usage = None
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = "Hello"
            chunk.choices[0].delta.tool_calls = None

            mock_response = _AsyncIter([chunk])

            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            provider = OpenAIProvider(config_streaming)
            messages = [{"role": "user", "content": "Hi"}]

            results = []
            async for event_type, data in provider.get_response_stream(messages):
                results.append((event_type, data))

            assert len(results) == 2
            assert results[0] == ("partial", "Hello")
            assert results[1] == ("final", "Hello")

    @pytest.mark.asyncio
    async def test_streaming_empty_delta_content_not_appended(self, config_streaming):
        with patch("openai.AsyncOpenAI") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client

            chunk = MagicMock()
            chunk.usage = MagicMock()
            chunk.usage.prompt_tokens = 10
            chunk.usage.completion_tokens = 0
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = None
            chunk.choices[0].delta.tool_calls = None

            mock_response = _AsyncIter([chunk])

            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            provider = OpenAIProvider(config_streaming)
            messages = [{"role": "user", "content": "Hi"}]

            results = []
            async for event_type, data in provider.get_response_stream(messages):
                results.append((event_type, data))

            assert results[0] == ("final", "")
            assert results[1] == ("usage", {"input_tokens": 10, "output_tokens": 0})
