import pytest

pytestmark = [pytest.mark.unit]
from app.handlers.automation import (
    track_auto_interject,
    normalize_repeat_content,
    track_repeat_parrot,
    reset_channel_automation_state,
)


class TestTrackAutoInterject:
    def test_disabled_returns_false(self, mock_discord_message):
        msg = mock_discord_message(content="Hello world")
        config = {"auto_interject_enabled": False}
        counts = {}
        result = track_auto_interject(msg, config, counts)
        assert result is False

    def test_message_too_short_returns_false(self, mock_discord_message):
        msg = mock_discord_message(content="Hi")
        config = {
            "auto_interject_enabled": True,
            "auto_interject_interval": 5,
            "auto_interject_min_length": 10,
        }
        counts = {}
        result = track_auto_interject(msg, config, counts)
        assert result is False

    def test_first_message_below_threshold(self, mock_discord_message):
        msg = mock_discord_message(content="Hello world, this is a test message")
        config = {
            "auto_interject_enabled": True,
            "auto_interject_interval": 5,
            "auto_interject_min_length": 0,
        }
        counts = {}
        result = track_auto_interject(msg, config, counts)
        assert result is False
        assert counts[msg.channel.id] == 1

    def test_reaches_threshold_returns_true(self, mock_discord_message):
        msg = mock_discord_message(content="Hello world")
        config = {
            "auto_interject_enabled": True,
            "auto_interject_interval": 3,
            "auto_interject_min_length": 0,
        }
        counts = {msg.channel.id: 2}
        result = track_auto_interject(msg, config, counts)
        assert result is True
        assert counts[msg.channel.id] == 3

    def test_exceeds_threshold_returns_true(self, mock_discord_message):
        msg = mock_discord_message(content="Hello world")
        config = {
            "auto_interject_enabled": True,
            "auto_interject_interval": 3,
            "auto_interject_min_length": 0,
        }
        counts = {msg.channel.id: 5}
        result = track_auto_interject(msg, config, counts)
        assert result is True

    def test_counter_accumulates(self, mock_discord_message):
        msg1 = mock_discord_message(content="First message")
        msg2 = mock_discord_message(content="Second message")
        config = {
            "auto_interject_enabled": True,
            "auto_interject_interval": 10,
            "auto_interject_min_length": 0,
        }
        counts = {}
        track_auto_interject(msg1, config, counts)
        track_auto_interject(msg2, config, counts)
        assert counts[msg1.channel.id] == 2

    def test_invalid_interval_falls_back(self, mock_discord_message):
        msg = mock_discord_message(content="Hello world")
        config = {
            "auto_interject_enabled": True,
            "auto_interject_interval": "invalid",
            "auto_interject_min_length": 0,
        }
        counts = {}
        result = track_auto_interject(msg, config, counts)
        assert result is False

    def test_multiple_channels_independent(self, mock_discord_message):
        config = {
            "auto_interject_enabled": True,
            "auto_interject_interval": 2,
            "auto_interject_min_length": 0,
        }
        msg_ch1 = mock_discord_message(content="ch1 msg", channel_id=111)
        msg_ch2 = mock_discord_message(content="ch2 msg", channel_id=222)
        counts = {}
        assert track_auto_interject(msg_ch1, config, counts) is False
        assert track_auto_interject(msg_ch2, config, counts) is False
        assert counts[111] == 1
        assert counts[222] == 1
        assert track_auto_interject(msg_ch1, config, counts) is True
        assert track_auto_interject(msg_ch2, config, counts) is True


