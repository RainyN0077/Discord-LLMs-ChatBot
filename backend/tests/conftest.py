import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

os.environ.setdefault("FAIL_ON_REDIS_ERROR", "false")

from app.utils import Stub, _async_stub
from app.config_cache import DEFAULT_CONFIG, invalidate_cache
from app.state import MEMORY_CUTOFFS
from app import state


def _create_mock_core_shared(tmp_path):
    mock_core_shared = MagicMock()
    mock_core_shared.token_calculator = MagicMock()
    mock_core_shared.token_calculator.get_token_count = MagicMock(return_value=100)
    mock_core_shared.token_calculator.get_token_count_for_messages = MagicMock(return_value=500)
    mock_core_shared.redis_client = MagicMock()
    mock_core_shared.redis_client.set = MagicMock(return_value=True)
    mock_core_shared.redis_client.get = MagicMock(return_value=None)
    mock_core_shared.redis_client.delete = MagicMock(return_value=True)
    mock_core_shared.redis_client.exists = MagicMock(return_value=False)
    mock_core_shared.INSTANCE_ID = "test-instance"
    mock_core_shared.strip_thinking_sections = MagicMock(return_value="sanitized text")
    mock_core_shared.strip_dsml_tool_blocks = MagicMock(return_value="sanitized text")
    mock_core_shared.contains_dsml_tool_blocks = MagicMock(return_value=False)
    mock_core_shared._parse_user_info_fields = MagicMock(return_value={})
    mock_core_shared._try_acquire_bot_process_lock = MagicMock(return_value=None)
    mock_core_shared._release_bot_process_lock = MagicMock(return_value=None)
    mock_core_shared._get_bot_lock_path = MagicMock(return_value=tmp_path / "bot.lock")
    return mock_core_shared


@pytest.fixture(autouse=True)
def _reset_global_state(monkeypatch, tmp_path):
    MEMORY_CUTOFFS.clear()
    invalidate_cache()
    state.bot_manager = None
    state.bot_task = None

    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    config_file = data_dir / "config.json"
    bots_dir = data_dir / "bots"
    bots_dir.mkdir(exist_ok=True)

    import app.config_cache as cc
    monkeypatch.setattr(cc, "DATA_DIR", data_dir)
    monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
    monkeypatch.setattr(cc, "BOTS_DIR", bots_dir)

    import app.routers.usage as usage_mod
    monkeypatch.setattr(usage_mod, "DATA_DIR", data_dir)
    import app.routers.logs as logs_mod
    monkeypatch.setattr(logs_mod, "DATA_DIR", data_dir)

    test_db_path = tmp_path / "test_kb.sqlite"
    from app.core_logic.knowledge_manager import KnowledgeManager
    test_km = KnowledgeManager(db_path=str(test_db_path))

    import app.core_logic.knowledge_manager as km_mod
    monkeypatch.setattr(km_mod, "get_knowledge_manager", lambda: test_km)
    import app.core_logic.context_builder as cb_mod
    monkeypatch.setattr(cb_mod, "get_knowledge_manager", lambda: test_km)
    import app.routers.memory as mem_mod
    monkeypatch.setattr(mem_mod, "get_knowledge_manager", lambda: test_km)
    import app.handlers.context_assembler as ca_mod
    try:
        monkeypatch.setattr(ca_mod, "get_knowledge_manager", lambda: test_km)
    except AttributeError:
        pass

    mock_core_shared = _create_mock_core_shared(tmp_path)
    _original_core_shared = sys.modules.get("app.core_shared")
    sys.modules["app.core_shared"] = mock_core_shared

    yield

    if _original_core_shared is not None:
        sys.modules["app.core_shared"] = _original_core_shared
    else:
        sys.modules.pop("app.core_shared", None)


