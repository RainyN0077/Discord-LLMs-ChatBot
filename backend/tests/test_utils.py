import pytest

pytestmark = [pytest.mark.unit]
from app.utils import (
    Stub,
    _async_stub,
    _safe_text,
    _json_safe,
    _safe_str_list,
    _safe_dict_list,
    split_message,
    escape_content,
    matches_trigger_keywords,
    TokenCalculator,
)

class TestStub:
    def test_attribute_assignment(self):
        obj = Stub(a=1, b="hello", c=[1, 2, 3])
        assert obj.a == 1
        assert obj.b == "hello"
        assert obj.c == [1, 2, 3]

    def test_nested_stub(self):
        inner = Stub(x=10)
        outer = Stub(child=inner, name="parent")
        assert outer.name == "parent"
        assert outer.child.x == 10

    def test_empty_stub(self):
        obj = Stub()
        assert not hasattr(obj, "nonexistent") or getattr(obj, "nonexistent", None) is None

    def test_dynamic_attr(self):
        obj = Stub()
        obj.new_attr = 42
        assert obj.new_attr == 42


@pytest.mark.asyncio
class TestAsyncStub:
    async def test_returns_value(self):
        fn = _async_stub("result")
        result = await fn()
        assert result == "result"

    async def test_returns_none(self):
        fn = _async_stub()
        result = await fn()
        assert result is None

    async def test_ignores_args(self):
        fn = _async_stub(42)
        result = await fn("ignored", keyword="also_ignored")
        assert result == 42


class TestSafeText:
    def test_none_returns_empty(self):
        assert _safe_text(None) == ""

    def test_string_returns_unchanged(self):
        assert _safe_text("hello") == "hello"

    def test_non_ascii_replaced(self):
        result = _safe_text("hello \udce2world")
        assert "hello" in result
        assert isinstance(result, str)

    def test_bytes_representation(self):
        result = _safe_text(b"hello")
        assert "hello" in result

    def test_int_converted(self):
        assert _safe_text(42) == "42"


class TestJsonSafe:
    def test_none_returns_none(self):
        assert _json_safe(None) is None

    def test_primitives_unchanged(self):
        assert _json_safe("hello") == "hello"
        assert _json_safe(42) == 42
        assert _json_safe(3.14) == 3.14
        assert _json_safe(True) is True

    def test_nested_dict_cleaned(self):
        data = {"key": "val", "nested": {"inner": "x"}}
        assert _json_safe(data) == {"key": "val", "nested": {"inner": "x"}}

    def test_list_cleaned(self):
        data = [1, "two", {"three": 3}]
        assert _json_safe(data) == [1, "two", {"three": 3}]

    def test_tuple_cleaned(self):
        data = (1, 2, 3)
        assert _json_safe(data) == [1, 2, 3]

    def test_set_cleaned(self):
        data = {1, 2}
        result = _json_safe(data)
        assert isinstance(result, list)
        assert sorted(result) == [1, 2]

    def test_non_serializable_value(self):
        import re
        pattern = re.compile(r"\d+")
        result = _json_safe(pattern)
        assert isinstance(result, str)

    def test_non_ascii_keys(self):
        data = {"\u952e": "\u503c"}
        result = _json_safe(data)
        assert "\u952e" in result
        assert result["\u952e"] == "\u503c"


class TestSafeStrList:
    def test_none_returns_empty(self):
        assert _safe_str_list(None) == []

    def test_string_returns_empty(self):
        assert _safe_str_list("not a list") == []

    def test_list_of_strings(self):
        assert _safe_str_list(["a", "b", "c"]) == ["a", "b", "c"]

    def test_mixed_types(self):
        result = _safe_str_list([1, "two", 3.0])
        assert result == ["1", "two", "3.0"]

    def test_tuple(self):
        result = _safe_str_list(("a", "b"))
        assert result == ["a", "b"]