class TestNormalizeRepeatContent:
    def test_disabled_trim_and_case_insensitive(self, mock_discord_message):
        msg = mock_discord_message(content="  Hello World  ")
        config = {
            "repeat_parrot_trim_whitespace": True,
            "repeat_parrot_case_sensitive": False,
            "repeat_parrot_min_length": 2,
        }
        result = normalize_repeat_content(msg, config)
        assert result == ("Hello World", "hello world")

    def test_no_trim(self, mock_discord_message):
        msg = mock_discord_message(content="  Hello World  ")
        config = {
            "repeat_parrot_trim_whitespace": False,
            "repeat_parrot_case_sensitive": False,
            "repeat_parrot_min_length": 2,
        }
        result = normalize_repeat_content(msg, config)
        assert result == ("  Hello World  ", "  hello world  ")

    def test_case_sensitive(self, mock_discord_message):
        msg = mock_discord_message(content="Hello World")
        config = {
            "repeat_parrot_trim_whitespace": True,
            "repeat_parrot_case_sensitive": True,
            "repeat_parrot_min_length": 2,
        }
        result = normalize_repeat_content(msg, config)
        assert result == ("Hello World", "Hello World")

    def test_content_too_short_returns_none(self, mock_discord_message):
        msg = mock_discord_message(content="Hi")
        config = {
            "repeat_parrot_trim_whitespace": True,
            "repeat_parrot_case_sensitive": False,
            "repeat_parrot_min_length": 5,
        }
        result = normalize_repeat_content(msg, config)
        assert result is None

    def test_empty_content_returns_none(self, mock_discord_message):
        msg = mock_discord_message(content="")
        config = {
            "repeat_parrot_trim_whitespace": True,
            "repeat_parrot_case_sensitive": False,
            "repeat_parrot_min_length": 2,
        }
        result = normalize_repeat_content(msg, config)
        assert result is None

    def test_none_content_returns_none(self, mock_discord_message):
        msg = mock_discord_message(content=None)
        config = {
            "repeat_parrot_trim_whitespace": True,
            "repeat_parrot_case_sensitive": False,
            "repeat_parrot_min_length": 2,
        }
        result = normalize_repeat_content(msg, config)
        assert result is None

    def test_whitespace_only_returns_none(self, mock_discord_message):
        msg = mock_discord_message(content="   ")
        config = {
            "repeat_parrot_trim_whitespace": True,
            "repeat_parrot_case_sensitive": False,
            "repeat_parrot_min_length": 2,
        }
        result = normalize_repeat_content(msg, config)
        assert result is None