@pytest.fixture
def test_config_dict() -> Dict[str, Any]:
    return {
        **DEFAULT_CONFIG,
        "bot_id": "test-bot",
        "bot_name": "Test Bot",
        "platform": "discord",
        "enabled": True,
        "discord_token": "",
        "api_secret_key": "test-api-key-for-tests",
        "llm_provider": "openai",
        "model_name": "gpt-4o",
        "api_key": "test-openai-key",
        "system_prompt": "You are a test assistant.",
        "blocked_prompt_response": "I cannot respond to that.",
        "trigger_keywords": [],
        "stream_response": False,
        "context_mode": "channel",
        "auto_interject_enabled": False,
        "repeat_parrot_enabled": False,
        "user_personas": {},
        "role_based_config": {},
        "scoped_prompts": {"guilds": {}, "channels": {}},
    }


@pytest.fixture
def mock_discord_message():
    def _make(**overrides) -> Stub:
        author = Stub(
            id=overrides.pop("author_id", 123456789),
            name=overrides.pop("author_name", "TestUser"),
            display_name=overrides.pop("author_display_name", "TestUser"),
            bot=False,
            roles=overrides.pop("author_roles", []),
        )
        channel = Stub(
            id=overrides.pop("channel_id", 987654321),
            name=overrides.pop("channel_name", "test-channel"),
        )
        guild = Stub(
            id=overrides.pop("guild_id", 111111111),
            name=overrides.pop("guild_name", "test-guild"),
        )
        reference = overrides.pop("reference", None)
        defaults = dict(
            content="Hello world",
            clean_content="Hello world",
            author=author,
            channel=channel,
            guild=guild,
            mentions=[],
            attachments=[],
            reference=reference,
            created_at=None,
        )
        defaults.update(overrides)
        return Stub(**defaults)
    return _make


@pytest.fixture
def mock_discord_bot():
    bot = Stub(
        user=Stub(id=999999999, name="BotUser", display_name="BotUser", bot=True),
        fetch_user=_async_stub(Stub(id=888888888, name="FetchedUser", display_name="FetchedUser", bot=False)),
    )
    return bot


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test_knowledge.sqlite")
    from app.core_logic.knowledge_manager import KnowledgeManager
    km = KnowledgeManager(db_path=db_path)
    return km


@pytest.fixture
def knowledge_manager_test(test_db):
    return test_db


@pytest.fixture
def auth_headers(test_config_dict):
    return {"X-API-Key": test_config_dict["api_secret_key"]}


@pytest.fixture
def bad_auth_headers():
    return {"X-API-Key": "wrong-api-key"}


@pytest.fixture
async def app_client(tmp_path, test_config_dict, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    bots_dir = data_dir / "bots"
    bots_dir.mkdir(exist_ok=True)
    config_file = data_dir / "config.json"
    config_file.write_text(json.dumps(test_config_dict, indent=2), encoding="utf-8")

    import app.config_cache as cc
    monkeypatch.setattr(cc, "DATA_DIR", data_dir)
    monkeypatch.setattr(cc, "CONFIG_FILE", config_file)
    monkeypatch.setattr(cc, "BOTS_DIR", bots_dir)

    import app.routers.usage as usage_mod
    monkeypatch.setattr(usage_mod, "DATA_DIR", data_dir)
    import app.routers.logs as logs_mod
    monkeypatch.setattr(logs_mod, "DATA_DIR", data_dir)

    cc.invalidate_cache()

    test_db_path = tmp_path / "test_kb.sqlite"
    from app.core_logic.knowledge_manager import KnowledgeManager
    test_km = KnowledgeManager(db_path=str(test_db_path))
    import app.core_logic.knowledge_manager as km_mod
    monkeypatch.setattr(km_mod, "get_knowledge_manager", lambda: test_km)
    import app.routers.memory as mem_mod
    monkeypatch.setattr(mem_mod, "get_knowledge_manager", lambda: test_km)

    from app.bot_manager import BotManager
    mock_manager = MagicMock(spec=BotManager)
    mock_manager._instances = {}
    mock_manager.list = MagicMock(return_value=[])
    mock_manager.get = MagicMock(return_value=None)
    mock_manager.load_all = AsyncMock(return_value=None)
    mock_manager.shutdown = AsyncMock(return_value=None)
    mock_manager.create = AsyncMock(return_value="test-bot")
    monkeypatch.setattr(state, "bot_manager", mock_manager)

    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
