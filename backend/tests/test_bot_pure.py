import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

pytestmark = [pytest.mark.unit]

from app.bot import (
    strip_thinking_sections,
    strip_dsml_tool_blocks,
    contains_dsml_tool_blocks,
    _parse_user_info_fields,
    process_knowledge_tags,
)


class TestStripThinkingSections:
    def test_empty_string(self):
        assert strip_thinking_sections("") == ""

    def test_no_thinking_tags(self):
        text = "Hello world, this is a normal message."
        assert strip_thinking_sections(text) == text

    def test_single_thinking_block_removed(self):
        text = "Hello <thinking>secret reasoning</thinking> World"
        result = strip_thinking_sections(text)
        assert "secret reasoning" not in result
        assert "Hello" in result
        assert "World" in result

    def test_multiple_thinking_blocks(self):
        text = "<thinking>one</thinking> middle <thinking>two</thinking> end"
        result = strip_thinking_sections(text)
        assert "one" not in result
        assert "two" not in result
        assert "middle" in result
        assert "end" in result

    def test_case_insensitive(self):
        text = "Start <THINKING>hidden</THINKING> End"
        result = strip_thinking_sections(text)
        assert "hidden" not in result
        assert "Start" in result
        assert "End" in result

    def test_multiline_dotall(self):
        text = "Start <thinking>\nsecret\nmultiline\n</thinking> End"
        result = strip_thinking_sections(text)
        assert "secret" not in result
        assert "Start" in result
        assert "End" in result

    def test_only_thinking_returns_empty(self):
        text = "<thinking>only thinking here</thinking>"
        assert strip_thinking_sections(text) == ""

    def test_nested_thinking_non_greedy(self):
        text = "<thinking>outer<thinking>inner</thinking>rest</thinking>"
        result = strip_thinking_sections(text)
        assert "inner" not in result
        assert "outer" not in result
        assert "</thinking>" in result
        assert "rest" in result


class TestStripDsmlToolBlocks:
    def test_empty_string(self):
        assert strip_dsml_tool_blocks("") == ""

    def test_no_dsml_in_text(self):
        text = "Hello world, nothing to strip here."
        assert strip_dsml_tool_blocks(text) == text

    def test_single_function_calls_block_removed(self):
        text = "Hello < | DSML | function_calls >stuff here< / | DSML | function_calls > World"
        result = strip_dsml_tool_blocks(text)
        assert "stuff here" not in result
        assert "Hello" in result
        assert "World" in result

    def test_dsml_line_removed(self):
        text = "keep this\n< | DSML | some_param >value\nkeep that"
        result = strip_dsml_tool_blocks(text)
        assert "keep this" in result
        assert "keep that" in result
        assert "some_param" not in result

    def test_multiple_dsml_blocks_removed(self):
        text = "< | DSML | function_calls >first< / | DSML | function_calls >\nmid\n< | DSML | function_calls >second< / | DSML | function_calls >\nend"
        result = strip_dsml_tool_blocks(text)
        assert "first" not in result
        assert "second" not in result
        assert "mid" in result
        assert "end" in result

    def test_case_insensitive(self):
        text = "Hello < | DSML | FUNCTION_CALLS >stuff< / | DSML | FUNCTION_CALLS > World"
        result = strip_dsml_tool_blocks(text)
        assert "stuff" not in result
        assert "Hello" in result
        assert "World" in result

    def test_inline_dsml_tag_removed(self):
        text = "before < | DSML | invoke | some_func | param=val > after"
        result = strip_dsml_tool_blocks(text)
        assert "some_func" not in result
        assert result == ""

    def test_text_with_only_dsml_returns_empty(self):
        text = "< | DSML | function_calls >only< / | DSML | function_calls >"
        assert strip_dsml_tool_blocks(text) == ""


class TestContainsDsmlToolBlocks:
    def test_empty_string(self):
        assert contains_dsml_tool_blocks("") is False

    def test_no_dsml(self):
        assert contains_dsml_tool_blocks("plain text") is False

    def test_has_function_calls(self):
        assert contains_dsml_tool_blocks("< | DSML | function_calls >stuff") is True

    def test_has_invoke(self):
        assert contains_dsml_tool_blocks("< | DSML | invoke") is True

    def test_has_parameter(self):
        assert contains_dsml_tool_blocks("some <|dsml|parameter>") is True

    def test_case_insensitive_match(self):
        assert contains_dsml_tool_blocks("< | DSML | FUNCTION_CALLS >") is True

    def test_partial_tag_no_match(self):
        assert contains_dsml_tool_blocks("< | DSML | something_else >") is False

    def test_text_near_tag(self):
        assert contains_dsml_tool_blocks("prefix< | DSML | invoke >suffix") is True


