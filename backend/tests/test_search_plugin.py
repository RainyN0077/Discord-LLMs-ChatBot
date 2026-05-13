"""Tests for plugins.search — SearchPlugin formatting and compression."""
import pytest
from app.utils import Stub


@pytest.fixture
def search_config():
    return {
        "enabled": True,
        "name": "SearchPlugin",
        "api_key": "tvly-test-key",
        "trigger_mode": "command",
        "command": "!search",
        "search_depth": "basic",
        "max_results": 3,
        "include_date": True,
        "compression_strategy": "none",
    }


@pytest.fixture
def search_plugin(search_config):
    from plugins.search import SearchPlugin
    plugin = SearchPlugin(search_config)
    # Patch client to avoid real Tavily calls
    plugin.client = None
    return plugin


class TestFormatResults:
    def test_empty_results(self, search_plugin):
        result = search_plugin.format_results({"results": []}, "test query")
        assert "No information found" in result

    def test_basic_formatting(self, search_plugin):
        search_result = {
            "results": [
                {
                    "title": "Test Title",
                    "url": "https://example.com",
                    "content": "This is the content of the search result.",
                }
            ]
        }
        formatted = search_plugin.format_results(search_result, "test")
        assert "Test Title" in formatted
        assert "https://example.com" in formatted
        assert "This is the content" in formatted
        assert "Web Search Results" in formatted

    def test_truncate_strategy(self, search_plugin):
        search_plugin.compression_strategy = "truncate"
        long_content = "x" * 500
        search_result = {
            "results": [
                {"title": "T", "url": "https://x.com", "content": long_content}
            ]
        }
        formatted = search_plugin.format_results(search_result, "test")
        assert "..." in formatted
        assert len(formatted) < len(long_content) + 200

    def test_rag_strategy(self, search_plugin):
        search_plugin.compression_strategy = "rag"
        search_result = {
            "results": [
                {
                    "title": "T",
                    "url": "https://x.com",
                    "content": "Sentence one. Sentence two about Python. Sentence three about testing.",
                }
            ]
        }
        formatted = search_plugin.format_results(search_result, "Python testing")
        assert "Python" in formatted

    def test_with_date(self, search_plugin):
        search_plugin.include_date = True
        search_result = {
            "results": [
                {
                    "title": "Dated",
                    "url": "https://x.com",
                    "content": "Content.",
                    "published_date": "2024-01-15",
                }
            ]
        }
        formatted = search_plugin.format_results(search_result, "test")
        assert "2024-01-15" in formatted

    def test_without_date(self, search_plugin):
        search_plugin.include_date = False
        search_result = {
            "results": [
                {"title": "NoDate", "url": "https://x.com", "content": "Content."}
            ]
        }
        formatted = search_plugin.format_results(search_result, "test")
        assert "Date:" not in formatted

    def test_multiple_results(self, search_plugin):
        search_result = {
            "results": [
                {"title": f"Title {i}", "url": f"https://x{i}.com", "content": f"Content {i}."}
                for i in range(3)
            ]
        }
        formatted = search_plugin.format_results(search_result, "test")
        assert formatted.count("- **") == 3


class TestCompressWithRag:
    def test_empty_content(self, search_plugin):
        result = search_plugin._compress_with_rag("", "query")
        assert "No content" in result

    def test_short_content_preserved(self, search_plugin):
        result = search_plugin._compress_with_rag("Short text.", "short")
        assert "Short text" in result

    def test_long_content_compressed(self, search_plugin):
        long_text = ". ".join([f"Sentence number {i} about various topics" for i in range(30)])
        result = search_plugin._compress_with_rag(long_text, "topics", max_chars=200)
        assert len(result) <= 210
        assert "topics" in result.lower()

    def test_no_relevant_chunks_falls_back(self, search_plugin):
        result = search_plugin._compress_with_rag("Irrelevant text here.", "completely_different", max_chars=50)
        assert len(result) > 0

    def test_small_chunks_handled(self, search_plugin):
        result = search_plugin._compress_with_rag("a b c", "b", max_chars=100)
        assert len(result) > 0


class TestFormatResultsEdgeCases:
    def test_missing_content_field(self, search_plugin):
        search_result = {
            "results": [{"title": "T", "url": "https://x.com"}]
        }
        formatted = search_plugin.format_results(search_result, "test")
        assert "No content" in formatted

    def test_no_results_key(self, search_plugin):
        formatted = search_plugin.format_results({}, "test")
        assert "No information found" in formatted
