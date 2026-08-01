"""
Integration test: verify that user portraits (user_personas) and negative portraits
(user_options) are correctly injected into the LLM system prompt context.
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.utils import Stub


def _build_mock_bot():
    bot = Stub()
    bot.user = Stub(id=999888777666, name="Test-Bot", display_name="TestBot")
    bot.fetch_user = _async_stub_re([None])
    return bot


def _build_mock_guild():
    guild = Stub(id=111)
    guild.members = []
    guild.get_member = lambda uid: None
    return guild


def _build_mock_user(uid, name, display_name=None):
    user = Stub(
        id=uid, name=name, display_name=display_name or name,
        bot=False, roles=[], discriminator="0",
    )
    return user


def _async_stub_re(results):
    async def _fn(*a, **kw):
        results[0]
        return results[0]
    return _fn


def test_user_portrait_injected_by_mention():
    """User persona should appear when the user is @mentioned."""
    from app.core_logic.persona_manager import build_system_prompt, determine_bot_persona

    bot = _build_mock_bot()
    config = {
        "system_prompt": "You are a helpful assistant.",
        "user_personas": {
            "p1": {
                "id": "123456789",
                "prompt": "Alice is a senior engineer who prefers concise answers.",
                "nickname": "Ali",
                "trigger_keywords": [],
            }
        },
    }

    author = _build_mock_user(123456789, "Alice", "Alice")

    guild = _build_mock_guild()
    channel = Stub(id=222, guild=guild)

    mention_user = _build_mock_user(123456789, "Alice", "Alice")

    msg = Stub()
    msg.author = author
    msg.channel = channel
    msg.guild = guild
    msg.content = "hello"
    msg.clean_content = "hello"
    msg.mentions = [mention_user]
    msg.reference = None
    msg.attachments = []

    _, _, directives = determine_bot_persona(config, "222", "111", None, None)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    prompt = loop.run_until_complete(
        build_system_prompt(bot, config, "", "", msg, directives)
    )

    assert "Alice" in prompt, f"Expected Alice in prompt, got:\n{prompt[:500]}"
    assert "senior engineer" in prompt, f"Expected persona content in prompt, got:\n{prompt[:500]}"
    assert "Participant Persona" in prompt, f"Expected Participant Personas block, got:\n{prompt[:500]}"
    print("PASS: User portrait injected by mention")
    print(f"  Prompt snippet: {prompt[prompt.find('[Context: Participant Personas]'):][:300]}")


def test_user_portrait_injected_by_keyword():
    """User persona should appear when trigger_keyword is in message text."""
    from app.core_logic.persona_manager import build_system_prompt, determine_bot_persona

    bot = _build_mock_bot()
    config = {
        "system_prompt": "You are a helpful assistant.",
        "user_personas": {
            "p1": {
                "id": "123456789",
                "prompt": "Bob is a wizard who speaks in riddles.",
                "nickname": "Bobby",
                "trigger_keywords": ["wizard", "magic"],
            }
        },
    }

    author = _build_mock_user(999999, "Stranger", "Stranger")

    guild = _build_mock_guild()
    channel = Stub(id=222, guild=guild)

    bob_user = _build_mock_user(123456789, "Bob", "Bobby")
    guild.get_member = lambda uid: bob_user if uid == 123456789 else None
    bot.fetch_user = _async_stub_re([bob_user])

    msg = Stub()
    msg.author = author
    msg.channel = channel
    msg.guild = guild
    msg.content = "Hey anyone seen the wizard around?"
    msg.clean_content = "Hey anyone seen the wizard around?"
    msg.mentions = []
    msg.reference = None
    msg.attachments = []

    bot.fetch_user = _async_stub_re([author])

    _, _, directives = determine_bot_persona(config, "222", "111", None, None)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    prompt = loop.run_until_complete(
        build_system_prompt(bot, config, "", "", msg, directives)
    )

    assert "wizard" in prompt.lower(), f"Expected wizard persona, got:\n{prompt[:500]}"
    print("PASS: User portrait triggered by keyword")
    print(f"  Prompt snippet: {prompt[prompt.find('[Context: Participant Personas]'):][:300]}")


def test_negative_portrait_injected():
    """Negative portrait from user_options should appear in system prompt."""
    from app.core_logic.persona_manager import build_system_prompt, determine_bot_persona

    bot = _build_mock_bot()
    config = {
        "system_prompt": "You are a helpful assistant.",
        "user_personas": {},
        "user_options": {
            "enabled": True,
            "rules": {
                "rule-1": {
                    "scope_type": "global",
                    "scope_id": "",
                    "mode": "blacklist",
                    "users": {
                        "u-1": {
                            "user_id": "123456789",
                            "user_display_name": "Troll",
                            "blacklist_mode": "negative_portrait",
                            "negative_portrait": "This user is known for trolling and sarcasm. Be cautious.",
                        }
                    }
                }
            }
        },
    }

    author = _build_mock_user(123456789, "Troll", "Troll")

    guild = _build_mock_guild()
    channel = Stub(id=222, guild=guild)

    msg = Stub()
    msg.author = author
    msg.channel = channel
    msg.guild = guild
    msg.content = "hello"
    msg.clean_content = "hello"
    msg.mentions = []
    msg.reference = None
    msg.attachments = []

    _, _, directives = determine_bot_persona(config, "222", "111", None, None)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    prompt = loop.run_until_complete(
        build_system_prompt(bot, config, "", "", msg, directives)
    )

    assert "Negative Impression" in prompt, f"Expected Negative Impression block, got:\n{prompt[:500]}"
    assert "trolling" in prompt.lower(), f"Expected trolling content, got:\n{prompt[:500]}"
    print("PASS: Negative portrait injected")
    print(f"  Prompt snippet: {prompt[prompt.find('[Negative Impression'):][:300]}")


def test_blacklist_blocks_trigger():
    """Blacklisted user with deny_response should be blocked from triggering."""
    from app.core_logic.user_options_manager import is_user_blocked_from_response

    config = {
        "user_options": {
            "enabled": True,
            "rules": {
                "rule-1": {
                    "scope_type": "global",
                    "scope_id": "",
                    "mode": "blacklist",
                    "users": {
                        "u-1": {
                            "user_id": "123456789",
                            "user_display_name": "BlockedUser",
                            "blacklist_mode": "deny_response",
                            "negative_portrait": "",
                        }
                    }
                }
            }
        },
    }

    assert is_user_blocked_from_response(config, "111", "222", "123456789") is True, "deny_response user should be blocked"
    assert is_user_blocked_from_response(config, "111", "222", "999999") is False, "unknown user should not be blocked"
    print("PASS: Blacklist blocks user correctly")


def test_whitelist_triggers_only():
    """Whitelisted user with triggers_only should still allow response."""
    from app.core_logic.user_options_manager import is_user_blocked_from_response

    config = {
        "user_options": {
            "enabled": True,
            "rules": {
                "rule-1": {
                    "scope_type": "global",
                    "scope_id": "",
                    "mode": "whitelist",
                    "whitelist_behavior": "triggers_only",
                    "users": {
                        "u-1": {
                            "user_id": "123456789",
                            "user_display_name": "VIP",
                            "blacklist_mode": "deny_response",
                            "negative_portrait": "",
                        }
                    }
                }
            }
        },
    }

    assert is_user_blocked_from_response(config, "111", "222", "123456789") is True, "triggers_only should block non-triggering user"
    assert is_user_blocked_from_response(config, "111", "222", "999999") is False, "unknown user should not be blocked"
    print("PASS: Whitelist triggers_only works")


def test_scope_priority_channel_over_guild():
    """Channel-scoped rule should take priority over guild-scoped rule."""
    from app.core_logic.user_options_manager import resolve_user_options

    config = {
        "user_options": {
            "enabled": True,
            "rules": {
                "rule-guild": {
                    "scope_type": "guild",
                    "scope_id": "111",
                    "mode": "blacklist",
                    "users": {
                        "u-1": {
                            "user_id": "123456789",
                            "user_display_name": "User",
                            "blacklist_mode": "block_messages",
                            "negative_portrait": "",
                        }
                    }
                },
                "rule-channel": {
                    "scope_type": "channel",
                    "scope_id": "222",
                    "mode": "whitelist",
                    "whitelist_behavior": "messages_only",
                    "users": {
                        "u-2": {
                            "user_id": "123456789",
                            "user_display_name": "User",
                            "blacklist_mode": "deny_response",
                            "negative_portrait": "",
                        }
                    }
                }
            }
        },
    }

    resolved = resolve_user_options(config, "111", "222", "123456789")
    assert resolved.mode == "whitelist", f"Expected whitelist (channel scope), got {resolved.mode}"
    assert resolved.whitelist_behavior == "messages_only", f"Expected messages_only, got {resolved.whitelist_behavior}"
    print("PASS: Channel scope takes priority over guild scope")


if __name__ == "__main__":
    print("=== Portrait & Blacklist Context Integration Tests ===\n")
    for name, test_fn in [
        ("test_user_portrait_injected_by_mention", test_user_portrait_injected_by_mention),
        ("test_user_portrait_injected_by_keyword", test_user_portrait_injected_by_keyword),
        ("test_negative_portrait_injected", test_negative_portrait_injected),
        ("test_blacklist_blocks_trigger", test_blacklist_blocks_trigger),
        ("test_whitelist_triggers_only", test_whitelist_triggers_only),
        ("test_scope_priority_channel_over_guild", test_scope_priority_channel_over_guild),
    ]:
        print(f"\n--- {name} ---")
        try:
            test_fn()
        except Exception as e:
            print(f"FAIL: {e}")
            import traceback
            traceback.print_exc()

    print("\n=== Done ===")
