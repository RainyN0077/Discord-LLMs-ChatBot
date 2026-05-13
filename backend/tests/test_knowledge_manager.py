import asyncio
import pytest

pytestmark = [pytest.mark.unit]
from app.core_logic.knowledge_manager import KnowledgeManager


class TestKnowledgeManagerHelpers:
    """Tests for internal helper methods (_strip_tag, _normalize, _tokens, _safe_*, _quality_score)."""

    def test_strip_tag_removes_memory_tag(self, test_db):
        result = test_db._strip_tag('[memory timestamp="2024-01-01T00:00:00Z" source="test" user_name="Tester" user_id="1"] Hello world')
        assert result == "Hello world"

    def test_strip_tag_no_tag_returns_original(self, test_db):
        result = test_db._strip_tag("Hello world")
        assert result == "Hello world"

    def test_strip_tag_empty_input(self, test_db):
        result = test_db._strip_tag("")
        assert result == ""

    def test_normalize_lowercase_and_collapse(self, test_db):
        result = test_db._normalize("[memory ...]   Hello   WORLD  ")
        assert result == "hello world"

    def test_normalize_strips_tag(self, test_db):
        result = test_db._normalize('[memory x="y"] Important fact')
        assert result == "important fact"

    def test_tokens_extracts_words(self, test_db):
        tokens = test_db._tokens("Hello world from Python")
        assert "hello" in tokens
        assert "world" in tokens
        assert "python" in tokens

    def test_tokens_respects_max_tokens(self, test_db):
        text = "one two three four five six seven eight"
        tokens = test_db._tokens(text, max_tokens=4)
        assert len(tokens) <= 4

    def test_tokens_deduplicates(self, test_db):
        tokens = test_db._tokens("hello hello world world")
        assert tokens.count("hello") == 1
        assert tokens.count("world") == 1

    def test_tokens_min_length_two(self, test_db):
        tokens = test_db._tokens("a b c ab cd efgh")
        assert "a" not in tokens
        assert "b" not in tokens
        assert "ab" in tokens

    def test_safe_int_in_range(self, test_db):
        assert test_db._safe_int(5, 10, 0, 100) == 5

    def test_safe_int_clamps_low(self, test_db):
        assert test_db._safe_int(-5, 10, 0, 100) == 0

    def test_safe_int_clamps_high(self, test_db):
        assert test_db._safe_int(200, 10, 0, 100) == 100

    def test_safe_int_invalid_returns_default(self, test_db):
        assert test_db._safe_int("abc", 10, 0, 100) == 10

    def test_safe_float_in_range(self, test_db):
        assert test_db._safe_float(0.5, 1.0, 0.0, 1.0) == 0.5

    def test_safe_float_clamps(self, test_db):
        assert test_db._safe_float(1.5, 0.5, 0.0, 1.0) == 1.0
        assert test_db._safe_float(-0.5, 0.5, 0.0, 1.0) == 0.0

    def test_safe_float_invalid_returns_default(self, test_db):
        assert test_db._safe_float("abc", 0.5, 0.0, 1.0) == 0.5

    def test_safe_bool_true_values(self, test_db):
        assert test_db._safe_bool(True, False) is True
        assert test_db._safe_bool("true", False) is True
        assert test_db._safe_bool("1", False) is True
        assert test_db._safe_bool("yes", False) is True
        assert test_db._safe_bool("on", False) is True

    def test_safe_bool_false_values(self, test_db):
        assert test_db._safe_bool(False, True) is False
        assert test_db._safe_bool("false", True) is False
        assert test_db._safe_bool("0", True) is False

    def test_safe_bool_invalid_returns_default(self, test_db):
        assert test_db._safe_bool("unknown", True) is True
        assert test_db._safe_bool("unknown", False) is False
        assert test_db._safe_bool(42, True) is True

    def test_quality_score_perfect(self, test_db):
        score = test_db._quality_score(
            "A very long and meaningful content string here for testing purposes",
            seen_count=10,
            distinct_users=5,
            p={"auto_memory_min_length": 8, "auto_memory_promote_min_observations": 5, "auto_memory_promote_min_distinct_users": 3},
        )
        assert 0.0 <= score <= 1.0

    def test_quality_score_low_signal(self, test_db):
        score = test_db._quality_score(
            "https://a.co",
            seen_count=10,
            distinct_users=5,
            p={"auto_memory_min_length": 8, "auto_memory_promote_min_observations": 5, "auto_memory_promote_min_distinct_users": 3},
        )
        assert 0.0 <= score <= 1.0
        assert test_db._low_signal("https://a.co") is True

    def test_resolve_policy_with_empty_config(self, test_db):
        policy = test_db._resolve_policy({})
        assert policy["auto_memory_enabled"] is True
        assert policy["auto_memory_min_length"] == 8
        assert policy["auto_memory_recall_top_k"] == 12

    def test_resolve_policy_with_custom_config(self, test_db):
        policy = test_db._resolve_policy({
            "auto_memory_enabled": False,
            "auto_memory_min_length": "20",
            "auto_memory_recall_top_k": 5,
        })
        assert policy["auto_memory_enabled"] is False
        assert policy["auto_memory_min_length"] == 20
        assert policy["auto_memory_recall_top_k"] == 5


