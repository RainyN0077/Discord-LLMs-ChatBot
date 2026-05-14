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
        bot = MagicMock()
        sent_msg = MagicMock()
        sent_msg.id = 999
        bot.send = AsyncMock(return_value=sent_msg)
        bot.edit_message = AsyncMock()
        event = MagicMock()
        event.channel_id = 100

        gen = _make_stream(("partial", "Hello"))
        full, usage = await render_streaming_response(bot, event, gen)

        bot.send.assert_called_once()
        call_kwargs = bot.send.call_args
        assert call_kwargs[0][1] == "Hello"
        assert call_kwargs[1].get("reply_message") is True

    @pytest.mark.asyncio
    async def test_empty_partial_does_not_send(self):
        bot = MagicMock()
        bot.send = AsyncMock()
        bot.edit_message = AsyncMock()
        event = MagicMock()
        event.channel_id = 100

        gen = _make_stream(("partial", ""))
        full, usage = await render_streaming_response(bot, event, gen)

        bot.send.assert_not_called()
        bot.edit_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_subsequent_partials_edit(self):
        bot = MagicMock()
        sent_msg = MagicMock()
        sent_msg.id = 999
        bot.send = AsyncMock(return_value=sent_msg)
        bot.edit_message = AsyncMock()
        event = MagicMock()
        event.channel_id = 100

        gen = _make_stream(("partial", "First"), ("partial", "Second"))
        full, usage = await render_streaming_response(bot, event, gen)

        bot.send.assert_called_once()
        bot.edit_message.assert_called_once()
        edit_call = bot.edit_message.call_args
        assert edit_call.kwargs["channel_id"] == 100
        assert edit_call.kwargs["message_id"] == 999

    @pytest.mark.asyncio
    async def test_same_content_does_not_re_edit(self):
        bot = MagicMock()
        sent_msg = MagicMock()
        sent_msg.id = 999
        bot.send = AsyncMock(return_value=sent_msg)
        bot.edit_message = AsyncMock()
        event = MagicMock()
        event.channel_id = 100

        gen = _make_stream(("partial", "Same"), ("partial", "Same"))
        full, usage = await render_streaming_response(bot, event, gen)

        bot.send.assert_called_once()
        bot.edit_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_edit_failure_is_silent(self):
        bot = MagicMock()
        sent_msg = MagicMock()
        sent_msg.id = 999
        bot.send = AsyncMock(return_value=sent_msg)
        bot.edit_message = AsyncMock(side_effect=Exception("API error"))
        event = MagicMock()
        event.channel_id = 100

        gen = _make_stream(("partial", "First"), ("partial", "Second"))
        full, usage = await render_streaming_response(bot, event, gen)

        bot.send.assert_called_once()
        bot.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_final_response_captured(self):
        bot = MagicMock()
        bot.send = AsyncMock()
        bot.edit_message = AsyncMock()
        event = MagicMock()
        event.channel_id = 100

        gen = _make_stream(("final", "The answer is 42"))
        full, usage = await render_streaming_response(bot, event, gen)

        assert full == "The answer is 42"
        assert usage is None

    @pytest.mark.asyncio
    async def test_usage_data_captured(self):
        bot = MagicMock()
        bot.send = AsyncMock()
        bot.edit_message = AsyncMock()
        event = MagicMock()
        event.channel_id = 100

        usage_info = {"input_tokens": 100, "output_tokens": 50}
        gen = _make_stream(("usage", usage_info))
        full, usage = await render_streaming_response(bot, event, gen)

        assert full == ""
        assert usage == usage_info

    @pytest.mark.asyncio
    async def test_full_stream_with_partials_and_final(self):
        bot = MagicMock()
        sent_msg = MagicMock()
        sent_msg.id = 888
        bot.send = AsyncMock(return_value=sent_msg)
        bot.edit_message = AsyncMock()
        event = MagicMock()
        event.channel_id = 200

        gen = _make_stream(
            ("partial", "The "),
            ("partial", "The answer "),
            ("partial", "The answer is "),
            ("final", "The answer is 42"),
        )
        full, usage = await render_streaming_response(bot, event, gen)

        assert full == "The answer is 42"
        assert bot.send.call_count == 1
        assert bot.edit_message.call_count == 2

    @pytest.mark.asyncio
    async def test_none_final_data(self):
        bot = MagicMock()
        bot.send = AsyncMock()
        event = MagicMock()
        event.channel_id = 100

        gen = _make_stream(("final", None))
        full, usage = await render_streaming_response(bot, event, gen)

        assert full == ""
