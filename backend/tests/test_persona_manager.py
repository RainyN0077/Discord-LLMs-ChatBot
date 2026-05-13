import pytest
from app.utils import Stub
from app.core_logic.persona_manager import (
    get_highest_configured_role,
    get_rich_identity,
    determine_bot_persona,
    find_mentioned_users_by_keywords,
)


class TestGetHighestConfiguredRole:
    def test_member_with_no_roles(self):
        member = Stub(roles=[], id=123)
        result = get_highest_configured_role(member, {"role_a": {"id": "999"}})
        assert result is None

    def test_role_not_configured(self):
        role1 = Stub(id=111, name="Admin")
        member = Stub(roles=[role1], id=123)
        result = get_highest_configured_role(member, {"role_b": {"id": "222"}})
        assert result is None

    def test_matching_role_returns_config(self):
        role1 = Stub(id=111, name="Admin")
        role2 = Stub(id=222, name="Moderator")
        member = Stub(roles=[role1, role2], id=123)
        role_configs = {
            "mod_cfg": {"id": "222", "title": "Mod", "prompt": "You are a mod."},
        }
        result = get_highest_configured_role(member, role_configs)
        assert result is None

    def test_highest_role_takes_priority(self):
        role_low = Stub(id=111, name="Member")
        role_high = Stub(id=999, name="Owner")
        member = Stub(roles=[role_low, role_high], id=123)
        role_configs = {
            "owner_cfg": {"id": "999", "title": "Owner", "prompt": "Owner prompt"},
            "member_cfg": {"id": "111", "title": "Member", "prompt": "Member prompt"},
        }
        result = get_highest_configured_role(member, role_configs)
        assert result is None

    def test_non_member_input_returns_none(self):
        user = Stub(id=123, name="User")
        result = get_highest_configured_role(user, {})
        assert result is None

    def test_empty_role_configs(self):
        role = Stub(id=111, name="Admin")
        member = Stub(roles=[role], id=123)
        result = get_highest_configured_role(member, {})
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

    def test_persona_info_id_match(self):
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