class TestMemoryCRUD:
    """Tests for Memory add/get/delete/update operations."""

    def test_add_memory_success(self, test_db):
        memory_id = test_db.add_memory(
            content="User likes coffee",
            timestamp="2024-01-01T00:00:00Z",
            user_id="123",
            user_name="Tester",
            source="test",
        )
        assert memory_id is not None
        assert isinstance(memory_id, int)

    def test_add_memory_duplicate_content_still_allowed(self, test_db):
        """add_memory UNIQUE constraint is on content (includes tag), so same base content with different tag works."""
        first_id = test_db.add_memory(
            content="Same content repeated",
            timestamp="2024-01-01T00:00:00Z",
            user_id="123",
            user_name="Tester",
            source="test",
        )
        second_id = test_db.add_memory(
            content="Same content repeated",
            timestamp="2024-01-02T00:00:00Z",
            user_id="456",
            user_name="Tester2",
            source="test",
        )
        assert first_id is not None
        assert second_id is not None
        assert first_id != second_id

    def test_find_existing_memory_returns_id(self, test_db):
        memory_id = test_db.add_memory(
            content="The sky is blue",
            timestamp="2024-01-01T00:00:00Z",
            user_id="1",
            user_name="User",
            source="test",
        )
        found_id = test_db._find_existing_memory("the sky is blue")
        assert found_id == memory_id

    def test_find_existing_memory_not_found(self, test_db):
        found_id = test_db._find_existing_memory("nonexistent content abcdef")
        assert found_id is None

    def test_get_all_memories_empty(self, test_db):
        memories = test_db.get_all_memories()
        assert isinstance(memories, list)
        assert len(memories) == 0

    def test_get_all_memories_with_data(self, test_db):
        test_db.add_memory(content="Fact A", timestamp="2024-01-01T00:00:00Z", user_id="1", user_name="U1", source="test")
        test_db.add_memory(content="Fact B", timestamp="2024-01-02T00:00:00Z", user_id="2", user_name="U2", source="test")
        memories = test_db.get_all_memories()
        assert len(memories) == 2

    def test_delete_memory_success(self, test_db):
        memory_id = test_db.add_memory(content="To be deleted", timestamp="2024-01-01T00:00:00Z", user_id="1", user_name="U", source="test")
        success = test_db.delete_memory(memory_id)
        assert success is True
        memories = test_db.get_all_memories()
        assert len(memories) == 0

    def test_delete_memory_not_found(self, test_db):
        success = test_db.delete_memory(99999)
        assert success is False

    def test_update_memory_success(self, test_db):
        memory_id = test_db.add_memory(content="Original content", timestamp="2024-01-01T00:00:00Z", user_id="1", user_name="U", source="test")
        success = test_db.update_memory(memory_id, "Updated content")
        assert success is True

        memories = test_db.get_all_memories()
        assert len(memories) == 1
        assert "Updated content" in memories[0]["content"]

    def test_update_memory_not_found(self, test_db):
        success = test_db.update_memory(99999, "New content")
        assert success is False