class TestTrackRepeatParrot:
    def test_disabled_returns_none(self, mock_discord_message):
        msg = mock_discord_message(content="Hello world")
        config = {"repeat_parrot_enabled": False}
        streaks = {}
        result = track_repeat_parrot(msg, config, streaks)
        assert result is None

    def test_first_message_no_trigger(self, mock_discord_message):
        msg = mock_discord_message(content="Hello world")
        config = {
            "repeat_parrot_enabled": True,
            "repeat_parrot_threshold": 3,
            "repeat_parrot_case_sensitive": False,
            "repeat_parrot_trim_whitespace": True,
            "repeat_parrot_min_length": 2,
            "repeat_parrot_require_multiple_users": True,
        }
        streaks = {}
        result = track_repeat_parrot(msg, config, streaks)
        assert result is None
        assert streaks[msg.channel.id]["count"] == 1

    def test_same_content_accumulates_count(self, mock_discord_message):
        config = {
            "repeat_parrot_enabled": True,
            "repeat_parrot_threshold": 3,
            "repeat_parrot_case_sensitive": False,
            "repeat_parrot_trim_whitespace": True,
            "repeat_parrot_min_length": 2,
            "repeat_parrot_require_multiple_users": True,
        }
        streaks = {}

        msg1 = mock_discord_message(content="Hello world", author_id=111)
        track_repeat_parrot(msg1, config, streaks)
        assert streaks[msg1.channel.id]["count"] == 1

        msg2 = mock_discord_message(content="Hello world", author_id=222)
        track_repeat_parrot(msg2, config, streaks)
        assert streaks[msg1.channel.id]["count"] == 2

    def test_different_content_resets_streak(self, mock_discord_message):
        config = {
            "repeat_parrot_enabled": True,
            "repeat_parrot_threshold": 3,
            "repeat_parrot_case_sensitive": False,
            "repeat_parrot_trim_whitespace": True,
            "repeat_parrot_min_length": 2,
            "repeat_parrot_require_multiple_users": False,
        }
        streaks = {}

        msg1 = mock_discord_message(content="Hello world", channel_id=1)
        track_repeat_parrot(msg1, config, streaks)
        assert streaks[1]["count"] == 1

        msg2 = mock_discord_message(content="Different message", channel_id=1)
        track_repeat_parrot(msg2, config, streaks)
        assert streaks[1]["count"] == 1
        assert streaks[1]["normalized"] == "different message"

    def test_reaches_threshold_single_user(self, mock_discord_message):
        config = {
            "repeat_parrot_enabled": True,
            "repeat_parrot_threshold": 3,
            "repeat_parrot_case_sensitive": False,
            "repeat_parrot_trim_whitespace": True,
            "repeat_parrot_min_length": 2,
            "repeat_parrot_require_multiple_users": False,
        }
        streaks = {}

        for _ in range(2):
            msg = mock_discord_message(content="Test message", channel_id=1, author_id=111)
            track_repeat_parrot(msg, config, streaks)

        msg3 = mock_discord_message(content="Test message", channel_id=1, author_id=111)
        result = track_repeat_parrot(msg3, config, streaks)
        assert result == "Test message"

    def test_requires_multiple_users(self, mock_discord_message):
        config = {
            "repeat_parrot_enabled": True,
            "repeat_parrot_threshold": 3,
            "repeat_parrot_case_sensitive": False,
            "repeat_parrot_trim_whitespace": True,
            "repeat_parrot_min_length": 2,
            "repeat_parrot_require_multiple_users": True,
        }
        streaks = {}

        for _ in range(3):
            msg = mock_discord_message(content="Test", channel_id=1, author_id=111)
            track_repeat_parrot(msg, config, streaks)

        result = track_repeat_parrot(
            mock_discord_message(content="Test", channel_id=1, author_id=111),
            config,
            streaks,
        )
        assert result is None

    def test_multiple_users_satisfies_requirement(self, mock_discord_message):
        config = {
            "repeat_parrot_enabled": True,
            "repeat_parrot_threshold": 3,
            "repeat_parrot_case_sensitive": False,
            "repeat_parrot_trim_whitespace": True,
            "repeat_parrot_min_length": 2,
            "repeat_parrot_require_multiple_users": True,
        }
        streaks = {}

        msg1 = mock_discord_message(content="Hello!", channel_id=1, author_id=111)
        track_repeat_parrot(msg1, config, streaks)
        msg2 = mock_discord_message(content="Hello!", channel_id=1, author_id=222)
        track_repeat_parrot(msg2, config, streaks)

        msg3 = mock_discord_message(content="Hello!", channel_id=1, author_id=111)
        result = track_repeat_parrot(msg3, config, streaks)
        assert result == "Hello!"

    def test_parroted_flag_prevents_repeat(self, mock_discord_message):
        config = {
            "repeat_parrot_enabled": True,
            "repeat_parrot_threshold": 3,
            "repeat_parrot_case_sensitive": False,
            "repeat_parrot_trim_whitespace": True,
            "repeat_parrot_min_length": 2,
            "repeat_parrot_require_multiple_users": False,
        }
        streaks = {}

        for _ in range(3):
            msg = mock_discord_message(content="Wow!", channel_id=1, author_id=111)
            track_repeat_parrot(msg, config, streaks)

        result = track_repeat_parrot(
            mock_discord_message(content="Wow!", channel_id=1, author_id=111),
            config,
            streaks,
        )
        assert result is None

    def test_case_sensitivity_in_tracking(self, mock_discord_message):
        config_with_case = dict(
            repeat_parrot_enabled=True,
            repeat_parrot_threshold=2,
            repeat_parrot_case_sensitive=True,
            repeat_parrot_trim_whitespace=True,
            repeat_parrot_min_length=2,
            repeat_parrot_require_multiple_users=False,
        )
        streaks = {}

        msg1 = mock_discord_message(content="Hello", channel_id=1, author_id=111)
        track_repeat_parrot(msg1, config_with_case, streaks)
        msg2 = mock_discord_message(content="hello", channel_id=1, author_id=222)
        result = track_repeat_parrot(msg2, config_with_case, streaks)
        assert result is None

    def test_too_short_message_clears_streak(self, mock_discord_message):
        config = {
            "repeat_parrot_enabled": True,
            "repeat_parrot_threshold": 3,
            "repeat_parrot_case_sensitive": False,
            "repeat_parrot_trim_whitespace": True,
            "repeat_parrot_min_length": 5,
        }
        streaks = {1: {"normalized": "hello world", "content": "Hello World", "count": 2, "user_ids": {"111"}, "parroted": False}}

        msg = mock_discord_message(content="Hi", channel_id=1)
        result = track_repeat_parrot(msg, config, streaks)
        assert result is None
        assert 1 not in streaks


class TestResetChannelAutomationState:
    def test_resets_counts_and_streaks(self):
        auto_counts = {1: 10, 2: 5}
        streaks = {1: {"normalized": "test", "content": "test", "count": 3, "user_ids": {"111"}, "parroted": False}, 2: {"normalized": "x", "content": "x", "count": 1, "user_ids": {"222"}, "parroted": False}}
        reset_channel_automation_state(1, auto_counts, streaks)
        assert auto_counts[1] == 0
        assert 1 not in streaks
        assert auto_counts[2] == 5
        assert 2 in streaks

    def test_reset_nonexistent_channel(self):
        auto_counts = {}
        streaks = {}
        reset_channel_automation_state(999, auto_counts, streaks)
        assert auto_counts[999] == 0
        assert 999 not in streaks
