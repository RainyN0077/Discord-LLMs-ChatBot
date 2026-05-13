from unittest.mock import MagicMock, patch

import pytest

from plugins.memory_plugin import MemoryPlugin


def _make_plugin():
    return MemoryPlugin({"name": "test_memory_plugin"})


class TestResolveThreshold:
    def test_resolve_threshold_top_level(self):
        plugin = _make_plugin()
        result = plugin._resolve_threshold({"memory_dedup_threshold": 0.5}, "memory_dedup_threshold")
        assert result == 0.5

    def test_resolve_threshold_behavior_legacy(self):
        plugin = _make_plugin()
        result = plugin._resolve_threshold({"behavior": {"memory_dedup_threshold": 0.7}}, "memory_dedup_threshold")
        assert result == 0.7

    def test_resolve_threshold_top_level_takes_priority(self):
        plugin = _make_plugin()
        result = plugin._resolve_threshold(
            {"memory_dedup_threshold": 0.3, "behavior": {"memory_dedup_threshold": 0.7}},
            "memory_dedup_threshold",
        )
        assert result == 0.3

    def test_resolve_threshold_invalid(self):
        plugin = _make_plugin()
        result = plugin._resolve_threshold({"memory_dedup_threshold": "invalid"}, "memory_dedup_threshold")
        assert result == 0.0

    def test_resolve_threshold_clamped(self):
        plugin = _make_plugin()
        assert plugin._resolve_threshold({"memory_dedup_threshold": 1.5}, "memory_dedup_threshold") == 1.0
        assert plugin._resolve_threshold({"memory_dedup_threshold": -0.5}, "memory_dedup_threshold") == 0.0

    def test_resolve_threshold_not_dict(self):
        plugin = _make_plugin()
        result = plugin._resolve_threshold(None, "memory_dedup_threshold")
        assert result == 0.0


class TestNormalizeForCompare:
    def test_normalize_for_compare(self):
        plugin = _make_plugin()
        result = plugin._normalize_for_compare("  Hello   WORLD  ")
        assert result == "hello world"

    def test_normalize_for_compare_empty(self):
        plugin = _make_plugin()
        assert plugin._normalize_for_compare("") == ""
        assert plugin._normalize_for_compare("   ") == ""


class TestStripMemoryTag:
    def test_strip_memory_tag_with_tag(self):
        plugin = _make_plugin()
        result = plugin._strip_memory_tag("[memory timestamp=xxx] actual content")
        assert result == "actual content"

    def test_strip_memory_tag_no_tag(self):
        plugin = _make_plugin()
        result = plugin._strip_memory_tag("regular content")
        assert result == "regular content"

    def test_strip_memory_tag_empty(self):
        plugin = _make_plugin()
        assert plugin._strip_memory_tag("") == ""
        assert plugin._strip_memory_tag(None) == ""


class TestIsDuplicate:
    def test_is_duplicate_exact(self):
        plugin = _make_plugin()
        existing = [{"content": "hello world"}]
        assert plugin._is_duplicate("hello world", existing, 0.9, "content") is True

    def test_is_duplicate_no_threshold(self):
        plugin = _make_plugin()
        existing = [{"content": "hello world"}]
        assert plugin._is_duplicate("hello world", existing, 0.0, "content") is False

    def test_is_duplicate_empty_new(self):
        plugin = _make_plugin()
        existing = [{"content": "hello world"}]
        assert plugin._is_duplicate("", existing, 0.9, "content") is False

    def test_is_duplicate_empty_existing(self):
        plugin = _make_plugin()
        existing = [{"content": ""}]
        assert plugin._is_duplicate("hello world", existing, 0.9, "content") is False

    def test_is_duplicate_not_similar(self):
        plugin = _make_plugin()
        existing = [{"content": "The quick brown fox jumps over the lazy dog"}]
        assert plugin._is_duplicate("Completely different text here", existing, 0.9, "content") is False


class TestGetCleanedStringList:
    def test_get_cleaned_string_list_str(self):
        plugin = _make_plugin()
        result = plugin._get_cleaned_string_list("Alice, Bob, Charlie")
        assert result == ["alice", "bob", "charlie"]

    def test_get_cleaned_string_list_str_chinese_comma(self):
        plugin = _make_plugin()
        result = plugin._get_cleaned_string_list("Alice，Bob，Charlie")
        assert result == ["alice", "bob", "charlie"]

    def test_get_cleaned_string_list_list(self):
        plugin = _make_plugin()
        result = plugin._get_cleaned_string_list([" Alice ", " BOB "])
        assert result == ["alice", "bob"]

    def test_get_cleaned_string_list_empty(self):
        plugin = _make_plugin()
        assert plugin._get_cleaned_string_list(None) == []
        assert plugin._get_cleaned_string_list("") == []
        assert plugin._get_cleaned_string_list([]) == []