class TestSafeDictList:
    def test_none_returns_empty(self):
        assert _safe_dict_list(None) == []

    def test_list_of_scalars_returns_wrapped_dicts(self):
        result = _safe_dict_list([1, 2, 3])
        assert result == [{"_value": 1}, {"_value": 2}, {"_value": 3}]

    def test_list_of_dicts(self):
        result = _safe_dict_list([{"a": 1}, {"b": 2}])
        assert result == [{"a": 1}, {"b": 2}]

    def test_mixed_dicts_and_scalars(self):
        result = _safe_dict_list([{"a": 1}, 42, {"b": 2}])
        assert result == [{"a": 1}, {"_value": 42}, {"b": 2}]


class TestSplitMessage:
    def test_empty_returns_empty(self):
        assert split_message("") == []

    def test_none_returns_empty(self):
        assert split_message(None) == []

    def test_short_message_no_split(self):
        result = split_message("Hello world")
        assert result == ["Hello world"]

    def test_exact_boundary(self):
        text = "A" * 2000
        result = split_message(text)
        assert len(result) == 1
        assert result[0] == text

    def test_splits_on_newline(self):
        text = "A" * 1500 + "\n" + "B" * 1500
        result = split_message(text)
        assert len(result) == 2

    def test_splits_on_space(self):
        text = "A" * 1500 + " " + "B" * 1500
        result = split_message(text)
        assert len(result) == 2

    def test_hard_cut_when_no_break(self):
        text = "A" * 3000
        result = split_message(text)
        assert len(result) >= 2
        combined = "".join(result)
        assert combined.startswith("A" * 3000) or len(combined) >= 3000

    def test_custom_max_length(self):
        text = "Hello world, this is a test message for splitting"
        result = split_message(text, max_length=20)
        for part in result:
            assert len(part) <= 20


class TestEscapeContent:
    def test_brackets_escaped(self):
        assert escape_content("[test]") == "&#91;test&#93;"

    def test_no_brackets_unchanged(self):
        assert escape_content("hello world") == "hello world"


