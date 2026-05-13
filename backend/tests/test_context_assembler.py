"""Tests for app.handlers.context_assembler — build_full_context."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.utils import Stub, _async_stub


@pytest.fixture
def mock_message(mock_discord_message):
    return mock_discord_message(content="Hello bot!")


@pytest.fixture
def mock_bot(mock_discord_bot):
    return mock_discord_bot


@pytest.fixture
def test_config(test_config_dict):
    return test_config_dict


class TestBuildFullContext:
    @pytest.mark.asyncio
    async def test_returns_6_tuple(self, mock_message, mock_bot, test_config):
        with patch("app.handlers.context_assembler.build_context_history",
                   new=AsyncMock(return_value=([], []))):
            from app.handlers.context_assembler import build_full_context
            cutoffs = {}
            result = await build_full_context(mock_bot, test_config, mock_message, cutoffs)
            assert isinstance(result, tuple)
            assert len(result) == 6

            system_prompt, formatted_content, history_llm, history_msgs, role_name, role_config = result
            assert isinstance(system_prompt, str)
            assert isinstance(formatted_content, str)
            assert isinstance(history_llm, list)
            assert isinstance(history_msgs, list)

    @pytest.mark.asyncio
    async def test_no_guild_handled(self, mock_message, mock_bot, test_config):
        with patch("app.handlers.context_assembler.build_context_history",
                   new=AsyncMock(return_value=([], []))):
            from app.handlers.context_assembler import build_full_context
            msg = Stub(
                content="hi", clean_content="hi",
                author=Stub(id=1, name="X", display_name="X", bot=False),
                channel=Stub(id=1),
                guild=None,
                mentions=[], attachments=[], reference=None,
            )
            cutoffs = {}
            result = await build_full_context(mock_bot, test_config, msg, cutoffs)
            assert len(result) == 6

    @pytest.mark.asyncio
    async def test_includes_bot_nickname(self, mock_message, mock_bot, test_config):
        with patch("app.handlers.context_assembler.build_context_history",
                   new=AsyncMock(return_value=([], []))):
            from app.handlers.context_assembler import build_full_context
            cutoffs = {}
            config = {**test_config, "bot_nickname": "MyTestBot"}
            system_prompt, _, _, _, _, _ = await build_full_context(mock_bot, config, mock_message, cutoffs)
            assert len(system_prompt) > 0

    @pytest.mark.asyncio
    async def test_no_guild_handled(self, mock_message, mock_bot, test_config):
        with patch("app.handlers.context_assembler.build_context_history",
                   new=AsyncMock(return_value=([], []))):
            from app.handlers.context_assembler import build_full_context
            msg = Stub(
                content="hi", clean_content="hi",
                author=Stub(id=1, name="X", display_name="X", bot=False),
                channel=Stub(id=1),
                guild=None,
                mentions=[], attachments=[], reference=None,
            )
            cutoffs = {}
            result = await build_full_context(mock_bot, test_config, msg, cutoffs)
            assert len(result) == 6

    @pytest.mark.asyncio
    async def test_injected_data_passed(self, mock_message, mock_bot, test_config):
        with patch("app.handlers.context_assembler.build_context_history",
                   new=AsyncMock(return_value=([], []))):
            from app.handlers.context_assembler import build_full_context
            cutoffs = {}
            _, formatted, _, _, _, _ = await build_full_context(
                mock_bot, test_config, mock_message, cutoffs,
                injected_data="PLUGIN_DATA_HERE"
            )
            assert "PLUGIN_DATA_HERE" in formatted

    @pytest.mark.asyncio
    async def test_cutoff_timestamp_used(self, mock_message, mock_bot, test_config):
        with patch("app.handlers.context_assembler.build_context_history",
                   new=AsyncMock(return_value=([], []))):
            from app.handlers.context_assembler import build_full_context
            cutoffs = {mock_message.channel.id: datetime(2020, 1, 1)}
            result = await build_full_context(mock_bot, test_config, mock_message, cutoffs)
            assert len(result) == 6

    @pytest.mark.asyncio
    async def test_user_message_in_formatted(self, mock_message, mock_bot, test_config):
        with patch("app.handlers.context_assembler.build_context_history",
                   new=AsyncMock(return_value=([], []))):
            from app.handlers.context_assembler import build_full_context
            cutoffs = {}
            _, formatted, _, _, _, _ = await build_full_context(mock_bot, test_config, mock_message, cutoffs)
            assert "Hello bot!" in formatted