class TestParseUserInfoFields:
    def test_empty_string(self):
        assert _parse_user_info_fields("") == {}

    def test_single_id_field(self):
        assert _parse_user_info_fields("id=12345") == {"id": "12345"}

    def test_id_with_semicolons(self):
        assert _parse_user_info_fields("id=12345;keywords=test;content=hello world") == {
            "id": "12345",
            "keywords": "test",
            "content": "hello world",
        }

    def test_keywords_only(self):
        assert _parse_user_info_fields("keywords=alpha") == {"keywords": "alpha"}

    def test_content_takes_rest_of_string(self):
        assert _parse_user_info_fields("content=a;b;c=extra") == {"content": "a;b;c=extra"}

    def test_unknown_key_breaks_parsing(self):
        assert _parse_user_info_fields("id=12345;name=Alice;keywords=test") == {"id": "12345"}

    def test_invalid_first_key_returns_empty(self):
        assert _parse_user_info_fields("name=Alice;id=12345") == {}

    def test_whitespace_trimming(self):
        assert _parse_user_info_fields("  id  =  12345  ;  keywords  =  hello  ") == {
            "id": "12345",
            "keywords": "hello",
        }

    def test_no_equals_sign(self):
        assert _parse_user_info_fields("just text") == {}

    def test_only_semicolons_no_equals(self):
        assert _parse_user_info_fields("a;b;c") == {}

    def test_id_without_semicolon_takes_rest(self):
        assert _parse_user_info_fields("id=12345 extra") == {"id": "12345 extra"}

    def test_value_contains_equals(self):
        assert _parse_user_info_fields("id=key=value;keywords=stuff") == {
            "id": "key=value",
            "keywords": "stuff",
        }


