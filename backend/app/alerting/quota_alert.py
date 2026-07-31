"""配额告警管理器.

提供基于日配额的告警机制，支持 WARNING / CRITICAL 级别告警和 Webhook 通知.

关键审计修复:
  - P0-7: Webhook URL SSRF 防护 (仅 https, 禁止内网 IP)
  - P1-1: 统一在 record_usage() 中触发, 使用 asyncio.create_task() 异步执行
  - P1-5: 配额告警在锁外异步执行, 不阻塞关键路径
  - P2-x: per-call 配置覆盖 + SSRF 单点校验/重定向/掩码/白名单 (security+qa 复审)
"""

import asyncio
import ipaddress
import logging
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional, Tuple

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
    token_limit: int = Field(1000000, ge=0)
    request_limit: int = Field(1000, ge=0)


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

    # 白名单载荷键: quota_limit 只输出明确字段, 未知键一律不进 payload
    _PAYLOAD_QUOTA_KEYS: Tuple[str, ...] = (
        "token_limit", "request_limit", "warning_threshold", "critical_threshold",
    )
    # 静态通配重指向域黑名单 (HIGH-3)
    _WILDCARD_REDIRECT_DOMAINS: Tuple[str, ...] = ("nip.io", "sslip.io", "xip.io")

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

        per-call 覆盖语义: daily_quota 提供的值优先 (生产路径由
        UsageTracker._read_bot_quota_config 产出, 恒含阈值与限额键); 键缺失时
        回退 manager 构造参数 (主要服务于直接调用场景, 如测试).

        安全契约:
          - effective_url 在本函数单点解析, _send_webhook 不做回退 (HIGH-2);
          - quota_limit 载荷白名单化, webhook_url 等敏感键不进 QuotaAlert
            与 webhook payload (MEDIUM-2);
          - 去重键携带日期, 跨天告警不丢失 (M4).
        """
        usage_percent = self._calc_usage_percent(daily_usage, daily_quota)

        warning_threshold = daily_quota.get("warning_threshold")
        critical_threshold = daily_quota.get("critical_threshold")
        level = self._determine_level(usage_percent, warning_threshold, critical_threshold)

        alert_key = (
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
            f":{bot_id}:{user_id or 'global'}"
        )
        prev_level = self._last_alert_level.get(alert_key, QuotaAlertLevel.OK)

        # 只在级别提升时告警 (OK→WARNING, WARNING→CRITICAL)
        # 降级或同级不告警
        current_severity = self._LEVEL_SEVERITY.get(level, 0)
        prev_severity = self._LEVEL_SEVERITY.get(prev_level, 0)
        if current_severity <= prev_severity:
            self._last_alert_level[alert_key] = level
            return None

        quota_limit = {
            k: v for k, v in daily_quota.items()
            if k in self._PAYLOAD_QUOTA_KEYS
        }
        alert = QuotaAlert(
            bot_id=bot_id,
            user_id=user_id,
            level=level,
            usage_percent=usage_percent,
            current_usage=dict(daily_usage),
            quota_limit=quota_limit,
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

        # 异步发送 Webhook (effective_url 单点解析, _send_webhook 不做回退)
        effective_url = daily_quota.get("webhook_url") or self._webhook_url
        await self._send_webhook(alert, effective_url)
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

    def _determine_level(
        self,
        usage_percent: float,
        warning_threshold: Optional[float] = None,
        critical_threshold: Optional[float] = None,
    ) -> QuotaAlertLevel:
        """根据使用率确定告警级别; 阈值参数为 None 时回退实例配置.

        注意: 显式 is None 判断, warning_threshold=0.0 是合法值, 不能用 or 回退.
        """
        if warning_threshold is None:
            warning_threshold = self._warning_threshold
        if critical_threshold is None:
            critical_threshold = self._critical_threshold
        if usage_percent >= critical_threshold:
            return QuotaAlertLevel.CRITICAL
        if usage_percent >= warning_threshold:
            return QuotaAlertLevel.WARNING
        return QuotaAlertLevel.OK

    # ------------------------------------------------------------------
    # Internal: webhook delivery with SSRF protection
    # ------------------------------------------------------------------

    @staticmethod
    def _redact_url(url: str) -> str:
        """返回仅含 scheme://hostname[:port] 的掩码形式, 隐藏 path 中的 webhook token.

        保留端口以便定位被拒的端点 (hostname 本身不含端口).
        """
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.hostname:
                host = parsed.hostname
                if parsed.port is not None:
                    host = f"{host}:{parsed.port}"
                return f"{parsed.scheme}://{host}"
        except Exception:
            pass
        return "<invalid>"

    def _validate_webhook_url(self, url: str) -> bool:
        """验证 Webhook URL 防止 SSRF (单一校验点, 作用于最终生效 URL).

        规则 (security 复审修订):
          - 仅允许 https
          - hostname 缺失 (None/空) → 拒绝
          - 显式黑名单: localhost / 127.0.0.1 / 0.0.0.0 / ::1 (含尾部点变体)
          - 纯数字/hex 形态主机名 (2130706433 / 0x7f.0.0.1 / 127.1): ipaddress
            解析失败即拒绝 —— Linux/glibc getaddrinfo 接受此类形式 (HIGH-3)
          - zone-id IPv6 ([fe80::1%eth0]): 先于解析拦截 (MEDIUM-3)
          - 静态通配重指向域 (nip.io / sslip.io / xip.io 小写子串) → 拒绝 (HIGH-3)
          - IP 判定: IPv4-mapped IPv6 解包为内嵌 IPv4 后统一检查 private /
            loopback / link-local / reserved / multicast / unspecified

        残余风险 (HIGH-3): 静态通配 DNS (仅堵已知域, 黑名单需维护); DNS
        rebinding (校验用静态 hostname, 连接时解析); 校验与连接间 TOCTOU。
        三者需异步解析器 + IP 钉扎才能根治, 本次不做。威胁模型: webhook_url
        是管理员信任输入 (X-API-Key 持有者), 非不可信终端输入。
        """
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme != "https":
                return False
            hostname = parsed.hostname
            if not hostname:
                return False
            hostname = hostname.rstrip(".")
            if "%" in hostname:
                return False
            if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
                return False
            # 纯数字/hex/点/冒号形态: 只能是 IP 字面量, 解析失败即拒绝
            if re.fullmatch(r"[0-9a-fA-Fx.:]+", hostname):
                try:
                    ip = ipaddress.ip_address(hostname)
                except ValueError:
                    return False
                if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
                    ip = ip.ipv4_mapped
                if (ip.is_private or ip.is_loopback or ip.is_link_local
                        or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
                    return False
                return True
            lowered = hostname.lower()
            if any(d in lowered for d in self._WILDCARD_REDIRECT_DOMAINS):
                return False
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

    async def _send_webhook(self, alert: QuotaAlert, webhook_url: Optional[str] = None) -> None:
        """发送 Webhook 通知 — 单一校验路径 (HIGH-2).

        对传入的同一 URL 依次执行: 非空 → _validate_webhook_url → 发送。
        本函数不做 URL 解析/回退 (effective_url 已由 check_and_alert 单点解析);
        None/空串 → 静默跳过 (仅本地日志)。发送失败不抛异常, 仅记日志。
        """
        if not webhook_url:
            return
        if not self._validate_webhook_url(webhook_url):
            logger.warning(
                "Webhook URL rejected (SSRF prevention): %s",
                self._redact_url(webhook_url),
            )
            return
        payload = self._build_webhook_payload(alert)
        # P1-A: 复用 ClientSession 实例 (非每次创建)
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        try:
            async with self._session.post(
                webhook_url,
                json=payload,
                allow_redirects=False,
            ) as resp:
                if resp.status >= 400:
                    logger.warning(
                        "Webhook returned %d for bot %s", resp.status, alert.bot_id,
                    )
                elif resp.status >= 300:
                    logger.warning(
                        "Webhook returned %d (redirect not followed) for bot %s",
                        resp.status, alert.bot_id,
                    )
        except asyncio.TimeoutError:
            logger.warning("Webhook timeout for bot %s", alert.bot_id)
        except Exception as e:
            logger.warning(
                "Webhook failed for bot %s: %s (url=%s)",
                alert.bot_id, type(e).__name__, self._redact_url(webhook_url or ""),
            )
