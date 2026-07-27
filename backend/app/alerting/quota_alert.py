"""配额告警管理器.

提供基于日配额的告警机制，支持 WARNING / CRITICAL 级别告警和 Webhook 通知.

关键审计修复:
  - P0-7: Webhook URL SSRF 防护 (仅 https, 禁止内网 IP)
  - P1-1: 统一在 record_usage() 中触发, 使用 asyncio.create_task() 异步执行
  - P1-5: 配额告警在锁外异步执行, 不阻塞关键路径
"""

import asyncio
import ipaddress
import logging
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

import aiohttp
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class QuotaAlertLevel(str, Enum):
    """配额告警级别."""
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class QuotaAlert:
    """配额告警事件数据."""
    bot_id: str
    user_id: Optional[str]
    level: QuotaAlertLevel
    usage_percent: float
    current_usage: Dict[str, Any]
    quota_limit: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class QuotaAlertConfig(BaseModel):
    """配额告警配置 (嵌入 Bot config 的 quota_alert 字段)."""
    enabled: bool = False
    webhook_url: str = ""
    warning_threshold: float = Field(0.80, ge=0.0, le=1.0)
    critical_threshold: float = Field(0.95, ge=0.0, le=1.0)


class QuotaAlertManager:
    """配额告警管理器.

    负责检查日配额使用率, 确定告警级别, 并在级别提升时发送 Webhook 通知.
    使用 _last_alert_level 追踪每个 (bot_id, user_id) 的最后告警级别,
    避免同一级别重复告警.
    """

    # 告警级别严重程度映射 (数值越大越严重)
    _LEVEL_SEVERITY = {
        QuotaAlertLevel.OK: 0,
        QuotaAlertLevel.WARNING: 1,
        QuotaAlertLevel.CRITICAL: 2,
    }

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        warning_threshold: float = 0.80,
        critical_threshold: float = 0.95,
    ) -> None:
        self._webhook_url = webhook_url
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold
        self._last_alert_level: Dict[str, QuotaAlertLevel] = {}
        self._session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check_and_alert(
        self,
        bot_id: str,
        user_id: Optional[str],
        daily_usage: Dict[str, Any],
        daily_quota: Dict[str, Any],
    ) -> Optional[QuotaAlert]:
        """检查配额使用率, 需要时发送告警.

        Args:
            bot_id: Bot 标识.
            user_id: 用户 ID (可选).
            daily_usage: 当日用量数据 (包含 requests, total_tokens 等).
            daily_quota: 配额限制数据 (包含 token_limit, request_limit 等).

        Returns:
            QuotaAlert 如果触发了告警, 否则 None.
        """
        usage_percent = self._calc_usage_percent(daily_usage, daily_quota)
        level = self._determine_level(usage_percent)

        alert_key = f"{bot_id}:{user_id or 'global'}"
        prev_level = self._last_alert_level.get(alert_key, QuotaAlertLevel.OK)

        # 只在级别提升时告警 (OK→WARNING, WARNING→CRITICAL)
        # 降级或同级不告警
        current_severity = self._LEVEL_SEVERITY.get(level, 0)
        prev_severity = self._LEVEL_SEVERITY.get(prev_level, 0)
        if current_severity <= prev_severity:
            self._last_alert_level[alert_key] = level
            return None

        alert = QuotaAlert(
            bot_id=bot_id,
            user_id=user_id,
            level=level,
            usage_percent=usage_percent,
            current_usage=dict(daily_usage),
            quota_limit=dict(daily_quota),
        )

        # 更新最后告警级别
        self._last_alert_level[alert_key] = level

        # 本地日志始终记录 (无论是否配置 Webhook)
        if level == QuotaAlertLevel.CRITICAL:
            logger.critical(
                "Quota alert: %s - bot='%s' usage=%.1f%% (CRITICAL)",
                alert_key, bot_id, usage_percent * 100,
            )
        else:
            logger.warning(
                "Quota alert: %s - bot='%s' usage=%.1f%% (WARNING)",
                alert_key, bot_id, usage_percent * 100,
            )

        # 异步发送 Webhook
        await self._send_webhook(alert)
        return alert

    async def close(self) -> None:
        """释放 Session 等资源."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # Internal: usage calculation
    # ------------------------------------------------------------------

    @staticmethod
    def _calc_usage_percent(daily_usage: Dict[str, Any], daily_quota: Dict[str, Any]) -> float:
        """计算日配额使用率, 返回 0.0 ~ 1.0 之间的值.

        优先使用 total_tokens / token_limit; 其次使用 requests / request_limit;
        如果无可比较维度则返回 0.0.
        """
        if not daily_quota:
            return 0.0

        # 主维度: token 配额
        total_tokens = daily_usage.get("total_tokens", 0)
        token_limit = daily_quota.get("token_limit", 0)
        if token_limit > 0:
            return min(total_tokens / token_limit, 1.0)

        # 备选维度: 请求数配额
        requests = daily_usage.get("requests", 0)
        request_limit = daily_quota.get("request_limit", 0)
        if request_limit > 0:
            return min(requests / request_limit, 1.0)

        return 0.0

    def _determine_level(self, usage_percent: float) -> QuotaAlertLevel:
        """根据使用率确定告警级别."""
        if usage_percent >= self._critical_threshold:
            return QuotaAlertLevel.CRITICAL
        if usage_percent >= self._warning_threshold:
            return QuotaAlertLevel.WARNING
        return QuotaAlertLevel.OK

    # ------------------------------------------------------------------
    # Internal: webhook delivery with SSRF protection
    # ------------------------------------------------------------------

    def _validate_webhook_url(self, url: str) -> bool:
        """P0-7 修复: 验证 Webhook URL 防止 SSRF.

        规则:
          - 仅允许 https 协议
          - 禁止 localhost / 127.0.0.1 / 0.0.0.0 / ::1
          - 禁止私有 IP 范围 (10.x, 172.16-31.x, 192.168.x)
          - 禁止 loopback / reserved IP
        """
        try:
            parsed = urllib.parse.urlparse(url)
            # 仅允许 https
            if parsed.scheme != "https":
                return False

            hostname = parsed.hostname or ""
            # 禁止已知的本地主机名
            if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
                return False

            # 禁止私有 / 回环 / 保留 IP 范围
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_reserved:
                    return False
            except ValueError:
                # hostname 不是 IP 地址 (域名), 允许
                pass

            return True
        except Exception:
            return False

    def _build_webhook_payload(self, alert: QuotaAlert) -> Dict[str, Any]:
        """构建 Webhook 请求体."""
        return {
            "event": "quota_alert",
            "level": alert.level.value,
            "bot_id": alert.bot_id,
            "user_id": alert.user_id,
            "usage_percent": round(alert.usage_percent * 100, 1),
            "current_usage": alert.current_usage,
            "quota_limit": alert.quota_limit,
            "timestamp": alert.timestamp.isoformat(),
            "message": (
                f"Quota alert for bot '{alert.bot_id}': "
                f"{alert.level.value.upper()} at {alert.usage_percent * 100:.1f}% usage"
            ),
        }

    async def _send_webhook(self, alert: QuotaAlert) -> None:
        """P0-7 修复: 发送 Webhook 通知, 带 SSRF 防护和超时.

        Webhook 发送失败不会抛出异常, 仅记录日志 (不阻塞主流程).
        """
        if not self._webhook_url:
            # 无 Webhook 配置时只依赖本地日志
            return

        # SSRF 防护
        if not self._validate_webhook_url(self._webhook_url):
            logger.warning(
                "Webhook URL rejected (SSRF prevention): %s", self._webhook_url,
            )
            return

        payload = self._build_webhook_payload(alert)

        # P1-A: 复用 ClientSession 实例 (非每次创建)
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        try:
            async with self._session.post(
                self._webhook_url,
                json=payload,
                max_redirects=0,
            ) as resp:
                if resp.status >= 400:
                    logger.warning(
                        "Webhook returned %d for bot %s", resp.status, alert.bot_id,
                    )
        except asyncio.TimeoutError:
            logger.warning("Webhook timeout for bot %s", alert.bot_id)
        except Exception as e:
            logger.warning("Webhook failed for bot %s: %s", alert.bot_id, e)