class TestMemoryCandidates:
    """Tests for memory_candidate operations."""

    def test_get_candidates_empty(self, test_db):
        candidates = test_db.get_memory_candidates()
        assert isinstance(candidates, list)
        assert len(candidates) == 0

    def test_ingest_creates_candidate(self, test_db):
        result = test_db.ingest_memory_candidate(
            content="This is a new memory candidate for testing",
            timestamp="2024-01-01T00:00:00Z",
            user_id="123",
            user_name="Tester",
            source="test",
        )
        assert result["status"] == "staged"
        assert "candidate_id" in result

    def test_ingest_duplicate_existing_memory(self, test_db):
        test_db.add_memory(
            content="Already a full memory",
            timestamp="2024-01-01T00:00:00Z",
            user_id="123",
            user_name="Tester",
            source="test",
        )
        result = test_db.ingest_memory_candidate(
            content="Already a full memory",
            timestamp="2024-01-02T00:00:00Z",
            user_id="456",
            user_name="Tester2",
            source="test",
        )
        assert result["status"] == "duplicate_existing"

    def test_ingest_disabled(self, test_db):
        result = test_db.ingest_memory_candidate(
            content="Some random content here",
            timestamp="2024-01-01T00:00:00Z",
            user_id="123",
            user_name="Tester",
            source="test",
            config={"auto_memory_enabled": False},
        )
        assert result["status"] == "skipped_disabled"

    def test_ingest_too_short(self, test_db):
        result = test_db.ingest_memory_candidate(
            content="Hi",
            timestamp="2024-01-01T00:00:00Z",
            user_id="123",
            user_name="Tester",
            source="test",
            config={"auto_memory_min_length": 100},
        )
        assert result["status"] == "skipped_too_short"

    def test_ingest_low_signal_url(self, test_db):
        result = test_db.ingest_memory_candidate(
            content="https://example.com/page",
            timestamp="2024-01-01T00:00:00Z",
            user_id="123",
            user_name="Tester",
            source="test",
        )
        assert result["status"] == "skipped_low_signal"

    def test_candidate_promote(self, test_db):
        result = test_db.ingest_memory_candidate(
            content="A valuable memory fact that should be promoted",
            timestamp="2024-01-01T00:00:00Z",
            user_id="123",
            user_name="Tester",
            source="test",
            config={"auto_memory_promote_min_observations": 1, "auto_memory_promote_min_distinct_users": 1, "auto_memory_quality_threshold": 0.0},
        )
        assert result["status"] == "promoted"
        assert "memory_id" in result

    def test_delete_candidate(self, test_db):
        result = test_db.ingest_memory_candidate(
            content="Candidate to be deleted later",
            timestamp="2024-01-01T00:00:00Z",
            user_id="123",
            user_name="Tester",
            source="test",
        )
        candidate_id = result.get("candidate_id")
        assert candidate_id is not None

        success = test_db.delete_memory_candidate(candidate_id)
        assert success is True

    def test_delete_candidate_not_found(self, test_db):
        success = test_db.delete_memory_candidate(99999)
        assert success is False