class TestProcessKnowledgeTags:
    @pytest.mark.asyncio
    async def test_empty_text_returns_empty(self):
        mock_message = MagicMock()
        result = await process_knowledge_tags(mock_message, "", {})
        assert result == ""

    @pytest.mark.asyncio
    async def test_no_tags_returns_text_unchanged(self):
        mock_message = MagicMock()
        text = "Hello world, no tags here."
        result = await process_knowledge_tags(mock_message, text, {})
        assert result == text.strip()

    @pytest.mark.asyncio
    async def test_memory_tag_calls_ingest_memory_candidate(self):
        mock_message = MagicMock()
        mock_message.created_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_message.author.id = 111
        mock_message.author.name = "TestUser"
        mock_message.channel.id = 222

        mock_km = MagicMock()
        mock_km.ingest_memory_candidate = MagicMock(return_value={"status": "promoted", "memory_id": "mem-1"})

        text = "Hello <memory>important fact</memory> World"

        with patch(
            "app.bot.get_knowledge_manager", return_value=mock_km
        ):
            result = await process_knowledge_tags(mock_message, text, {})
            mock_km.ingest_memory_candidate.assert_called_once()
            call_kwargs = mock_km.ingest_memory_candidate.call_args.kwargs
            assert call_kwargs["content"] == "important fact"
            assert call_kwargs["user_id"] == "111"
            assert call_kwargs["user_name"] == "TestUser"
            assert call_kwargs["source"] == "ai_tag"
            assert call_kwargs["channel_id"] == "222"

        assert "important fact" not in result
        assert "Hello" in result
        assert "World" in result

    @pytest.mark.asyncio
    async def test_memory_tag_multiple_entries(self):
        mock_message = MagicMock()
        mock_message.created_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_message.author.id = 111
        mock_message.author.name = "TestUser"
        mock_message.channel.id = 222

        mock_km = MagicMock()
        mock_km.ingest_memory_candidate = MagicMock(return_value={"status": "staged", "candidate_id": "c-1"})

        text = "<memory>fact one</memory> mid <memory>fact two</memory>"

        with patch(
            "app.bot.get_knowledge_manager", return_value=mock_km
        ):
            result = await process_knowledge_tags(mock_message, text, {})
            assert mock_km.ingest_memory_candidate.call_count == 2

        assert "fact one" not in result
        assert "fact two" not in result

    @pytest.mark.asyncio
    async def test_memory_tag_skips_empty_content(self):
        mock_message = MagicMock()
        mock_message.created_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_message.author.id = 111
        mock_message.author.name = "TestUser"
        mock_message.channel.id = 222

        mock_km = MagicMock()
        mock_km.ingest_memory_candidate = MagicMock(return_value={"status": "staged"})

        text = "Before <memory>  </memory> After"

        with patch(
            "app.bot.get_knowledge_manager", return_value=mock_km
        ):
            result = await process_knowledge_tags(mock_message, text, {})
            mock_km.ingest_memory_candidate.assert_not_called()

        assert result == "Before  After"

    @pytest.mark.asyncio
    async def test_user_info_tag_adds_world_book_entry(self):
        mock_message = MagicMock()
        mock_message.created_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_message.author.id = 111
        mock_message.author.name = "TestUser"
        mock_message.channel.id = 222
        mock_message.guild = MagicMock()
        mock_message.guild.id = 999

        mock_km = MagicMock()
        mock_km.add_world_book_entry = MagicMock()

        text = "Context <user_info id=12345;keywords=python,code;content=User is a developer></user_info> End"

        with patch(
            "app.bot.get_knowledge_manager", return_value=mock_km
        ), patch(
            "app.core_logic.user_validator.validate_user_id",
            new=AsyncMock(return_value=MagicMock(id=12345, display_name="Dev")),
        ):
            result = await process_knowledge_tags(mock_message, text, {})
            mock_km.add_world_book_entry.assert_called_once()
            call_kwargs = mock_km.add_world_book_entry.call_args.kwargs
            assert call_kwargs["keywords"] == "python,code"
            assert call_kwargs["content"] == "User is a developer>"
            assert call_kwargs["source"] == "ai_tag"

        assert "id=12345" not in result
        assert "Context" in result
        assert "End" in result

    @pytest.mark.asyncio
    async def test_user_info_tag_dm_skips_validation(self):
        mock_message = MagicMock()
        mock_message.created_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_message.author.id = 111
        mock_message.author.name = "DMUser"
        mock_message.channel.id = 222
        mock_message.guild = None

        mock_km = MagicMock()
        mock_km.add_world_book_entry = MagicMock()

        text = "<user_info id=99999;content=Direct message user></user_info> text"

        with patch(
            "app.bot.get_knowledge_manager", return_value=mock_km
        ):
            result = await process_knowledge_tags(mock_message, text, {})
            mock_km.add_world_book_entry.assert_called_once()
            call_kwargs = mock_km.add_world_book_entry.call_args.kwargs
            assert call_kwargs["linked_user_id"] == "99999"

        assert "text" in result

    @pytest.mark.asyncio
    async def test_combined_memory_and_user_info_tags(self):
        mock_message = MagicMock()
        mock_message.created_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_message.author.id = 111
        mock_message.author.name = "TestUser"
        mock_message.channel.id = 222
        mock_message.guild = MagicMock()
        mock_message.guild.id = 999

        mock_km = MagicMock()
        mock_km.ingest_memory_candidate = MagicMock(return_value={"status": "promoted", "memory_id": "m1"})
        mock_km.add_world_book_entry = MagicMock()

        text = "Start <memory>remember this</memory> mid <user_info id=42;content=Profile data></user_info> End"

        with patch(
            "app.bot.get_knowledge_manager", return_value=mock_km
        ), patch(
            "app.core_logic.user_validator.validate_user_id",
            new=AsyncMock(return_value=MagicMock(id=42, display_name="User42")),
        ):
            result = await process_knowledge_tags(mock_message, text, {})
            mock_km.ingest_memory_candidate.assert_called_once()
            mock_km.add_world_book_entry.assert_called_once()

        assert "remember this" not in result
        assert "Profile data" not in result
        assert "Start" in result
        assert "mid" in result
        assert "End" in result

    @pytest.mark.asyncio
    async def test_user_info_tag_empty_parsed_skipped(self):
        mock_message = MagicMock()
        mock_message.created_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_message.author.id = 111
        mock_message.author.name = "TestUser"
        mock_message.channel.id = 222

        mock_km = MagicMock()
        mock_km.add_world_book_entry = MagicMock()

        text = "Before <user_info nofields></user_info> After"

        with patch(
            "app.bot.get_knowledge_manager", return_value=mock_km
        ):
            result = await process_knowledge_tags(mock_message, text, {})
            mock_km.add_world_book_entry.assert_not_called()

        assert result == "Before  After"

    @pytest.mark.asyncio
    async def test_memory_tag_ingest_error_is_caught(self):
        mock_message = MagicMock()
        mock_message.created_at = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_message.author.id = 111
        mock_message.author.name = "TestUser"
        mock_message.channel.id = 222

        mock_km = MagicMock()
        mock_km.ingest_memory_candidate = MagicMock(side_effect=RuntimeError("DB failure"))

        text = "<memory>some content</memory> rest"

        with patch(
            "app.bot.get_knowledge_manager", return_value=mock_km
        ):
            result = await process_knowledge_tags(mock_message, text, {})
            mock_km.ingest_memory_candidate.assert_called_once()

        assert "some content" not in result
        assert "rest" in result
