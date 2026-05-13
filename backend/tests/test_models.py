import pytest

pytestmark = [pytest.mark.unit]
from pydantic import ValidationError

from app.models import (
    Config,
    DirectChatRequest,
    DirectChatMessage,
    DirectChatAttachment,
    PluginTriggerRequest,
    MemoryCandidateItem,
    MemoryItem,
    WorldBookItem,
    UpdateMemoryRequest,
    ClearMemoryRequest,
    DebuggerRequest,
    ModelTestRequest,
    PluginConfig,
    Persona,
    RoleConfig,
    ContextSettings,
    ScopedPrompts,
    ScopedPromptItem,
)


class TestConfigModel:
    def _base_config(self, **overrides):
        defaults = dict(
            discord_token="test-token",
            llm_provider="openai",
            api_key="sk-test",
            model_name="gpt-4o",
            system_prompt="Be helpful.",
            blocked_prompt_response="Nope.",
            trigger_keywords=[],
            stream_response=False,
            context_mode="channel",
            api_secret_key="test-secret",
            channel_context_settings=ContextSettings(message_limit=10, char_limit=4000),
            memory_context_settings=ContextSettings(message_limit=15, char_limit=6000),
        )
        defaults.update(overrides)
        return defaults

    def test_minimal_valid_config(self):
        cfg = Config(**self._base_config())
        assert cfg.discord_token == "test-token"
        assert cfg.llm_provider == "openai"

    def test_missing_required_fields_raises(self):
        with pytest.raises(ValidationError):
            Config()

    def test_default_values_applied(self):
        cfg = Config(**self._base_config(llm_is_multimodal=True))
        assert cfg.llm_is_multimodal is True
        assert cfg.ocr_provider == "openai"
        assert cfg.embedding_provider == "openai"
        assert cfg.rerank_provider == "openai"

    def test_ocr_constraints(self):
        cfg = Config(**self._base_config(ocr_max_output_chars=5000))
        assert cfg.ocr_max_output_chars == 5000

    def test_ocr_max_output_chars_out_of_range(self):
        with pytest.raises(ValidationError):
            Config(**self._base_config(ocr_max_output_chars=100))

    def test_auto_interject_constraints(self):
        with pytest.raises(ValidationError):
            Config(**self._base_config(auto_interject_interval=0))

    def test_repeat_parrot_threshold_constraint(self):
        with pytest.raises(ValidationError):
            Config(**self._base_config(repeat_parrot_threshold=1))

    def test_nested_scoped_prompts(self):
        cfg = Config(**self._base_config(
            scoped_prompts=ScopedPrompts(
                guilds={"123": ScopedPromptItem(id="1", enabled=True, mode="append", prompt="Guild prompt")},
                channels={},
            ),
        ))
        assert cfg.scoped_prompts.guilds["123"].prompt == "Guild prompt"

    def test_api_secret_key_present(self):
        cfg = Config(**self._base_config(api_secret_key="my-secret-123"))
        assert cfg.api_secret_key == "my-secret-123"


class TestDirectChatRequest:
    def test_empty_messages_valid(self):
        req = DirectChatRequest()
        assert req.messages == []

    def test_valid_request_with_messages(self):
        req = DirectChatRequest(
            messages=[DirectChatMessage(role="user", content="Hello")],
            include_system_prompt=True,
        )
        assert len(req.messages) == 1
        assert req.messages[0].content == "Hello"

    def test_default_debug_mode_false(self):
        req = DirectChatRequest()
        assert req.debug_mode is False

    def test_attachments_default_empty(self):
        req = DirectChatRequest()
        assert req.attachments == []


class TestPluginTriggerRequest:
    def test_default_values(self):
        req = PluginTriggerRequest(plugin_name="test_plugin")
        assert req.plugin_name == "test_plugin"
        assert req.author_name == "API"
        assert req.author_display_name == "API"
        assert req.message_content == ""

    def test_custom_values(self):
        req = PluginTriggerRequest(
            plugin_name="my_plugin",
            message_content="test content",
            author_name="John",
            author_id=42,
        )
        assert req.author_name == "John"
        assert req.author_id == 42
        assert req.message_content == "test content"