class TestWorldBook:
    """Tests for World Book CRUD operations."""

    def test_add_world_book_entry(self, test_db):
        entry_id = test_db.add_world_book_entry(
            keywords="lore, world",
            content="Important lore about the world",
            linked_user_id="42",
            source="manual",
        )
        assert isinstance(entry_id, int)

    def test_get_all_world_book_empty(self, test_db):
        entries = test_db.get_all_world_book_entries()
        assert entries == []

    def test_get_all_world_book_with_data(self, test_db):
        test_db.add_world_book_entry(keywords="abc", content="First entry", source="manual")
        test_db.add_world_book_entry(keywords="def", content="Second entry", source="manual")
        entries = test_db.get_all_world_book_entries()
        assert len(entries) == 2

    def test_update_world_book_entry(self, test_db):
        entry_id = test_db.add_world_book_entry(keywords="old", content="Old content", source="manual")
        success = test_db.update_world_book_entry(entry_id, keywords="new", content="New content", enabled=True, linked_user_id=None)
        assert success is True

        entries = test_db.get_all_world_book_entries()
        assert entries[0]["keywords"] == "new"
        assert entries[0]["content"] == "New content"

    def test_update_world_book_not_found(self, test_db):
        success = test_db.update_world_book_entry(99999, keywords="x", content="y", enabled=True)
        assert success is False

    def test_delete_world_book_entry(self, test_db):
        entry_id = test_db.add_world_book_entry(keywords="temp", content="Temporary", source="manual")
        success = test_db.delete_world_book_entry(entry_id)
        assert success is True
        assert len(test_db.get_all_world_book_entries()) == 0

    def test_delete_world_book_not_found(self, test_db):
        success = test_db.delete_world_book_entry(99999)
        assert success is False

    def test_get_world_book_entries_for_user(self, test_db):
        test_db.add_world_book_entry(keywords="a", content="Linked to user 10", linked_user_id="10", source="manual")
        test_db.add_world_book_entry(keywords="b", content="Linked to user 20", linked_user_id="20", source="manual")
        test_db.add_world_book_entry(keywords="c", content="Not linked", source="manual")

        entries = test_db.get_world_book_entries_for_user("10")
        assert len(entries) == 1
        assert entries[0]["content"] == "Linked to user 10"


class TestFTS5Search:
    """Tests for FTS5-based memory and world book search."""

    def test_find_world_book_entries_for_text(self, test_db):
        test_db.add_world_book_entry(keywords="coffee, beans", content="The kingdom exports coffee beans.", source="manual")
        test_db.add_world_book_entry(keywords="tea", content="The kingdom also drinks tea.", source="manual")

        results = test_db.find_world_book_entries_for_text("I love coffee in the morning")
        assert len(results) >= 1

    def test_find_world_book_no_match(self, test_db):
        test_db.add_world_book_entry(keywords="dragons", content="Dragons live in the mountains.", source="manual")
        results = test_db.find_world_book_entries_for_text("I enjoy peaceful farming")
        assert results == []

    def test_get_relevant_memories_returns_results(self, test_db):
        test_db.add_memory(content="The capital city is named Eldoria", timestamp="2024-01-01T00:00:00Z", user_id="1", user_name="GM", source="manual")
        test_db.add_memory(content="Dragons are extinct in this realm", timestamp="2024-01-02T00:00:00Z", user_id="1", user_name="GM", source="manual")
        test_db.add_memory(content="The king's name is Arthur", timestamp="2024-01-03T00:00:00Z", user_id="2", user_name="Player", source="manual")

        results = asyncio.run(test_db.get_relevant_memories("capital city name", top_k=5))
        assert isinstance(results, list)

    def test_get_relevant_memories_no_match(self, test_db):
        test_db.add_memory(content="The ocean is deep", timestamp="2024-01-01T00:00:00Z", user_id="1", user_name="U", source="manual")
        results = asyncio.run(test_db.get_relevant_memories("xyzzy foobar nonexistent", top_k=5))
        assert isinstance(results, list)

    def test_memory_search_respects_top_k(self, test_db):
        for i in range(10):
            test_db.add_memory(
                content=f"Keyword test memory number {i}",
                timestamp=f"2024-01-{i+1:02d}T00:00:00Z",
                user_id=str(i),
                user_name=f"User{i}",
                source="manual",
            )

        results = asyncio.run(test_db.get_relevant_memories("keyword test memory", top_k=3, char_limit=10000))
        assert len(results) <= 3
