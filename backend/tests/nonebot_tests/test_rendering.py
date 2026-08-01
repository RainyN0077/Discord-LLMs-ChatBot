from unittest.mock import AsyncMock, MagicMock, patch
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.nonebug]

from nb_plugins.core_llm_bot.rendering import render_streaming_response


async def _make_stream(*items):
    for item in items:
        yield item


class TestRendering:
    @pytest.mark.asyncio
    async def test_partial_sends_initial_message(self):
        runtime = MagicMock()
        runtime.send_message = AsyncMock(return_value="999")
        runtime.edit_message = AsyncMock()
        channel_id = "100"

        gen = _make_stream(("partial", "Hello"))
        full, usage = await render_streaming_response(runtime, channel_id, gen)

        runtime.send_message.assert_called_once_with(
            channel_id="100",
            content="Hello",
            reply_to_message_id=None,
        )

    @pytest.mark.asyncio
    async def test_empty_partial_does_not_send(self):
        runtime = MagicMock()
        runtime.send_message = AsyncMock()
        runtime.edit_message = AsyncMock()
        channel_id = "100"

        gen = _make_stream(("partial", ""))
        full, usage = await render_streaming_response(runtime, channel_id, gen)

        runtime.send_message.assert_not_called()
        runtime.edit_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_subsequent_partials_edit(self):
        runtime = MagicMock()
        runtime.send_message = AsyncMock(return_value="999")
        runtime.edit_message = AsyncMock()
        channel_id = "100"

        gen = _make_stream(("partial", "First"), ("partial", "Second"))
        full, usage = await render_streaming_response(runtime, channel_id, gen)

        runtime.send_message.assert_called_once_with(
            channel_id="100",
            content="First",
            reply_to_message_id=None,
        )
        runtime.edit_message.assert_called_once_with(
            channel_id="100",
            message_id="999",
            content="Second",
        )

    @pytest.mark.asyncio
    async def test_same_content_does_not_re_edit(self):
        runtime = MagicMock()
        runtime.send_message = AsyncMock(return_value="999")
        runtime.edit_message = AsyncMock()
        channel_id = "100"

        gen = _make_stream(("partial", "Same"), ("partial", "Same"))
        full, usage = await render_streaming_response(runtime, channel_id, gen)

        runtime.send_message.assert_called_once()
        runtime.edit_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_edit_failure_is_silent(self):
        runtime = MagicMock()
        runtime.send_message = AsyncMock(return_value="999")
        runtime.edit_message = AsyncMock(side_effect=Exception("API error"))
        channel_id = "100"

        gen = _make_stream(("partial", "First"), ("partial", "Second"))
        full, usage = await render_streaming_response(runtime, channel_id, gen)

        runtime.send_message.assert_called_once()
        runtime.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_final_response_captured(self):
        runtime = MagicMock()
        runtime.send_message = AsyncMock()
        runtime.edit_message = AsyncMock()
        channel_id = "100"

        gen = _make_stream(("final", "The answer is 42"))
        full, usage = await render_streaming_response(runtime, channel_id, gen)

        assert full == "The answer is 42"
        assert usage is None

    @pytest.mark.asyncio
    async def test_usage_data_captured(self):
        runtime = MagicMock()
        runtime.send_message = AsyncMock()
        runtime.edit_message = AsyncMock()
        channel_id = "100"

        usage_info = {"input_tokens": 100, "output_tokens": 50}
        gen = _make_stream(("usage", usage_info))
        full, usage = await render_streaming_response(runtime, channel_id, gen)

        assert full == ""
        assert usage == usage_info

    @pytest.mark.asyncio
    async def test_full_stream_with_partials_and_final(self):
        runtime = MagicMock()
        runtime.send_message = AsyncMock(return_value="888")
        runtime.edit_message = AsyncMock()
        channel_id = "200"

        gen = _make_stream(
            ("partial", "The "),
            ("partial", "The answer "),
            ("partial", "The answer is "),
            ("final", "The answer is 42"),
        )
        full, usage = await render_streaming_response(runtime, channel_id, gen)

        assert full == "The answer is 42"
        assert runtime.send_message.call_count == 1
        assert runtime.edit_message.call_count == 2

    @pytest.mark.asyncio
    async def test_none_final_data(self):
        runtime = MagicMock()
        runtime.send_message = AsyncMock()
        runtime.edit_message = AsyncMock()
        channel_id = "100"

        gen = _make_stream(("final", None))
        full, usage = await render_streaming_response(runtime, channel_id, gen)

        assert full == ""
