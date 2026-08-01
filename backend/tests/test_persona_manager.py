import pytest

pytestmark = [pytest.mark.unit]
from unittest.mock import MagicMock
from app.utils import Stub
from app.core_logic.persona_manager import (
    get_highest_configured_role,
    get_rich_identity,
    determine_bot_persona,
    find_mentioned_users_by_keywords,
)
from app.core_logic import persona_manager as pm_module
from app.core_logic.persona_manager import build_system_prompt
from datetime import datetime, timezone


class TestGetHighestConfiguredRole:
    def test_empty_role_list_returns_none(self):
        result = get_highest_configured_role([], {"role_a": {"id": "999"}})
        assert result is None

    def test_role_not_configured(self):
        result = get_highest_configured_role(["111"], {"role_b": {"id": "222"}})
        assert result is None

    def test_matching_role_returns_config(self):
        role_configs = {
            "mod_cfg": {"id": "222", "title": "Mod", "prompt": "You are a mod."},
        }
        result = get_highest_configured_role(["111", "222"], role_configs)
        assert result is not None
        assert result[1]["title"] == "Mod"

    def test_highest_role_takes_priority(self):
        role_configs = {
            "owner_cfg": {"id": "999", "title": "Owner", "prompt": "Owner prompt"},
            "member_cfg": {"id": "111", "title": "Member", "prompt": "Member prompt"},
        }
        result = get_highest_configured_role(["111", "999"], role_configs)
        assert result is not None
        assert result[1]["title"] == "Owner"

    def test_non_list_input_returns_none(self):
        result = get_highest_configured_role([], {})
        assert result is None

    def test_empty_role_configs(self):
        result = get_highest_configured_role(["111"], {})
        assert result is None


class TestGetRichIdentity:
    def test_bot_user_returns_display_name(self):
        author = Stub(id=999, display_name="BotName", bot=True)
        result = get_rich_identity(author, {}, None)
        assert result == "BotName"

    def test_role_title_priority(self):
        author = Stub(id=123, display_name="User123", bot=False)
        role_config = {"title": "The Admin"}
        result = get_rich_identity(author, {}, role_config)
        assert result == "The Admin"

    def test_fallback_to_display_name(self):
        author = Stub(id=123, display_name="User123", bot=False)
        result = get_rich_identity(author, {}, None)
        assert result == "User123"

    def test_persona_info_ignored_for_display(self):
        author = Stub(id=42, display_name="Alice", bot=False)
        personas = {"p1": {"id": "42", "nickname": "Ali"}}
        result = get_rich_identity(author, personas, None)
        assert result == "Alice"


class TestDetermineBotPersona:
    def test_no_scoped_prompts_returns_empty(self):
        config = {"scoped_prompts": {"guilds": {}, "channels": {}}}
        persona, situational, log = determine_bot_persona(config, "ch1", "g1", None, None)
        assert persona == ""
        assert situational == ""

    def test_channel_override_takes_priority(self):
        config = {
            "scoped_prompts": {
                "guilds": {"g1": {"id": "1", "enabled": True, "mode": "override", "prompt": "Guild override"}},
                "channels": {"ch1": {"id": "2", "enabled": True, "mode": "override", "prompt": "Channel override"}},
            }
        }
        persona, situational, log = determine_bot_persona(config, "ch1", "g1", None, None)
        assert persona == "Channel override"
        assert len(log) == 1

    def test_guild_override_fallback(self):
        config = {
            "scoped_prompts": {
                "guilds": {"g1": {"id": "1", "enabled": True, "mode": "override", "prompt": "Guild override"}},
                "channels": {},
            }
        }
        persona, situational, log = determine_bot_persona(config, "ch1", "g1", None, None)
        assert persona == "Guild override"

    def test_role_config_fallback(self):
        config = {"scoped_prompts": {"guilds": {}, "channels": {}}}
        role_config = {"prompt": "Role prompt"}
        persona, situational, log = determine_bot_persona(config, "ch1", "g1", "Leader", role_config)
        assert persona == "Role prompt"

    def test_channel_append(self):
        config = {
            "scoped_prompts": {
                "guilds": {},
                "channels": {"ch1": {"id": "2", "enabled": True, "mode": "append", "prompt": "Channel context"}},
            }
        }
        persona, situational, log = determine_bot_persona(config, "ch1", "g1", None, None)
        assert persona == ""
        assert situational == "Channel context"

    def test_guild_append(self):
        config = {
            "scoped_prompts": {
                "guilds": {"g1": {"id": "1", "enabled": True, "mode": "append", "prompt": "Guild context"}},
                "channels": {},
            }
        }
        persona, situational, log = determine_bot_persona(config, "ch1", "g1", None, None)
        assert situational == "Guild context"

    def test_disabled_scoped_prompt_ignored(self):
        config = {
            "scoped_prompts": {
                "guilds": {"g1": {"id": "1", "enabled": False, "mode": "override", "prompt": "Should not appear"}},
                "channels": {},
            }
        }
        persona, situational, _ = determine_bot_persona(config, "ch1", "g1", None, None)
        assert persona == ""

    def test_combined_override_and_append(self):
        config = {
            "scoped_prompts": {
                "guilds": {},
                "channels": {
                    "ch1": {"id": "1", "enabled": True, "mode": "override", "prompt": "Persona"},
                    "ch2": {"id": "2", "enabled": True, "mode": "append", "prompt": "Situation"},
                },
            }
        }
        persona, situational, log = determine_bot_persona(config, "ch1", "g1", None, None)
        assert persona == "Persona"
        assert situational == ""