class TestMatchesTriggerKeywords:
    def test_empty_content_returns_false(self):
        assert matches_trigger_keywords("", ["hello"]) is False

    def test_empty_keywords_returns_false(self):
        assert matches_trigger_keywords("hello", []) is False

    def test_empty_string_content_returns_false(self):
        assert matches_trigger_keywords("", []) is False

    def test_contains_mode_match(self):
        assert matches_trigger_keywords("hello world", ["hello"]) is True

    def test_contains_mode_no_match(self):
        assert matches_trigger_keywords("goodbye world", ["hello"]) is False

    def test_starts_with_mode_match(self):
        assert matches_trigger_keywords("hello world", ["hello"], match_mode="starts_with") is True

    def test_starts_with_mode_no_match(self):
        assert matches_trigger_keywords("world hello", ["hello"], match_mode="starts_with") is False

    def test_exact_mode_match(self):
        assert matches_trigger_keywords("hello", ["hello"], match_mode="exact") is True

    def test_exact_mode_no_match(self):
        assert matches_trigger_keywords("hello world", ["hello"], match_mode="exact") is False

    def test_regex_mode_match(self):
        assert matches_trigger_keywords("abc123", [r"\d+"], match_mode="regex") is True

    def test_regex_mode_no_match(self):
        assert matches_trigger_keywords("abc", [r"\d+"], match_mode="regex") is False

    def test_case_sensitive_match(self):
        assert matches_trigger_keywords("Hello", ["hello"], case_sensitive=True) is False

    def test_case_sensitive_no_match(self):
        assert matches_trigger_keywords("hello", ["Hello"], case_sensitive=True) is False

    def test_case_insensitive_default(self):
        assert matches_trigger_keywords("HELLO world", ["hello"]) is True

    def test_skips_empty_keyword_string(self):
        assert matches_trigger_keywords("hello world", [""]) is False

    def test_skips_whitespace_only_keyword(self):
        assert matches_trigger_keywords("hello world", ["   "]) is False

    def test_multiple_keywords_first_matches(self):
        assert matches_trigger_keywords("hello world", ["goodbye", "hello", "test"]) is True

    def test_invalid_regex_logged(self, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        result = matches_trigger_keywords("hello", ["[invalid"], match_mode="regex")
        assert result is False
        assert len(caplog.records) >= 1

    def test_default_mode_is_contains(self):
        assert matches_trigger_keywords("test hello world", ["hello"]) is True


class TestTokenCalculator:
    def setup_method(self):
        self.calc = TokenCalculator()

    def test_empty_messages_returns_zero(self):
        result = self.calc.get_token_count_for_messages([], "openai", "gpt-4o")
        assert result == 0

    def test_empty_text_returns_zero(self):
        result = self.calc.get_token_count("", "openai", "gpt-4o")
        assert result == 0

    def test_openai_provider_returns_int(self):
        result = self.calc.get_token_count("Hello world", "openai", "gpt-4o")
        assert isinstance(result, int)
        assert result > 0

    def test_grok_provider_uses_openai_tokenizer(self):
        result = self.calc.get_token_count("Hello world", "grok", "grok-2")
        assert isinstance(result, int)
        assert result > 0

    def test_google_provider_returns_estimate(self):
        result = self.calc.get_token_count("Hello world", "google", "gemini-pro")
        assert isinstance(result, int)
        assert result > 0

    def test_unknown_provider_fallback(self):
        result = self.calc.get_token_count("Hello world", "unknown_provider", "unknown_model")
        assert isinstance(result, int)
        assert result > 0

    def test_get_token_count_for_messages_openai(self):
        messages = [{"role": "user", "content": "Hello world"}]
        result = self.calc.get_token_count_for_messages(messages, "openai", "gpt-4o")
        assert isinstance(result, int)
        assert result > 0

    def test_get_token_count_for_messages_anthropic(self):
        messages = [{"role": "user", "content": "Hello world"}]
        result = self.calc.get_token_count_for_messages(messages, "anthropic", "claude-3-opus")
        assert isinstance(result, int)
        assert result > 0

    def test_openai_model_not_found_fallback(self):
        result = self.calc.get_token_count("Hello world", "openai", "non-existent-model-xyz")
        assert isinstance(result, int)
        assert result > 0

    def test_exception_fallback_returns_len(self):
        result = self.calc.get_token_count("test " * 100, "unknown", "unknown")
        assert isinstance(result, int)
        assert result > 0

    def test_anthropic_client_available_or_fallback(self):
        result = self.calc.get_token_count("Hello world", "anthropic", "claude-3-haiku")
        assert isinstance(result, int)
        assert result > 0


class TestIsInternalUrl:
    """Tests for SSRF protection in _is_internal_url."""
    @pytest.mark.asyncio
    async def test_localhost_is_internal(self):
        from app.utils import _is_internal_url
        is_blocked, ips, hostname = await _is_internal_url("http://localhost:8080/api")
        assert is_blocked is True

    @pytest.mark.asyncio
    async def test_loopback_is_internal(self):
        from app.utils import _is_internal_url
        is_blocked, ips, hostname = await _is_internal_url("http://127.0.0.1:3000")
        assert is_blocked is True

    @pytest.mark.asyncio
    async def test_private_10_is_internal(self):
        from app.utils import _is_internal_url
        is_blocked, ips, hostname = await _is_internal_url("http://10.0.0.1/api")
        assert is_blocked is True

    @pytest.mark.asyncio
    async def test_private_192_168_is_internal(self):
        from app.utils import _is_internal_url
        is_blocked, ips, hostname = await _is_internal_url("http://192.168.1.1")
        assert is_blocked is True

    @pytest.mark.asyncio
    async def test_public_url_is_not_internal(self):
        from app.utils import _is_internal_url
        from unittest.mock import patch
        with patch("socket.getaddrinfo", return_value=[(None, None, 0, "", ("93.184.216.34", 0))]):
            is_blocked, ips, hostname = await _is_internal_url("https://example.com")
            assert is_blocked is False

    @pytest.mark.asyncio
    async def test_invalid_url_is_blocked(self):
        from app.utils import _is_internal_url
        is_blocked, ips, hostname = await _is_internal_url("")
        assert is_blocked is True
        is_blocked, ips, hostname = await _is_internal_url("not-a-valid-url")
        assert is_blocked is True