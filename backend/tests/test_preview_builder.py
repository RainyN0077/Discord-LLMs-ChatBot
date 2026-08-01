import json
from datetime import datetime, timezone
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


class TestGeneratePreviewRegression:
    """S6/A8：移除 preview_builder 的 'prompt_templates' config 注入后输出不变（模板经显式参数生效）. """

    async def _run_preview(self, bot_config, templates=None):
        from app.models import (
            PromptPreviewRequest, PromptPreviewTemplates, PromptPreviewScenario,
        )
        from app.core_logic.preview_builder import generate_preview
        from app.core_logic import persona_manager as pm_module

        class _FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2024, 1, 1, 12, 0, 0, tzinfo=tz or timezone.utc)

        request = PromptPreviewRequest(
            templates=PromptPreviewTemplates(
                message_format="«{author_id_str}»「{content}」",
                user_request_block="<user_request>\n{parts}\n</user_request>",
                system_prompt_foundation_header="定制基础规则标题",
                operational_instructions=["指令甲", "指令乙"],
            ),
            scenario=PromptPreviewScenario(
                guild_id="100", channel_id="200", user_id="300",
                message_content="Hello world", user_roles=[], image_count=0,
            ),
        )
        with patch.object(pm_module, "datetime", _FixedDatetime):
            return await generate_preview(request, bot_config)

    async def test_preview_output_unchanged_with_or_without_config_key(self):
        """config 含/不含 prompt_templates 键 → 预览输出逐字节一致（证明该注入为死代码）. """
        bot_config = {
            "system_prompt": "基础人设。",
            "role_based_config": {},
            "user_personas": {},
            "scoped_prompts": {"channels": {}, "guilds": {}},
        }
        r_without = await self._run_preview(bot_config)
        r_with = await self._run_preview({**bot_config, "prompt_templates": {"message_format": "X"}})
        assert r_without == r_with

    async def test_preview_templates_still_effective(self):
        """模板仍经显式 templates 参数生效（定制标题/指令/用户消息格式/请求块）. """
        bot_config = {
            "system_prompt": "基础人设。",
            "role_based_config": {},
            "user_personas": {},
            "scoped_prompts": {"channels": {}, "guilds": {}},
        }
        result = await self._run_preview(bot_config)
        assert "[定制基础规则标题]" in result["final_system_prompt"]
        assert "指令甲" in result["final_system_prompt"]
        assert result["final_user_request"].startswith("<user_request>")
        assert "«模拟用户 模拟用户 id：300»「Hello world」" in result["final_user_request"]
