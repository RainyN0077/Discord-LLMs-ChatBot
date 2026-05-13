import pytest
from datetime import datetime

from app.utils import escape_xml, transform_memories_for_prompt


class TestEscapeXml:
    def test_escape_xml_special_chars(self):
        result = escape_xml('<hello attr="value" attr2=\'val\'>')
        assert result == '&lt;hello attr=&quot;value&quot; attr2=&apos;val&apos;&gt;'

    def test_escape_xml_empty(self):
        assert escape_xml("") == ""

    def test_escape_xml_none(self):
        assert escape_xml(None) == ""

    def test_escape_xml_plain_text(self):
        assert escape_xml("hello world") == "hello world"


class TestTransformMemories:
    def test_transform_memories_with_timestamp(self):
        memories = [
            {
                "content": 'regular content without tag',
                "timestamp": "2024-01-01T00:00:00Z",
            }
        ]
        result = transform_memories_for_prompt(memories, 'UTC')
        assert len(result) == 1
        assert "regular content without tag" in result[0]

    def test_transform_memories_with_tag(self):
        memories = [
            {
                "content": '[memory timestamp="2024-01-01T00:00:00Z" user_name="TestUser"] some content',
            }
        ]
        result = transform_memories_for_prompt(memories, 'UTC')
        assert len(result) == 1
        assert "TestUser" in result[0]
        assert "2024" in result[0]

    def test_transform_memories_without_tag(self):
        memories = [
            {
                "content": "no tags here",
            }
        ]
        result = transform_memories_for_prompt(memories, 'UTC')
        assert len(result) == 1
        assert "no tags here" in result[0]

    def test_transform_memories_invalid_timezone(self):
        memories = [
            {
                "content": '[memory timestamp="2024-01-01T00:00:00Z" user_name="User"] test',
            }
        ]
        result = transform_memories_for_prompt(memories, 'Mars/Somewhere')
        assert len(result) == 1
        assert "User" in result[0]

    def test_transform_memories_empty(self):
        result = transform_memories_for_prompt([], 'UTC')
        assert result == []

    def test_transform_memories_with_timestamp_no_zone(self):
        memories = [
            {
                "content": '[memory timestamp="2024-01-01T00:00:00" user_name="NoZone"] content',
            }
        ]
        result = transform_memories_for_prompt(memories, 'UTC')
        assert len(result) == 1
