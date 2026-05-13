import json
from unittest.mock import MagicMock, patch

import pytest

from app.core_logic.preview_builder import ConstructionLog, _create_mock_objects


class TestConstructionLog:
    def test_construction_log_add(self):
        log = ConstructionLog()
        log.add("entry 1")
        log.add("entry 2", indent=1)
        result = log.get_log()
        assert len(result) == 2
        assert result[0] == "entry 1"
        assert result[1] == "  entry 2"

    def test_construction_log_indent(self):
        log = ConstructionLog()
        log.add("level 0")
        log.add("level 2", indent=2)
        assert log.get_log() == ["level 0", "    level 2"]

    def test_construction_log_get_log(self):
        log = ConstructionLog()
        log.add("a")
        log.add("b")
        assert log.get_log() == ["a", "b"]

    def test_construction_log_empty(self):
        log = ConstructionLog()
        assert log.get_log() == []


class TestCreateMockObjects:
    def test_create_mock_objects_basic(self):
        scenario = {
            "guild_id": "100",
            "channel_id": "200",
            "user_id": "300",
            "message_content": "Hello world",
        }
        bot_config = {"role_based_config": {}}
        mock_message, log = _create_mock_objects(scenario, bot_config)
        assert mock_message.content == "Hello world"
        assert mock_message.author.id == 300
        assert mock_message.channel.id == 200
        assert mock_message.guild.id == 100
        assert len(log.get_log()) > 0

    def test_create_mock_objects_with_reply(self):
        scenario = {
            "guild_id": "100",
            "channel_id": "200",
            "user_id": "300",
            "message_content": "reply text",
            "is_reply": True,
            "replied_message": {
                "author_id": "400",
                "content": "original message",
            },
        }
        bot_config = {"role_based_config": {}}
        mock_message, log = _create_mock_objects(scenario, bot_config)
        assert mock_message.reference is not None
        assert mock_message.reference.resolved.clean_content is not None

    def test_create_mock_objects_with_image(self):
        scenario = {
            "guild_id": "100",
            "channel_id": "200",
            "user_id": "300",
            "message_content": "look at this",
            "image_count": 3,
        }
        bot_config = {"role_based_config": {}}
        mock_message, log = _create_mock_objects(scenario, bot_config)
        assert len(mock_message.attachments) == 3
        assert mock_message.attachments[0].content_type == "image/png"

    def test_create_mock_objects_with_roles(self):
        scenario = {
            "guild_id": "100",
            "channel_id": "200",
            "user_id": "300",
            "message_content": "hello",
            "user_roles": ["12345"],
        }
        bot_config = {"role_based_config": {"12345": {"title": "Admin", "prompt": ""}}}
        mock_message, log = _create_mock_objects(scenario, bot_config)
        assert len(mock_message.author.roles) == 1
        assert mock_message.author.roles[0].name == "Admin"

    def test_create_mock_objects_with_mention(self):
        scenario = {
            "guild_id": "100",
            "channel_id": "200",
            "user_id": "300",
            "message_content": "Hey @张三, check this",
        }
        bot_config = {"role_based_config": {}}
        mock_message, log = _create_mock_objects(scenario, bot_config)
        assert len(mock_message.mentions) == 1
        assert mock_message.mentions[0].name == "张三"
