"""Tests for app.alerting.quota_alert — QuotaAlertManager class.

Covers:
  - Usage calculation and level determination
  - Webhook URL validation (P0-7 SSRF prevention)
  - Level promotion alerting (no repeat alerts for same level)
  - Webhook delivery failure handling
  - Edge cases (zero quota, zero usage)
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.alerting.quota_alert import (
    QuotaAlertConfig,
    QuotaAlertLevel,
    QuotaAlertManager,
    QuotaAlert,
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def manager():
    """QuotaAlertManager with default thresholds (80% warning, 95% critical)."""
    return QuotaAlertManager(webhook_url=None)


@pytest.fixture
def manager_with_webhook():
    """QuotaAlertManager with a valid webhook URL (webhook.site is a public SaaS)."""
    return QuotaAlertManager(webhook_url="https://hooks.example.com/alerts")


def _make_usage(requests=10, total_tokens=1000):
    return {"requests": requests, "total_tokens": total_tokens, "input_tokens": 500, "output_tokens": 500}


def _make_quota(token_limit=0, request_limit=0):
    q = {}
    if token_limit > 0:
        q["token_limit"] = token_limit
    if request_limit > 0:
        q["request_limit"] = request_limit
    return q


# =========================================================================
# Test: QuotaAlertConfig
# =========================================================================

class TestQuotaAlertConfig:
    def test_default_values(self):
        cfg = QuotaAlertConfig()
        assert cfg.enabled is False
        assert cfg.webhook_url == ""
        assert cfg.warning_threshold == 0.80
        assert cfg.critical_threshold == 0.95

    def test_custom_values(self):
        cfg = QuotaAlertConfig(
            enabled=True,
            webhook_url="https://hooks.example.com/alert",
            warning_threshold=0.70,
            critical_threshold=0.90,
        )
        assert cfg.enabled is True
        assert cfg.warning_threshold == 0.70
        assert cfg.critical_threshold == 0.90

    def test_threshold_bounds(self):
        """Thresholds must be between 0.0 and 1.0."""
        with pytest.raises(ValueError):
            QuotaAlertConfig(warning_threshold=1.5)
        with pytest.raises(ValueError):
            QuotaAlertConfig(critical_threshold=-0.1)

    def test_webhook_url_empty_string(self):
        """Empty webhook_url is valid (no webhook delivery, local log only)."""
        cfg = QuotaAlertConfig(enabled=True, webhook_url="")
        assert cfg.webhook_url == ""


# =========================================================================
# Test: Usage calculation and level determination
# =========================================================================

class TestCalcUsagePercent:
    @pytest.mark.parametrize("usage,quota,expected", [
        # Normal cases
        (_make_usage(total_tokens=500), _make_quota(token_limit=1000), 0.50),
        (_make_usage(total_tokens=800), _make_quota(token_limit=1000), 0.80),
        (_make_usage(total_tokens=950), _make_quota(token_limit=1000), 0.95),
        (_make_usage(total_tokens=1500), _make_quota(token_limit=1000), 1.0),  # capped at 1.0
        # Fallback to request_limit
        (_make_usage(requests=5, total_tokens=0), _make_quota(request_limit=10), 0.50),
        (_make_usage(requests=9, total_tokens=0), _make_quota(request_limit=10), 0.90),
        # Empty quota → 0.0
        (_make_usage(total_tokens=1000), {}, 0.0),
        # Zero limits → 0.0
        (_make_usage(total_tokens=1000), _make_quota(token_limit=0, request_limit=0), 0.0),
        # Zero usage
        (_make_usage(total_tokens=0), _make_quota(token_limit=1000), 0.0),
    ])
    def test_calc_usage_percent(self, usage, quota, expected, manager):
        result = manager._calc_usage_percent(usage, quota)
        assert abs(result - expected) < 0.001, f"Expected {expected}, got {result}"

    def test_token_limit_has_priority(self, manager):
        """token_limit should be checked before request_limit."""
        usage = _make_usage(requests=10, total_tokens=500)
        quota = {"token_limit": 1000, "request_limit": 5}
        result = manager._calc_usage_percent(usage, quota)
        # token_limit: 500/1000 = 0.5, request_limit: 10/5 = 2.0
        # token_limit has priority
        assert abs(result - 0.50) < 0.001


class TestDetermineLevel:
    def test_ok_below_warning(self, manager):
        assert manager._determine_level(0.50) == QuotaAlertLevel.OK
        assert manager._determine_level(0.79) == QuotaAlertLevel.OK

    def test_warning_at_threshold(self, manager):
        assert manager._determine_level(0.80) == QuotaAlertLevel.WARNING
        assert manager._determine_level(0.90) == QuotaAlertLevel.WARNING
        assert manager._determine_level(0.949) == QuotaAlertLevel.WARNING

    def test_critical_at_threshold(self, manager):
        assert manager._determine_level(0.95) == QuotaAlertLevel.CRITICAL
        assert manager._determine_level(0.99) == QuotaAlertLevel.CRITICAL
        assert manager._determine_level(1.0) == QuotaAlertLevel.CRITICAL

    def test_custom_thresholds(self):
        m = QuotaAlertManager(warning_threshold=0.60, critical_threshold=0.85)
        assert m._determine_level(0.50) == QuotaAlertLevel.OK
        assert m._determine_level(0.60) == QuotaAlertLevel.WARNING
        assert m._determine_level(0.85) == QuotaAlertLevel.CRITICAL


# =========================================================================
# Test: Alert flow — level promotion only
# =========================================================================

class TestCheckAndAlert:
    @pytest.mark.asyncio
    async def test_usage_below_warning_returns_none(self, manager):
        """Usage < 80% → no alert."""
        alert = await manager.check_and_alert(
            bot_id="test-bot",
            user_id=None,
            daily_usage=_make_usage(total_tokens=500),
            daily_quota=_make_quota(token_limit=1000),
        )
        assert alert is None

    @pytest.mark.asyncio
    async def test_usage_at_warning_triggers_alert(self, manager):
        """Usage ≥ 80% → WARNING alert returned."""
        alert = await manager.check_and_alert(
            bot_id="test-bot",
            user_id=None,
            daily_usage=_make_usage(total_tokens=800),
            daily_quota=_make_quota(token_limit=1000),
        )
        assert alert is not None
        assert alert.level == QuotaAlertLevel.WARNING
        assert alert.bot_id == "test-bot"
        assert abs(alert.usage_percent - 0.80) < 0.001

    @pytest.mark.asyncio
    async def test_usage_at_critical_triggers_alert(self, manager):
        """Usage ≥ 95% → CRITICAL alert returned."""
        alert = await manager.check_and_alert(
            bot_id="test-bot",
            user_id=None,
            daily_usage=_make_usage(total_tokens=950),
            daily_quota=_make_quota(token_limit=1000),
        )
        assert alert is not None
        assert alert.level == QuotaAlertLevel.CRITICAL
        assert abs(alert.usage_percent - 0.95) < 0.001

    @pytest.mark.asyncio
    async def test_level_downgrade_does_not_re_alert(self, manager):
        """Level decreases (e.g. CRITICAL→WARNING) → no new alert."""
        # First set state to CRITICAL
        await manager.check_and_alert(
            bot_id="test-bot", user_id=None,
            daily_usage=_make_usage(total_tokens=1000),
            daily_quota=_make_quota(token_limit=1000),
        )
        # Then check with lower usage — level is WARNING but BELOW previous CRITICAL
        alert = await manager.check_and_alert(
            bot_id="test-bot", user_id=None,
            daily_usage=_make_usage(total_tokens=800),
            daily_quota=_make_quota(token_limit=1000),
        )
        assert alert is None

    @pytest.mark.asyncio
    async def test_level_promotion_from_warning_to_critical(self, manager):
        """WARNING → CRITICAL triggers a new alert."""
        await manager.check_and_alert(
            bot_id="test-bot", user_id=None,
            daily_usage=_make_usage(total_tokens=800),
            daily_quota=_make_quota(token_limit=1000),
        )
        # Promote to CRITICAL
        alert = await manager.check_and_alert(
            bot_id="test-bot", user_id=None,
            daily_usage=_make_usage(total_tokens=1000),
            daily_quota=_make_quota(token_limit=1000),
        )
        assert alert is not None
        assert alert.level == QuotaAlertLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_ok_never_triggers_alert(self, manager):
        """OK level never triggers an alert regardless of previous state."""
        await manager.check_and_alert(
            bot_id="test-bot", user_id=None,
            daily_usage=_make_usage(total_tokens=500),
            daily_quota=_make_quota(token_limit=1000),
        )
        alert = await manager.check_and_alert(
            bot_id="test-bot", user_id=None,
            daily_usage=_make_usage(total_tokens=400),
            daily_quota=_make_quota(token_limit=1000),
        )
        assert alert is None

    @pytest.mark.asyncio
    async def test_same_level_does_not_re_alert(self, manager):
        """Same WARNING level twice → no second alert."""
        alert1 = await manager.check_and_alert(
            bot_id="test-bot", user_id=None,
            daily_usage=_make_usage(total_tokens=800),
            daily_quota=_make_quota(token_limit=1000),
        )
        assert alert1 is not None
        alert2 = await manager.check_and_alert(
            bot_id="test-bot", user_id=None,
            daily_usage=_make_usage(total_tokens=850),
            daily_quota=_make_quota(token_limit=1000),
        )
        assert alert2 is None

    @pytest.mark.asyncio
    async def test_different_bot_ids_independent(self, manager):
        """Different bots have independent alert states."""
        # Bot A hits WARNING
        alert_a = await manager.check_and_alert(
            bot_id="bot-a", user_id=None,
            daily_usage=_make_usage(total_tokens=800),
            daily_quota=_make_quota(token_limit=1000),
        )
        assert alert_a is not None

        # Bot B also hits WARNING (independent)
        alert_b = await manager.check_and_alert(
            bot_id="bot-b", user_id=None,
            daily_usage=_make_usage(total_tokens=800),
            daily_quota=_make_quota(token_limit=1000),
        )
        assert alert_b is not None

    @pytest.mark.asyncio
    async def test_quota_zero_no_alert(self, manager):
        """daily_quota = {} or zero limits → no alert (usage_percent = 0.0)."""
        alert = await manager.check_and_alert(
            bot_id="test-bot", user_id=None,
            daily_usage=_make_usage(total_tokens=99999),
            daily_quota={},
        )
        assert alert is None

        # Also test with explicit zero token_limit
        alert2 = await manager.check_and_alert(
            bot_id="test-bot", user_id=None,
            daily_usage=_make_usage(total_tokens=99999),
            daily_quota=_make_quota(token_limit=0),
        )
        assert alert2 is None


# =========================================================================
# Test: Webhook URL validation (P0-7 SSRF prevention)
# =========================================================================

class TestValidateWebhookUrl:
    def test_https_allowed(self, manager):
        assert manager._validate_webhook_url("https://hooks.example.com/alerts") is True
        assert manager._validate_webhook_url("https://discord.com/api/webhooks/xxx") is True
        assert manager._validate_webhook_url("https://webhook.site/abc-123") is True

    def test_http_rejected(self, manager):
        assert manager._validate_webhook_url("http://hooks.example.com/alerts") is False
        assert manager._validate_webhook_url("http://evil.com/hook") is False

    def test_localhost_rejected(self, manager):
        assert manager._validate_webhook_url("https://localhost:8080/hook") is False
        assert manager._validate_webhook_url("https://127.0.0.1:9000/hook") is False
        assert manager._validate_webhook_url("https://0.0.0.0/hook") is False
        assert manager._validate_webhook_url("https://[::1]/hook") is False

    def test_private_ip_rejected(self, manager):
        assert manager._validate_webhook_url("https://10.0.0.1/hook") is False
        assert manager._validate_webhook_url("https://172.16.0.1/hook") is False
        assert manager._validate_webhook_url("https://192.168.1.1/hook") is False

    def test_empty_string_rejected(self, manager):
        assert manager._validate_webhook_url("") is False

    def test_malformed_url_rejected(self, manager):
        assert manager._validate_webhook_url("not-a-url") is False
        assert manager._validate_webhook_url("") is False

    def test_public_ip_allowed(self, manager):
        """Public IP addresses should be allowed."""
        assert manager._validate_webhook_url("https://93.184.216.34/hook") is True

    def test_fqdn_allowed(self, manager):
        """Fully qualified domain names should be allowed."""
        assert manager._validate_webhook_url("https://hooks.slack.com/services/xxx") is True
        assert manager._validate_webhook_url("https://example.com/webhook") is True


# =========================================================================
# Test: Webhook delivery
# =========================================================================

class TestSendWebhook:
    @pytest.mark.asyncio
    async def test_no_webhook_skips_silently(self, manager):
        """No webhook_url configured → no error, but alert is still created and returned."""
        alert = await manager.check_and_alert(
            bot_id="test-bot", user_id=None,
            daily_usage=_make_usage(total_tokens=800),
            daily_quota=_make_quota(token_limit=1000),
        )
        assert alert is not None
        assert alert.level == QuotaAlertLevel.WARNING

    @pytest.mark.asyncio
    async def test_webhook_success(self, manager_with_webhook):
        """Successful webhook delivery does not raise."""
        with patch("aiohttp.ClientSession") as mock_session:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_post_ctx = AsyncMock()
            mock_post_ctx.__aenter__.return_value = mock_resp
            mock_session.return_value.post.return_value = mock_post_ctx

            alert = await manager_with_webhook.check_and_alert(
                bot_id="test-bot", user_id=None,
                daily_usage=_make_usage(total_tokens=800),
                daily_quota=_make_quota(token_limit=1000),
            )
            assert alert is not None
            # Verify session.post was called with correct args
            mock_session.return_value.post.assert_called_once()
            call_kwargs = mock_session.return_value.post.call_args[1]
            assert call_kwargs["json"]["event"] == "quota_alert"
            assert call_kwargs["json"]["level"] == "warning"
            assert call_kwargs["max_redirects"] == 0

    @pytest.mark.asyncio
    async def test_webhook_http_error_logged(self, manager_with_webhook):
        """4xx/5xx response from webhook should not crash."""
        with patch("aiohttp.ClientSession") as mock_session:
            mock_resp = AsyncMock()
            mock_resp.status = 500
            mock_post_ctx = AsyncMock()
            mock_post_ctx.__aenter__.return_value = mock_resp
            mock_session.return_value.post.return_value = mock_post_ctx

            # Should not raise
            alert = await manager_with_webhook.check_and_alert(
                bot_id="test-bot", user_id=None,
                daily_usage=_make_usage(total_tokens=800),
                daily_quota=_make_quota(token_limit=1000),
            )
            assert alert is not None

    @pytest.mark.asyncio
    async def test_webhook_timeout_logged(self, manager_with_webhook):
        """Webhook timeout should not crash."""
        with patch("aiohttp.ClientSession") as mock_session:
            mock_post_ctx = AsyncMock()
            mock_post_ctx.post.side_effect = asyncio.TimeoutError()
            mock_session.return_value.post.side_effect = asyncio.TimeoutError()

            # Should not raise
            alert = await manager_with_webhook.check_and_alert(
                bot_id="test-bot", user_id=None,
                daily_usage=_make_usage(total_tokens=800),
                daily_quota=_make_quota(token_limit=1000),
            )
            assert alert is not None

    @pytest.mark.asyncio
    async def test_webhook_connection_error_logged(self, manager_with_webhook):
        """Connection error should not crash."""
        with patch("aiohttp.ClientSession") as mock_session:
            mock_post_ctx = AsyncMock()
            mock_post_ctx.post.side_effect = ConnectionError("Connection refused")
            mock_session.return_value.post.side_effect = ConnectionError("Connection refused")

            # Should not raise
            alert = await manager_with_webhook.check_and_alert(
                bot_id="test-bot", user_id=None,
                daily_usage=_make_usage(total_tokens=800),
                daily_quota=_make_quota(token_limit=1000),
            )
            assert alert is not None

    @pytest.mark.asyncio
    async def test_webhook_ssrf_rejected(self):
        """SSRF-prone URLs are rejected and do not trigger HTTP requests."""
        m = QuotaAlertManager(webhook_url="https://localhost:8080/hack")
        with patch("aiohttp.ClientSession.post") as mock_post:
            alert = await m.check_and_alert(
                bot_id="test-bot", user_id=None,
                daily_usage=_make_usage(total_tokens=800),
                daily_quota=_make_quota(token_limit=1000),
            )
            assert alert is not None
            mock_post.assert_not_called()


# =========================================================================
# Test: QuotaAlert dataclass
# =========================================================================

class TestQuotaAlert:
    def test_alert_dataclass(self):
        now = datetime.now(timezone.utc)
        alert = QuotaAlert(
            bot_id="test-bot",
            user_id="user-1",
            level=QuotaAlertLevel.CRITICAL,
            usage_percent=0.95,
            current_usage={"total_tokens": 9500},
            quota_limit={"token_limit": 10000},
            timestamp=now,
        )
        assert alert.bot_id == "test-bot"
        assert alert.user_id == "user-1"
        assert alert.level == QuotaAlertLevel.CRITICAL
        assert alert.usage_percent == 0.95
        assert alert.current_usage == {"total_tokens": 9500}
        assert alert.quota_limit == {"token_limit": 10000}
        assert alert.timestamp == now

    def test_default_timestamp(self):
        """Timestamp should default to now (UTC)."""
        alert = QuotaAlert(
            bot_id="test-bot",
            user_id=None,
            level=QuotaAlertLevel.WARNING,
            usage_percent=0.80,
            current_usage={},
            quota_limit={},
        )
        assert alert.timestamp is not None
        assert alert.timestamp.tzinfo is not None

    def test_webhook_payload_build(self, manager):
        now = datetime.now(timezone.utc)
        alert = QuotaAlert(
            bot_id="test-bot",
            user_id="user-1",
            level=QuotaAlertLevel.WARNING,
            usage_percent=0.85,
            current_usage={"total_tokens": 850},
            quota_limit={"token_limit": 1000},
            timestamp=now,
        )
        payload = manager._build_webhook_payload(alert)
        assert payload["event"] == "quota_alert"
        assert payload["level"] == "warning"
        assert payload["bot_id"] == "test-bot"
        assert payload["user_id"] == "user-1"
        assert payload["usage_percent"] == 85.0
        assert "850" in str(payload["current_usage"])
        assert "WARNING" in payload["message"]