class TestMemoryCandidateItem:
    def test_required_fields(self):
        item = MemoryCandidateItem(
            id=1,
            content_sample="test content",
            first_seen="2024-01-01T00:00:00Z",
            last_seen="2024-01-02T00:00:00Z",
            seen_count=3,
            distinct_user_count=1,
            promoted=0,
        )
        assert item.id == 1
        assert item.content_sample == "test content"
        assert item.seen_count == 3

    def test_default_list_fields(self):
        item = MemoryCandidateItem(
            id=1,
            content_sample="test",
            first_seen="2024-01-01T00:00:00Z",
            last_seen="2024-01-02T00:00:00Z",
            seen_count=1,
            distinct_user_count=1,
            promoted=0,
        )
        assert item.user_ids == []
        assert item.channel_ids == []
        assert item.source_types == []

    def test_promoted_item(self):
        item = MemoryCandidateItem(
            id=2,
            content_sample="promoted content",
            first_seen="2024-01-01T00:00:00Z",
            last_seen="2024-01-02T00:00:00Z",
            seen_count=5,
            distinct_user_count=2,
            promoted=1,
            promoted_memory_id=10,
            promoted_at="2024-01-03T00:00:00Z",
        )
        assert item.promoted == 1
        assert item.promoted_memory_id == 10


class TestMemoryItem:
    def test_minimal_item(self):
        item = MemoryItem(content="Test memory content")
        assert item.content == "Test memory content"
        assert item.id is None
        assert item.source is None

    def test_full_item(self):
        item = MemoryItem(
            id=1,
            content="Full memory",
            timestamp="2024-01-01T00:00:00",
            user_id="123",
            user_name="TestUser",
            source="manual",
            timezone="UTC",
        )
        assert item.id == 1
        assert item.user_name == "TestUser"


class TestWorldBookItem:
    def test_default_enabled(self):
        item = WorldBookItem(keywords="test", content="Test world book")
        assert item.enabled is True

    def test_custom_values(self):
        item = WorldBookItem(
            id=5,
            keywords="lore, world",
            content="Important lore content",
            enabled=False,
            linked_user_id="42",
        )
        assert item.keywords == "lore, world"
        assert item.enabled is False
        assert item.linked_user_id == "42"


class TestPersona:
    def test_defaults(self):
        p = Persona()
        assert p.trigger_keywords == []
        assert p.nickname is None

    def test_with_values(self):
        p = Persona(id="1", nickname="Alice", prompt="I am Alice", trigger_keywords=["alice", "test"])
        assert p.nickname == "Alice"
        assert len(p.trigger_keywords) == 2


class TestRoleConfig:
    def test_defaults(self):
        rc = RoleConfig()
        assert rc.title == ""
        assert rc.prompt == ""
        assert rc.message_limit == 0
        assert rc.token_limit == 0

    def test_constraints(self):
        with pytest.raises(ValidationError):
            RoleConfig(message_limit=-1)

        with pytest.raises(ValidationError):
            RoleConfig(message_refresh_minutes=0)

        with pytest.raises(ValidationError):
            RoleConfig(message_output_budget=0)


class TestContextSettings:
    def test_defaults(self):
        cs = ContextSettings(message_limit=10, char_limit=4000)
        assert cs.unlimited_context_length is False
        assert cs.unlimited_message_count is False

    def test_negative_values_rejected(self):
        with pytest.raises(ValidationError):
            ContextSettings(message_limit=-1, char_limit=4000)

    def test_valid_settings(self):
        cs = ContextSettings(
            message_limit=100,
            char_limit=10000,
            unlimited_context_length=True,
            unlimited_message_count=True,
        )
        assert cs.unlimited_context_length is True
        assert cs.unlimited_message_count is True


class TestUpdateMemoryRequest:
    def test_content_required(self):
        req = UpdateMemoryRequest(content="Updated content")
        assert req.content == "Updated content"


class TestClearMemoryRequest:
    def test_channel_id_required(self):
        req = ClearMemoryRequest(channel_id="12345")
        assert req.channel_id == "12345"


class TestDebuggerRequest:
    def test_required_fields(self):
        req = DebuggerRequest(user_id="123", channel_id="456", message_content="test")
        assert req.user_id == "123"
        assert req.guild_id is None

    def test_optional_guild_and_role(self):
        req = DebuggerRequest(user_id="1", channel_id="2", guild_id="3", role_id="4", message_content="test")
        assert req.guild_id == "3"
        assert req.role_id == "4"


class TestModelTestRequest:
    def test_defaults(self):
        req = ModelTestRequest(provider="openai", api_key="sk-test", model_name="gpt-4o")
        assert req.task == "chat"
        assert req.base_url is None
        assert req.ocr_timeout_seconds is None

    def test_ocr_timeout_constraints(self):
        with pytest.raises(ValidationError):
            ModelTestRequest(provider="openai", api_key="k", model_name="m", ocr_timeout_seconds=0)

        with pytest.raises(ValidationError):
            ModelTestRequest(provider="openai", api_key="k", model_name="m", ocr_timeout_seconds=100000)