class TestFindMentionedUsersByKeywords:
    def test_empty_text_returns_empty(self):
        personas = {"p1": {"id": "1", "trigger_keywords": ["alice"]}}
        result = find_mentioned_users_by_keywords("", personas)
        assert result == set()

    def test_empty_personas_returns_empty(self):
        result = find_mentioned_users_by_keywords("hello alice", {})
        assert result == set()

    def test_keyword_match_finds_user(self):
        personas = {"p1": {"id": "42", "trigger_keywords": ["alice", "wonderland"]}}
        result = find_mentioned_users_by_keywords("Hello alice, how are you?", personas)
        assert "42" in result

    def test_nickname_match(self):
        personas = {"p1": {"id": "10", "nickname": "Bob", "trigger_keywords": []}}
        result = find_mentioned_users_by_keywords("Hey Bob!", personas)
        assert "10" in result

    def test_case_insensitive_match(self):
        personas = {"p1": {"id": "5", "trigger_keywords": ["Alice"]}}
        result = find_mentioned_users_by_keywords("hello ALICE", personas)
        assert "5" in result

    def test_no_match_returns_empty(self):
        personas = {"p1": {"id": "1", "trigger_keywords": ["alice"]}}
        result = find_mentioned_users_by_keywords("Hello Bob", personas)
        assert result == set()

    def test_multiple_matches(self):
        personas = {
            "p1": {"id": "1", "trigger_keywords": ["alice"]},
            "p2": {"id": "2", "trigger_keywords": ["bob"]},
        }
        result = find_mentioned_users_by_keywords("Alice and Bob went to the park", personas)
        assert "1" in result
        assert "2" in result

    def test_missing_id_skipped(self):
        personas = {"p1": {"trigger_keywords": ["alice"]}}
        result = find_mentioned_users_by_keywords("hello alice", personas)
        assert result == set()


class TestBuildSystemPromptTemplates:
    """build_system_prompt 6 键（5 header + operational_instructions）消费完整性（S2）. """

    async def test_header_templates_effective(self, mock_discord_bot, mock_discord_message):
        msg = mock_discord_message(content="hi")
        config = {
            "system_prompt": "base",
            "user_personas": {"p1": {"id": "123456789", "prompt": "admin persona"}},
            "role_based_config": {},
        }
        templates = {
            "system_prompt_foundation_header": "基础规则标题",
            "system_prompt_persona_header": "人设标题",
            "system_prompt_situation_header": "情景标题",
            "system_prompt_participants_header": "参与者标题",
            "system_prompt_security_header": "安全标题",
        }
        result = await build_system_prompt(
            mock_discord_bot, config, "PERSONA", "SITUATION", msg, [], templates=templates
        )
        assert "[基础规则标题]" in result
        assert "[人设标题]" in result
        assert "[情景标题]" in result
        assert "[参与者标题]" in result
        assert "[安全标题]" in result
        assert "[Foundation and Core Rules]" not in result
        assert "[Current Persona for This Interaction]" not in result
        assert "[Situational Context]" not in result
        assert "[Context: Participant Personas]" not in result
        assert "[Security & Operational Instructions]" not in result

    async def test_operational_instructions_effective(self, mock_discord_bot, mock_discord_message):
        msg = mock_discord_message(content="hi")
        config = {"system_prompt": "base", "user_personas": {}, "role_based_config": {}}
        result = await build_system_prompt(
            mock_discord_bot, config, "", "", msg, [],
            templates={"operational_instructions": ["指令甲", "指令乙"]},
        )
        assert "指令甲" in result
        assert "指令乙" in result
        assert "You MUST operate" not in result

    @pytest.mark.parametrize("bad", [None, [], [""], ["ok", 123], "not-a-list", [123]])
    async def test_invalid_operational_instructions_fallback(
        self, mock_discord_bot, mock_discord_message, bad
    ):
        msg = mock_discord_message(content="hi")
        config = {"system_prompt": "base", "user_personas": {}, "role_based_config": {}}
        result = await build_system_prompt(
            mock_discord_bot, config, "", "", msg, [],
            templates={"operational_instructions": bad},
        )
        assert "1. You MUST operate" in result

    async def test_none_templates_matches_defaults(
        self, mock_discord_bot, mock_discord_message, monkeypatch
    ):
        class _FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2024, 1, 1, 12, 0, 0, tzinfo=tz or timezone.utc)

        monkeypatch.setattr(pm_module, "datetime", _FixedDatetime)
        msg = mock_discord_message(content="hi")
        config = {"system_prompt": "base", "user_personas": {}, "role_based_config": {}}
        r_none = await build_system_prompt(mock_discord_bot, config, "P", "S", msg, [], templates=None)
        r_empty = await build_system_prompt(mock_discord_bot, config, "P", "S", msg, [], templates={})
        assert r_none == r_empty
        assert "[Foundation and Core Rules]" in r_none
        assert "[Current Persona for This Interaction]" in r_none
        assert "[Situational Context]" in r_none
        assert "[Security & Operational Instructions]" in r_none
        assert "1. You MUST operate" in r_none