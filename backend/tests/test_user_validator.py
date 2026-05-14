import pytest
from unittest.mock import MagicMock, AsyncMock

import discord

pytestmark = [pytest.mark.unit]

from app.core_logic.user_validator import validate_user_id, resolve_user_identity


class TestValidateUserId:
    @pytest.mark.asyncio
    async def test_invalid_user_id_returns_none(self):
        guild = MagicMock(spec=discord.Guild)
        result = await validate_user_id("not_a_number", guild)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_member_finds_member_returns_it(self):
        member = MagicMock(spec=discord.Member)
        guild = MagicMock(spec=discord.Guild)
        guild.get_member.return_value = member

        result = await validate_user_id("123", guild)

        guild.get_member.assert_called_once_with(123)
        assert result is member

    @pytest.mark.asyncio
    async def test_get_member_none_fetch_member_succeeds(self):
        fetched = MagicMock(spec=discord.Member)
        guild = MagicMock(spec=discord.Guild)
        guild.get_member.return_value = None
        guild.fetch_member = AsyncMock(return_value=fetched)

        result = await validate_user_id("456", guild)

        guild.get_member.assert_called_once_with(456)
        guild.fetch_member.assert_awaited_once_with(456)
        assert result is fetched

    @pytest.mark.asyncio
    async def test_fetch_member_raises_not_found_returns_none(self):
        guild = MagicMock(spec=discord.Guild)
        guild.get_member.return_value = None
        guild.fetch_member = AsyncMock(side_effect=discord.errors.NotFound(MagicMock(), "not found"))

        result = await validate_user_id("789", guild)

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_member_raises_http_exception_returns_none(self):
        guild = MagicMock(spec=discord.Guild)
        guild.get_member.return_value = None
        guild.fetch_member = AsyncMock(side_effect=discord.errors.HTTPException(MagicMock(), "http error"))

        result = await validate_user_id("100", guild)

        assert result is None


class TestResolveUserIdentity:
    def test_persona_with_matching_id_and_nickname_returns_nickname(self):
        personas = {"p1": {"id": "42", "nickname": "Ali"}}
        result = resolve_user_identity("42", personas)
        assert result == "Ali"

    def test_persona_with_matching_id_no_nickname_falls_through_to_guild(self):
        member = MagicMock(spec=discord.Member)
        member.display_name = "Bob"
        guild = MagicMock(spec=discord.Guild)
        guild.get_member.return_value = member

        personas = {"p1": {"id": "42"}}
        result = resolve_user_identity("42", personas, guild)

        assert result == "Bob"

    def test_no_persona_match_guild_has_member_returns_display_name(self):
        member = MagicMock(spec=discord.Member)
        member.display_name = "Charlie"
        guild = MagicMock(spec=discord.Guild)
        guild.get_member.return_value = member

        result = resolve_user_identity("1", personas={}, guild=guild)

        guild.get_member.assert_called_once_with(1)
        assert result == "Charlie"

    def test_no_persona_match_no_guild_returns_user_format(self):
        result = resolve_user_identity("123", personas={})
        assert result == "User(123)"

    def test_invalid_user_id_in_guild_path_returns_user_format(self):
        guild = MagicMock(spec=discord.Guild)
        result = resolve_user_identity("abc", personas={}, guild=guild)
        assert result == "User(abc)"

    def test_persona_nickname_takes_priority_over_guild_display_name(self):
        member = MagicMock(spec=discord.Member)
        member.display_name = "Bob"
        guild = MagicMock(spec=discord.Guild)
        guild.get_member.return_value = member

        personas = {"p1": {"id": "42", "nickname": "Ali"}}
        result = resolve_user_identity("42", personas, guild)

        assert result == "Ali"
