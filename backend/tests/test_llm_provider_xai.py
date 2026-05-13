import pytest

from app.llm_providers.xai_provider import XAIProvider


class TestStringifyContent:
    def test_stringify_content_str(self):
        assert XAIProvider._stringify_content("hello") == "hello"

    def test_stringify_content_list_dict(self):
        content = [{"text": "part1"}, {"text": "part2"}]
        result = XAIProvider._stringify_content(content)
        assert "part1" in result
        assert "part2" in result

    def test_stringify_content_list_dict_fallback_to_content_key(self):
        content = [{"content": "via content key"}]
        result = XAIProvider._stringify_content(content)
        assert "via content key" in result

    def test_stringify_content_non_str(self):
        assert XAIProvider._stringify_content(42) == "42"
        assert XAIProvider._stringify_content(None) == "None"


class TestPrepareTools:
    def test_prepare_tools_returns_list(self):
        tools = [{"function": {"name": "my_func", "description": "Does things", "parameters": {}}}]
        result = XAIProvider._prepare_tools(tools)
        assert result is not None
        assert len(result) == 1

    def test_prepare_tools_empty(self):
        assert XAIProvider._prepare_tools(None) is None
        assert XAIProvider._prepare_tools([]) is None

    def test_prepare_tools_missing_name(self):
        tools = [{"function": {"name": "", "description": "test"}}]
        result = XAIProvider._prepare_tools(tools)
        assert result is None


class TestMergeUsage:
    def test_merge_usage_both(self):
        first = {"input_tokens": 10, "output_tokens": 5}
        second = {"input_tokens": 20, "output_tokens": 10}
        result = XAIProvider._merge_usage(first, second)
        assert result == {"input_tokens": 30, "output_tokens": 15}

    def test_merge_usage_first_only(self):
        first = {"input_tokens": 10, "output_tokens": 5}
        result = XAIProvider._merge_usage(first, None)
        assert result == first

    def test_merge_usage_second_only(self):
        second = {"input_tokens": 20, "output_tokens": 10}
        result = XAIProvider._merge_usage(None, second)
        assert result == second

    def test_merge_usage_none(self):
        result = XAIProvider._merge_usage(None, None)
        assert result is None


class TestToolResultPayload:
    def test_tool_result_payload_str(self):
        assert XAIProvider._tool_result_payload("hello") == "hello"

    def test_tool_result_payload_dict(self):
        result = XAIProvider._tool_result_payload({"key": "value", "num": 42})
        assert '"key"' in result
        assert '"value"' in result

    def test_tool_result_payload_non_serializable(self):
        obj = object()
        result = XAIProvider._tool_result_payload(obj)
        assert isinstance(result, str)
