from unittest.mock import MagicMock, PropertyMock

import pytest

from app.llm_providers.google_provider import GoogleProvider


class FakeTextResponse:
    text = "Hello from text attribute"


class FakeCandidateContent:
    text = "Hello from candidate"


class FakeContent:
    parts = [FakeCandidateContent()]


class FakeCandidate:
    content = FakeContent()


class FakeCandidatesResponse:
    text = ""
    candidates = [FakeCandidate()]


class FakeUsageMetadata:
    prompt_token_count = 100
    candidates_token_count = 50


class FakeResponseWithUsage:
    usage_metadata = FakeUsageMetadata()


class FakeResponseWithoutUsage:
    pass


class FakeFunctionCall:
    name = "test_func"
    args = {"arg1": "value1"}


class FakeResponseWithFunctionCalls:
    function_calls = [FakeFunctionCall()]


class FakeResponseWithoutFunctionCalls:
    pass


class TestExtractTextFromResponse:
    def test_extract_text_from_response_text_attr(self):
        result = GoogleProvider._extract_text_from_response(FakeTextResponse())
        assert result == "Hello from text attribute"

    def test_extract_text_from_response_candidates(self):
        result = GoogleProvider._extract_text_from_response(FakeCandidatesResponse())
        assert result == "Hello from candidate"

    def test_extract_text_from_response_empty(self):
        empty = MagicMock()
        type(empty).text = PropertyMock(side_effect=Exception("no text"))
        type(empty).candidates = PropertyMock(return_value=[])
        result = GoogleProvider._extract_text_from_response(empty)
        assert result == ""


class TestExtractUsage:
    def test_extract_usage_returns_dict(self):
        result = GoogleProvider._extract_usage(FakeResponseWithUsage())
        assert result == {"input_tokens": 100, "output_tokens": 50}

    def test_extract_usage_none(self):
        result = GoogleProvider._extract_usage(FakeResponseWithoutUsage())
        assert result is None


class TestStringifyContent:
    def test_stringify_content_str(self):
        assert GoogleProvider._stringify_content("hello") == "hello"

    def test_stringify_content_list_dict(self):
        content = [{"text": "part1"}, {"text": "part2"}]
        result = GoogleProvider._stringify_content(content)
        assert "part1" in result
        assert "part2" in result

    def test_stringify_content_list_mixed(self):
        content = [{"text": "a"}, "b", 123]
        result = GoogleProvider._stringify_content(content)
        assert "a" in result
        assert "b" in result
        assert "123" in result

    def test_stringify_content_other_type(self):
        assert GoogleProvider._stringify_content(42) == "42"


class TestPrepareTools:
    def test_prepare_tools_returns_list(self):
        tools = [{"function": {"name": "my_func", "description": "Does things", "parameters": {}}}]
        result = GoogleProvider._prepare_tools(tools)
        assert result is not None
        assert len(result) == 1

    def test_prepare_tools_empty(self):
        assert GoogleProvider._prepare_tools(None) is None
        assert GoogleProvider._prepare_tools([]) is None

    def test_prepare_tools_missing_name(self):
        tools = [{"function": {"name": "", "description": "test"}}]
        result = GoogleProvider._prepare_tools(tools)
        assert result is None


class TestExtractFunctionCalls:
    def test_extract_function_calls_returns_list(self):
        result = GoogleProvider._extract_function_calls(FakeResponseWithFunctionCalls())
        assert len(result) == 1

    def test_extract_function_calls_none(self):
        result = GoogleProvider._extract_function_calls(FakeResponseWithoutFunctionCalls())
        assert result == []
